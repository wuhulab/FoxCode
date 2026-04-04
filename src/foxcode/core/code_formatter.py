"""
FoxCode 代码格式化器

提供多语言代码格式化功能，支持 Python、JavaScript/TypeScript 等。

主要功能：
- Python 格式化 (black, autopep8)
- JavaScript/TypeScript 格式化 (prettier)
- 配置文件检测和应用
- 批量格式化和增量格式化
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class FormatterType(str, Enum):
    """格式化器类型"""
    BLACK = "black"           # Python - black
    AUTOPEP8 = "autopep8"     # Python - autopep8
    YAPF = "yapf"             # Python - yapf
    PRETTIER = "prettier"     # JavaScript/TypeScript/JSON/CSS
    ESLINT = "eslint"         # JavaScript/TypeScript
    RUFF = "ruff"             # Python - ruff
    GO_FMT = "gofmt"          # Go
    RUSTFMT = "rustfmt"       # Rust
    CLANG_FORMAT = "clang-format"  # C/C++


class Language(str, Enum):
    """编程语言"""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JSON = "json"
    CSS = "css"
    HTML = "html"
    MARKDOWN = "markdown"
    GO = "go"
    RUST = "rust"
    C = "c"
    CPP = "cpp"
    JAVA = "java"
    UNKNOWN = "unknown"


@dataclass
class FormatResult:
    """
    格式化结果
    
    Attributes:
        success: 是否成功
        original_content: 原始内容
        formatted_content: 格式化后内容
        formatter_used: 使用的格式化器
        changes_made: 是否有更改
        error: 错误信息
        file_path: 文件路径
        duration_ms: 耗时（毫秒）
    """
    success: bool = True
    original_content: str = ""
    formatted_content: str = ""
    formatter_used: str = ""
    changes_made: bool = False
    error: str = ""
    file_path: str = ""
    duration_ms: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "formatter_used": self.formatter_used,
            "changes_made": self.changes_made,
            "error": self.error,
            "file_path": self.file_path,
            "duration_ms": self.duration_ms,
        }


@dataclass
class BatchFormatResult:
    """
    批量格式化结果
    
    Attributes:
        total_files: 总文件数
        successful: 成功数
        failed: 失败数
        changed: 更改数
        unchanged: 未更改数
        results: 各文件结果
        duration_ms: 总耗时
    """
    total_files: int = 0
    successful: int = 0
    failed: int = 0
    changed: int = 0
    unchanged: int = 0
    results: list[FormatResult] = field(default_factory=list)
    duration_ms: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "total_files": self.total_files,
            "successful": self.successful,
            "failed": self.failed,
            "changed": self.changed,
            "unchanged": self.unchanged,
            "duration_ms": self.duration_ms,
        }


class FormatterConfig(BaseModel):
    """
    格式化器配置
    
    Attributes:
        default_python_formatter: 默认 Python 格式化器
        default_js_formatter: 默认 JS 格式化器
        line_length: 行长度限制
        indent_size: 缩进大小
        use_tabs: 是否使用制表符
        quote_style: 引号风格
        format_on_save: 保存时自动格式化
        exclude_patterns: 排除模式
    """
    default_python_formatter: FormatterType = FormatterType.BLACK
    default_js_formatter: FormatterType = FormatterType.PRETTIER
    line_length: int = Field(default=88, ge=40, le=200)
    indent_size: int = Field(default=4, ge=2, le=8)
    use_tabs: bool = False
    quote_style: str = "double"  # double, single
    format_on_save: bool = True
    exclude_patterns: list[str] = Field(
        default_factory=lambda: [
            "node_modules", ".git", "__pycache__", "venv", ".venv",
            "dist", "build", "*.min.js", "*.min.css"
        ]
    )


class CodeFormatter:
    """
    多语言代码格式化器
    
    提供多种语言的代码格式化功能。
    
    Example:
        >>> formatter = CodeFormatter()
        >>> result = await formatter.format_file(Path("main.py"))
        >>> print(f"格式化成功: {result.success}")
    """
    
    # 文件扩展名到语言的映射
    EXTENSION_LANGUAGE_MAP = {
        ".py": Language.PYTHON,
        ".pyw": Language.PYTHON,
        ".js": Language.JAVASCRIPT,
        ".mjs": Language.JAVASCRIPT,
        ".cjs": Language.JAVASCRIPT,
        ".ts": Language.TYPESCRIPT,
        ".tsx": Language.TYPESCRIPT,
        ".jsx": Language.JAVASCRIPT,
        ".json": Language.JSON,
        ".css": Language.CSS,
        ".scss": Language.CSS,
        ".less": Language.CSS,
        ".html": Language.HTML,
        ".htm": Language.HTML,
        ".md": Language.MARKDOWN,
        ".markdown": Language.MARKDOWN,
        ".go": Language.GO,
        ".rs": Language.RUST,
        ".c": Language.C,
        ".h": Language.C,
        ".cpp": Language.CPP,
        ".hpp": Language.CPP,
        ".cc": Language.CPP,
        ".java": Language.JAVA,
    }
    
    # 语言到格式化器的映射
    LANGUAGE_FORMATTER_MAP = {
        Language.PYTHON: [FormatterType.RUFF, FormatterType.BLACK, FormatterType.AUTOPEP8],
        Language.JAVASCRIPT: [FormatterType.PRETTIER],
        Language.TYPESCRIPT: [FormatterType.PRETTIER],
        Language.JSON: [FormatterType.PRETTIER],
        Language.CSS: [FormatterType.PRETTIER],
        Language.HTML: [FormatterType.PRETTIER],
        Language.MARKDOWN: [FormatterType.PRETTIER],
        Language.GO: [FormatterType.GO_FMT],
        Language.RUST: [FormatterType.RUSTFMT],
        Language.C: [FormatterType.CLANG_FORMAT],
        Language.CPP: [FormatterType.CLANG_FORMAT],
    }
    
    def __init__(self, config: FormatterConfig | None = None):
        """
        初始化格式化器
        
        Args:
            config: 格式化器配置
        """
        self.config = config or FormatterConfig()
        self._available_formatters = self._detect_available_formatters()
        logger.info(f"代码格式化器初始化完成，可用格式化器: {list(self._available_formatters.keys())}")
    
    def _detect_available_formatters(self) -> dict[FormatterType, bool]:
        """检测可用的格式化器"""
        available = {}
        
        formatters = [
            (FormatterType.BLACK, "black"),
            (FormatterType.AUTOPEP8, "autopep8"),
            (FormatterType.RUFF, "ruff"),
            (FormatterType.PRETTIER, "prettier"),
            (FormatterType.GO_FMT, "gofmt"),
            (FormatterType.RUSTFMT, "rustfmt"),
            (FormatterType.CLANG_FORMAT, "clang-format"),
        ]
        
        for formatter_type, command in formatters:
            try:
                result = subprocess.run(
                    [command, "--version"],
                    capture_output=True,
                    timeout=5,
                )
                available[formatter_type] = result.returncode == 0
            except (subprocess.SubprocessError, FileNotFoundError):
                available[formatter_type] = False
        
        return available
    
    def detect_language(self, file_path: Path) -> Language:
        """
        检测文件语言
        
        Args:
            file_path: 文件路径
            
        Returns:
            语言类型
        """
        ext = file_path.suffix.lower()
        return self.EXTENSION_LANGUAGE_MAP.get(ext, Language.UNKNOWN)
    
    def detect_formatter(self, file_path: Path) -> FormatterType | None:
        """
        检测应使用的格式化器
        
        Args:
            file_path: 文件路径
            
        Returns:
            格式化器类型
        """
        language = self.detect_language(file_path)
        
        if language == Language.UNKNOWN:
            return None
        
        # 检查项目配置
        project_formatter = self._check_project_formatter(file_path, language)
        if project_formatter:
            return project_formatter
        
        # 使用默认格式化器
        formatters = self.LANGUAGE_FORMATTER_MAP.get(language, [])
        
        for formatter in formatters:
            if self._available_formatters.get(formatter, False):
                return formatter
        
        return None
    
    def _check_project_formatter(
        self,
        file_path: Path,
        language: Language,
    ) -> FormatterType | None:
        """检查项目配置的格式化器"""
        # 检查 pyproject.toml
        if language == Language.PYTHON:
            pyproject = self._find_config_file(file_path, "pyproject.toml")
            if pyproject:
                try:
                    import tomli
                    with open(pyproject, "rb") as f:
                        data = tomli.load(f)
                    
                    # 检查 black 配置
                    if "tool" in data and "black" in data["tool"]:
                        return FormatterType.BLACK
                    # 检查 ruff 配置
                    if "tool" in data and "ruff" in data["tool"]:
                        return FormatterType.RUFF
                except Exception:
                    pass
        
        # 检查 .prettierrc
        if language in (Language.JAVASCRIPT, Language.TYPESCRIPT, Language.JSON, Language.CSS):
            prettier_config = self._find_config_file(file_path, ".prettierrc")
            if prettier_config:
                return FormatterType.PRETTIER
        
        return None
    
    def _find_config_file(self, file_path: Path, config_name: str) -> Path | None:
        """查找配置文件"""
        current = file_path.parent if file_path.is_file() else file_path
        
        while current != current.parent:
            config_path = current / config_name
            if config_path.exists():
                return config_path
            current = current.parent
        
        return None
    
    def load_editorconfig(self, file_path: Path) -> dict[str, Any]:
        """
        加载 .editorconfig 配置
        
        Args:
            file_path: 文件路径
            
        Returns:
            配置字典
        """
        config = {}
        editorconfig_path = self._find_config_file(file_path, ".editorconfig")
        
        if not editorconfig_path:
            return config
        
        try:
            with open(editorconfig_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 简单解析 .editorconfig
            current_section = None
            for line in content.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                if line.startswith("[") and line.endswith("]"):
                    current_section = line[1:-1]
                    continue
                
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip().lower()
                    value = value.strip().lower()
                    
                    if key == "indent_style":
                        config["use_tabs"] = value == "tab"
                    elif key == "indent_size":
                        config["indent_size"] = int(value)
                    elif key == "max_line_length":
                        config["line_length"] = int(value)
                    elif key == "quote_type":
                        config["quote_style"] = value
            
        except Exception as e:
            logger.debug(f"解析 .editorconfig 失败: {e}")
        
        return config
    
    async def format_file(self, file_path: Path) -> FormatResult:
        """
        格式化单个文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            格式化结果
        """
        start_time = datetime.now()
        
        if not file_path.exists():
            return FormatResult(
                success=False,
                error=f"文件不存在: {file_path}",
                file_path=str(file_path),
            )
        
        # 检测格式化器
        formatter_type = self.detect_formatter(file_path)
        if not formatter_type:
            return FormatResult(
                success=False,
                error="未找到可用的格式化器",
                file_path=str(file_path),
            )
        
        # 检查格式化器是否可用
        if not self._available_formatters.get(formatter_type, False):
            return FormatResult(
                success=False,
                error=f"格式化器 {formatter_type.value} 不可用",
                file_path=str(file_path),
            )
        
        try:
            # 读取文件内容
            with open(file_path, "r", encoding="utf-8") as f:
                original_content = f.read()
            
            # 格式化
            formatted_content = await self._format_with_formatter(
                original_content,
                formatter_type,
                file_path,
            )
            
            # 计算耗时
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # 检查是否有更改
            changes_made = formatted_content != original_content
            
            # 如果有更改，写回文件
            if changes_made:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(formatted_content)
            
            return FormatResult(
                success=True,
                original_content=original_content,
                formatted_content=formatted_content,
                formatter_used=formatter_type.value,
                changes_made=changes_made,
                file_path=str(file_path),
                duration_ms=duration_ms,
            )
            
        except Exception as e:
            return FormatResult(
                success=False,
                error=str(e),
                file_path=str(file_path),
            )
    
    async def format_code(
        self,
        code: str,
        language: Language,
    ) -> str:
        """
        格式化代码字符串
        
        Args:
            code: 代码字符串
            language: 语言类型
            
        Returns:
            格式化后的代码
        """
        # 获取默认格式化器
        formatters = self.LANGUAGE_FORMATTER_MAP.get(language, [])
        
        for formatter in formatters:
            if self._available_formatters.get(formatter, False):
                return await self._format_with_formatter(code, formatter, None)
        
        # 没有可用的格式化器，返回原代码
        return code
    
    async def _format_with_formatter(
        self,
        code: str,
        formatter_type: FormatterType,
        file_path: Path | None = None,
    ) -> str:
        """使用指定格式化器格式化代码"""
        if formatter_type == FormatterType.BLACK:
            return await self._format_with_black(code, file_path)
        elif formatter_type == FormatterType.AUTOPEP8:
            return await self._format_with_autopep8(code, file_path)
        elif formatter_type == FormatterType.RUFF:
            return await self._format_with_ruff(code, file_path)
        elif formatter_type == FormatterType.PRETTIER:
            return await self._format_with_prettier(code, file_path)
        elif formatter_type == FormatterType.GO_FMT:
            return await self._format_with_gofmt(code, file_path)
        else:
            return code
    
    async def _format_with_black(
        self,
        code: str,
        file_path: Path | None = None,
    ) -> str:
        """使用 black 格式化"""
        try:
            import black
            
            mode = black.FileMode(
                line_length=self.config.line_length,
                string_normalization=self.config.quote_style == "double",
            )
            
            return black.format_str(code, mode=mode)
        except ImportError:
            # 使用命令行
            return await self._run_formatter_command(
                ["black", "--line-length", str(self.config.line_length), "-"],
                code,
            )
    
    async def _format_with_autopep8(
        self,
        code: str,
        file_path: Path | None = None,
    ) -> str:
        """使用 autopep8 格式化"""
        try:
            import autopep8
            
            return autopep8.fix_code(
                code,
                options={"max_line_length": self.config.line_length},
            )
        except ImportError:
            return await self._run_formatter_command(
                ["autopep8", "--max-line-length", str(self.config.line_length), "-"],
                code,
            )
    
    async def _format_with_ruff(
        self,
        code: str,
        file_path: Path | None = None,
    ) -> str:
        """使用 ruff 格式化"""
        return await self._run_formatter_command(
            ["ruff", "format", "--line-length", str(self.config.line_length), "-"],
            code,
        )
    
    async def _format_with_prettier(
        self,
        code: str,
        file_path: Path | None = None,
    ) -> str:
        """使用 prettier 格式化"""
        args = [
            "prettier",
            "--print-width", str(self.config.line_length),
            "--tab-width", str(self.config.indent_size),
            "--use-tabs" if self.config.use_tabs else "--no-use-tabs",
            "--single-quote" if self.config.quote_style == "single" else "--no-single-quote",
            "--stdin-filepath", str(file_path) if file_path else "stdin",
        ]
        
        return await self._run_formatter_command(args, code)
    
    async def _format_with_gofmt(
        self,
        code: str,
        file_path: Path | None = None,
    ) -> str:
        """使用 gofmt 格式化"""
        return await self._run_formatter_command(["gofmt"], code)
    
    async def _run_formatter_command(
        self,
        args: list[str],
        input_code: str,
    ) -> str:
        """运行格式化器命令"""
        try:
            result = subprocess.run(
                args,
                input=input_code,
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode == 0:
                return result.stdout
            else:
                logger.warning(f"格式化器返回错误: {result.stderr}")
                return input_code
                
        except subprocess.TimeoutExpired:
            logger.error("格式化器执行超时")
            return input_code
        except Exception as e:
            logger.error(f"格式化器执行失败: {e}")
            return input_code
    
    async def format_directory(
        self,
        directory: Path,
        recursive: bool = True,
    ) -> BatchFormatResult:
        """
        批量格式化目录
        
        Args:
            directory: 目录路径
            recursive: 是否递归
            
        Returns:
            批量格式化结果
        """
        start_time = datetime.now()
        result = BatchFormatResult()
        
        # 收集文件
        files = []
        if recursive:
            for ext in self.EXTENSION_LANGUAGE_MAP.keys():
                files.extend(directory.rglob(f"*{ext}"))
        else:
            for ext in self.EXTENSION_LANGUAGE_MAP.keys():
                files.extend(directory.glob(f"*{ext}"))
        
        # 过滤排除的文件
        files = [
            f for f in files
            if not any(pattern in str(f) for pattern in self.config.exclude_patterns)
        ]
        
        result.total_files = len(files)
        
        # 格式化每个文件
        for file_path in files:
            format_result = await self.format_file(file_path)
            result.results.append(format_result)
            
            if format_result.success:
                result.successful += 1
                if format_result.changes_made:
                    result.changed += 1
                else:
                    result.unchanged += 1
            else:
                result.failed += 1
        
        result.duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        
        return result
    
    def get_available_formatters(self) -> list[str]:
        """获取可用的格式化器列表"""
        return [
            ft.value for ft, available in self._available_formatters.items()
            if available
        ]


# 创建默认格式化器实例
code_formatter = CodeFormatter()
