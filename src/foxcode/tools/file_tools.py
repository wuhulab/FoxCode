"""
FoxCode 文件操作工具

提供文件读写、搜索、管理等功能
"""

from __future__ import annotations

import asyncio
import fnmatch
import hashlib
import logging
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiofiles

from foxcode.core.encoding import decode_bytes, detect_encoding
from foxcode.tools.base import (
    BaseTool,
    ToolCategory,
    ToolParameter,
    ToolResult,
    tool,
)

logger = logging.getLogger(__name__)


def _safe_error_message(operation: str, error: Exception, include_details: bool = False) -> str:
    """
    生成安全的错误消息
    
    对用户显示通用错误消息，详细错误记录到日志。
    防止敏感路径和系统信息泄露。
    
    Args:
        operation: 操作类型
        error: 原始异常
        include_details: 是否包含详细信息（仅用于调试模式）
        
    Returns:
        安全的错误消息
    """
    # 记录详细错误到日志
    logger.error(f"{operation} 失败: {error}")
    
    if include_details:
        # 调试模式下返回详细信息（但仍然脱敏路径）
        error_str = str(error)
        # 脱敏路径信息
        error_str = re.sub(r'[A-Za-z]:\\[^\s<>:"|?*]+', '***PATH***', error_str)
        error_str = re.sub(r'/[^\s<>:"|?*]+/[^\s<>:"|?*]+', '***PATH***', error_str)
        return f"{operation} 失败: {error_str}"
    
    # 返回通用错误消息
    error_type = type(error).__name__
    generic_messages = {
        'FileNotFoundError': f"文件不存在或无法访问",
        'PermissionError': f"权限不足，无法执行操作",
        'IsADirectoryError': f"目标是一个目录，不是文件",
        'NotADirectoryError': f"目标不是目录",
        'FileExistsError': f"文件已存在",
        'OSError': f"系统错误，操作失败",
        'UnicodeDecodeError': f"文件编码不支持",
        'ValueError': f"参数无效",
    }
    
    return generic_messages.get(error_type, f"{operation} 失败，请检查参数后重试")


@dataclass
class PathSecurityConfig:
    """
    路径安全配置
    
    控制文件操作的路径访问权限
    """
    enabled: bool = True
    allowed_directories: list[str] = field(default_factory=list)
    denied_directories: list[str] = field(default_factory=lambda: [
        "/etc", "/var", "/root", "/home",
        "C:\\Windows", "C:\\Program Files", "C:\\ProgramData",
        "C:\\Users", "\\Windows", "\\Program Files",
    ])
    allow_symlinks: bool = False
    max_symlink_depth: int = 5
    follow_symlinks_in_allowed_dirs: bool = True


class PathSecurityValidator:
    """
    路径安全验证器
    
    验证文件路径是否在允许的工作目录范围内，防止路径穿越攻击
    """
    
    def __init__(self, config: PathSecurityConfig | None = None):
        self.config = config or PathSecurityConfig()
        self._allowed_paths: list[Path] = []
        self._denied_paths: list[Path] = []
        self._initialized = False
    
    def initialize(self, working_dir: Path | str | None = None) -> None:
        """
        初始化允许的目录列表
        
        Args:
            working_dir: 工作目录，如果未指定则使用当前目录
        """
        if working_dir is None:
            working_dir = Path.cwd()
        working_path = Path(working_dir).resolve()
        
        self._allowed_paths = [working_path]
        
        for allowed in self.config.allowed_directories:
            try:
                allowed_path = Path(allowed).resolve()
                if allowed_path.exists() and allowed_path.is_dir():
                    self._allowed_paths.append(allowed_path)
            except Exception as e:
                logger.warning(f"无法添加允许目录 {allowed}: {e}")
        
        self._denied_paths = []
        for denied in self.config.denied_directories:
            try:
                denied_path = Path(denied)
                if denied_path.exists():
                    self._denied_paths.append(denied_path.resolve())
            except Exception:
                pass
        
        self._initialized = True
        logger.info(f"路径安全验证器初始化完成，允许目录: {[str(p) for p in self._allowed_paths]}")
    
    def validate_path(
        self,
        file_path: str | Path,
        operation: str = "read",
        check_symlink: bool = True,
    ) -> tuple[bool, str, Path | None]:
        """
        验证路径是否安全（增强版）
        
        安全检查包括：
        - 路径规范化（防止 ../ 等遍历）
        - 符号链接检测和验证
        - 允许/禁止目录检查
        - 中间路径组件检查
        
        Args:
            file_path: 要验证的路径
            operation: 操作类型 (read, write, delete)
            check_symlink: 是否检查符号链接
            
        Returns:
            (是否安全, 错误消息, 解析后的路径)
        """
        if not self._initialized:
            self.initialize()
        
        if not self.config.enabled:
            try:
                return True, "", Path(file_path).resolve()
            except Exception as e:
                return False, f"路径解析失败: {e}", None
        
        try:
            path = Path(file_path)
            
            # 检查空字节注入
            if '\x00' in str(path):
                return False, "路径包含非法的空字节", None
            
            # 标准化路径，检测路径穿越
            normalized = os.path.normpath(str(path))
            path_parts = normalized.split(os.sep)
            
            # 检查路径穿越尝试（包括编码绕过）
            for part in path_parts:
                if part == '..':
                    return False, "路径包含非法的遍历字符 (..)", None
                # 检测 Unicode 同形字符绕过
                if self._contains_unicode_confusable(part):
                    return False, f"路径包含可疑的 Unicode 字符", None
            
            # 解析路径（解析符号链接）
            try:
                # 使用 lstat 检查是否是符号链接，然后再解析
                if path.exists() and path.is_symlink():
                    if not self.config.allow_symlinks:
                        return False, "路径是符号链接且不允许符号链接", None
                    # 解析符号链接目标
                    resolved_path = Path(os.path.realpath(str(path)))
                else:
                    resolved_path = Path(os.path.realpath(str(path))) if path.exists() else path.resolve(strict=False)
            except Exception as e:
                try:
                    resolved_path = path.resolve(strict=False)
                except Exception as e2:
                    return False, f"路径解析失败: {e2}", None
            
            # 符号链接安全检查
            if check_symlink and not self.config.allow_symlinks:
                symlink_result = self._check_symlink_enhanced(path, resolved_path)
                if symlink_result:
                    return False, symlink_result, None
            
            # 检查解析后的路径是否在禁止目录中
            for denied in self._denied_paths:
                try:
                    if self._is_subpath(resolved_path, denied):
                        return False, f"路径在禁止目录中", None
                except Exception:
                    pass
            
            # 检查解析后的路径是否在允许目录中
            is_allowed = False
            for allowed in self._allowed_paths:
                try:
                    if self._is_subpath(resolved_path, allowed) or resolved_path == allowed:
                        is_allowed = True
                        break
                except Exception:
                    pass
            
            if not is_allowed:
                return False, "路径不在允许的工作目录范围内", None
            
            # 验证路径组件（防止中间符号链接攻击）
            try:
                self._validate_path_components(resolved_path)
            except ValueError as e:
                return False, str(e), None
            
            # 检查操作类型
            if operation in ("write", "delete"):
                if path.exists() and path.is_dir():
                    return False, f"路径是目录，无法执行 {operation} 操作", None
            
            # 最终验证：确保解析后的路径仍然在允许目录内（防止竞态条件）
            if not self._final_path_validation(resolved_path):
                return False, "路径验证失败，可能存在竞态条件", None
            
            return True, "", resolved_path
            
        except Exception as e:
            logger.error(f"路径验证异常: {e}")
            return False, "路径验证失败", None
    
    def _contains_unicode_confusable(self, text: str) -> bool:
        """
        检查文本是否包含 Unicode 同形字符
        
        Args:
            text: 要检查的文本
            
        Returns:
            是否包含可疑字符
        """
        # 常见的路径相关 Unicode 同形字符
        suspicious_chars = {
            '\uff0e': '.',  # 全角句号
            '\u2024': '.',  # 单点前导符
            '\uff0f': '/',  # 全角斜杠
            '\uff3c': '\\', # 全角反斜杠
            '\u2215': '/',  # 除号
            '\u2216': '\\', # 集合减号
        }
        
        for char in suspicious_chars:
            if char in text:
                return True
        return False
    
    def _final_path_validation(self, resolved_path: Path) -> bool:
        """
        最终路径验证（防止竞态条件）
        
        使用文件描述符验证路径，防止 TOCTOU 攻击。
        
        Args:
            resolved_path: 解析后的路径
            
        Returns:
            是否验证通过
        """
        try:
            # 检查路径是否存在
            if not resolved_path.exists():
                return True  # 新文件，允许创建
            
            # 使用 os.open 获取文件描述符（带 O_NOFOLLOW 防止符号链接）
            if hasattr(os, 'O_NOFOLLOW'):
                try:
                    fd = os.open(str(resolved_path), os.O_RDONLY | os.O_NOFOLLOW)
                    os.close(fd)
                except OSError:
                    # 可能是符号链接或无法访问
                    return False
            
            # 再次验证路径是否在允许目录内
            for allowed in self._allowed_paths:
                try:
                    resolved_path.relative_to(allowed)
                    return True
                except ValueError:
                    continue
            
            return False
        except Exception:
            return False
    
    def _check_symlink_enhanced(self, original_path: Path, resolved_path: Path) -> str | None:
        """
        增强的符号链接安全检查
        
        Args:
            original_path: 原始路径
            resolved_path: 解析后的路径
            
        Returns:
            错误消息，如果安全则返回 None
        """
        try:
            current = original_path
            components = []
            
            while current != current.parent:
                components.insert(0, current)
                current = current.parent
            
            for component in components:
                if component.exists() and component.is_symlink():
                    if not self.config.allow_symlinks:
                        return f"路径包含符号链接: {component}"
                    
                    try:
                        link_target = component.readlink()
                        if str(link_target).startswith(('/', '\\')) or (
                            len(str(link_target)) >= 2 and str(link_target)[1] == ':'
                        ):
                            return f"符号链接指向绝对路径: {link_target}"
                        
                        resolved_target = Path(os.path.realpath(str(component)))
                        
                        for allowed in self._allowed_paths:
                            try:
                                if not self._is_subpath(resolved_target, allowed):
                                    return f"符号链接目标不在允许目录中: {resolved_target}"
                            except Exception:
                                pass
                    except Exception as e:
                        return f"符号链接检查失败: {e}"
            
            try:
                original_real = Path(os.path.realpath(str(original_path))) if original_path.exists() else resolved_path
                if original_real != resolved_path:
                    return "路径解析不一致，可能存在符号链接攻击"
            except Exception:
                pass
            
            symlink_depth = self._count_symlink_depth(original_path)
            if symlink_depth > self.config.max_symlink_depth:
                return f"符号链接深度超过限制 ({symlink_depth} > {self.config.max_symlink_depth})"
            
            return None
            
        except Exception as e:
            return f"符号链接检查失败: {e}"
    
    def _validate_path_components(self, path: Path) -> None:
        """
        验证路径的所有组件
        
        确保路径的每个部分都是有效的
        
        Args:
            path: 要验证的路径
        """
        current = path
        while current != current.parent:
            if current.exists():
                if current.is_symlink() and not self.config.allow_symlinks:
                    raise ValueError(f"路径组件是符号链接: {current}")
            current = current.parent
    
    def _count_symlink_depth(self, path: Path, max_depth: int = 10) -> int:
        """
        计算符号链接深度
        
        Args:
            path: 路径
            max_depth: 最大检查深度
            
        Returns:
            符号链接深度
        """
        depth = 0
        current = path
        
        while depth < max_depth:
            try:
                if current.is_symlink():
                    depth += 1
                    current = current.readlink()
                    if not current.is_absolute():
                        current = path.parent / current
                else:
                    break
            except Exception:
                break
        
        return depth
    
    def _is_subpath(self, path: Path, parent: Path) -> bool:
        """
        检查路径是否是父路径的子路径
        
        Args:
            path: 要检查的路径
            parent: 父路径
            
        Returns:
            是否是子路径
        """
        try:
            path.resolve(strict=False).relative_to(parent.resolve(strict=False))
            return True
        except ValueError:
            return False


_path_validator: PathSecurityValidator | None = None


def get_path_validator() -> PathSecurityValidator:
    """
    获取全局路径验证器实例
    
    Returns:
        PathSecurityValidator 实例
    """
    global _path_validator
    if _path_validator is None:
        _path_validator = PathSecurityValidator()
    return _path_validator


def set_path_validator(validator: PathSecurityValidator) -> None:
    """
    设置全局路径验证器实例
    
    Args:
        validator: PathSecurityValidator 实例
    """
    global _path_validator
    _path_validator = validator


@tool
class ReadFileTool(BaseTool):
    """Read file content"""
    
    name = "read_file"
    description = "Read the content of a specified file, supports line range"
    category = ToolCategory.FILE
    parameters = [
        ToolParameter(
            name="file_path",
            type="string",
            description="File path to read (absolute path)",
            required=True,
        ),
        ToolParameter(
            name="offset",
            type="integer",
            description="Starting line number (from 1)",
            required=False,
            default=1,
        ),
        ToolParameter(
            name="limit",
            type="integer",
            description="Maximum number of lines to read",
            required=False,
            default=2000,
        ),
    ]
    
    async def execute(
        self,
        file_path: str,
        offset: int = 1,
        limit: int = 2000,
        **kwargs: Any,
    ) -> ToolResult:
        """执行文件读取"""
        try:
            path_validator = get_path_validator()
            is_valid, error_msg, resolved_path = path_validator.validate_path(
                file_path, operation="read"
            )
            
            if not is_valid:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"路径安全验证失败: {error_msg}",
                )
            
            path = resolved_path
            
            if not path.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"文件不存在: {file_path}",
                )
            
            if not path.is_file():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"路径不是文件: {file_path}",
                )
            
            file_size = path.stat().st_size
            max_size = getattr(self.config, "max_file_size", 10 * 1024 * 1024)
            if file_size > max_size:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"文件过大 ({file_size} 字节)，最大允许 {max_size} 字节",
                )
            
            async with aiofiles.open(path, "rb") as f:
                raw_data = await f.read()
            
            content, detected_encoding = decode_bytes(raw_data)
            lines = content.splitlines(keepends=True)
            
            start = max(0, offset - 1)
            end = min(len(lines), start + limit)
            selected_lines = lines[start:end]
            
            output_lines = []
            max_line_num = end
            line_num_width = len(str(max_line_num))
            
            for i, line in enumerate(selected_lines, start=offset):
                line_content = line.rstrip("\n\r")
                output_lines.append(f"{i:>{line_num_width}}→{line_content}")
            
            output = "\n".join(output_lines)
            
            if len(lines) > end:
                output += f"\n\n... 已截断，文件共 {len(lines)} 行"
            
            encoding_info = f"\n\n[编码: {detected_encoding}]"
            
            return ToolResult(
                success=True,
                output=output + encoding_info,
                data={
                    "total_lines": len(lines),
                    "read_lines": len(selected_lines),
                    "start_line": offset,
                    "end_line": end,
                    "encoding": detected_encoding,
                    "file_size": file_size,
                },
            )
            
        except UnicodeDecodeError:
            return ToolResult(
                success=False,
                output="",
                error="文件编码不支持，请确认是文本文件",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=_safe_error_message("读取文件", e),
            )


@tool
class WriteFileTool(BaseTool):
    """Write file content"""
    
    name = "write_file"
    description = "Create a new file or overwrite existing file content"
    category = ToolCategory.FILE
    dangerous = True
    parameters = [
        ToolParameter(
            name="file_path",
            type="string",
            description="File path to write (absolute path)",
            required=True,
        ),
        ToolParameter(
            name="content",
            type="string",
            description="Content to write to the file",
            required=True,
        ),
    ]
    
    async def execute(
        self,
        file_path: str,
        content: str,
        **kwargs: Any,
    ) -> ToolResult:
        """执行文件写入（带完整性验证）"""
        try:
            path_validator = get_path_validator()
            is_valid, error_msg, resolved_path = path_validator.validate_path(
                file_path, operation="write"
            )
            
            if not is_valid:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"路径安全验证失败: {error_msg}",
                )
            
            path = resolved_path
            
            if path.exists() and path.is_dir():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"路径是目录，无法写入: {file_path}",
                )
            
            path.parent.mkdir(parents=True, exist_ok=True)
            
            expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            
            async with aiofiles.open(path, "w", encoding="utf-8") as f:
                await f.write(content)
            
            verification_passed = False
            verification_error = None
            
            try:
                async with aiofiles.open(path, "r", encoding="utf-8") as f:
                    written_content = await f.read()
                
                written_hash = hashlib.sha256(written_content.encode("utf-8")).hexdigest()
                
                if written_hash == expected_hash:
                    verification_passed = True
                else:
                    verification_error = "文件哈希不匹配，写入可能不完整"
                    logger.error(f"文件完整性验证失败: {file_path}")
                
                if written_content != content:
                    verification_passed = False
                    verification_error = "文件内容不匹配，写入可能损坏"
                    logger.error(f"文件内容验证失败: {file_path}")
                    
            except Exception as verify_error:
                verification_error = f"验证失败: {verify_error}"
                logger.error(f"文件验证异常: {file_path} - {verify_error}")
            
            try:
                os.chmod(path, 0o644)
            except Exception:
                pass
            
            if verification_passed:
                logger.info(f"文件写入成功并验证通过: {file_path}")
                return ToolResult(
                    success=True,
                    output=f"文件已写入并验证: {file_path}",
                    data={
                        "file_path": str(path),
                        "size": len(content),
                        "lines": content.count("\n") + 1,
                        "hash": expected_hash[:16],
                        "verified": True,
                    },
                )
            else:
                logger.warning(f"文件写入成功但验证失败: {file_path}")
                return ToolResult(
                    success=True,
                    output=f"文件已写入但验证失败: {file_path}\n警告: {verification_error}",
                    data={
                        "file_path": str(path),
                        "size": len(content),
                        "lines": content.count("\n") + 1,
                        "hash": expected_hash[:16],
                        "verified": False,
                        "verification_error": verification_error,
                    },
                )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=_safe_error_message("写入文件", e),
            )


@tool
class EditFileTool(BaseTool):
    """Edit file content"""
    
    name = "edit_file"
    description = "Search and replace text content in a file"
    category = ToolCategory.FILE
    dangerous = True
    parameters = [
        ToolParameter(
            name="file_path",
            type="string",
            description="File path to edit (absolute path)",
            required=True,
        ),
        ToolParameter(
            name="old_text",
            type="string",
            description="Text to search for (must match exactly)",
            required=True,
        ),
        ToolParameter(
            name="new_text",
            type="string",
            description="Text to replace with",
            required=True,
        ),
    ]
    
    async def execute(
        self,
        file_path: str,
        old_text: str,
        new_text: str,
        **kwargs: Any,
    ) -> ToolResult:
        """执行文件编辑"""
        try:
            path_validator = get_path_validator()
            is_valid, error_msg, resolved_path = path_validator.validate_path(
                file_path, operation="write"
            )
            
            if not is_valid:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"路径安全验证失败: {error_msg}",
                )
            
            path = resolved_path
            
            if not path.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"文件不存在: {file_path}",
                )
            
            async with aiofiles.open(path, "rb") as f:
                raw_data = await f.read()
            
            content, detected_encoding = decode_bytes(raw_data)
            
            if old_text not in content:
                return ToolResult(
                    success=False,
                    output="",
                    error="未找到要替换的文本",
                )
            
            occurrences = content.count(old_text)
            if occurrences > 1:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"找到 {occurrences} 处匹配，请提供更具体的文本以唯一标识",
                )
            
            new_content = content.replace(old_text, new_text, 1)
            
            try:
                async with aiofiles.open(path, "w", encoding=detected_encoding) as f:
                    await f.write(new_content)
            except (UnicodeEncodeError, LookupError):
                async with aiofiles.open(path, "w", encoding="utf-8") as f:
                    await f.write(new_content)
                detected_encoding = "utf-8"
            
            logger.info(f"文件编辑成功: {file_path}")
            
            return ToolResult(
                success=True,
                output=f"文件已编辑: {file_path}\n替换了 1 处文本\n编码: {detected_encoding}",
                data={
                    "file_path": str(path),
                    "occurrences": 1,
                    "encoding": detected_encoding,
                },
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=_safe_error_message("编辑文件", e),
            )


@tool
class ListDirectoryTool(BaseTool):
    """List directory contents"""
    
    name = "list_directory"
    description = "List files and subdirectories in a specified directory"
    category = ToolCategory.FILE
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="Directory path to list (absolute path)",
            required=True,
        ),
        ToolParameter(
            name="recursive",
            type="boolean",
            description="Whether to recursively list subdirectories",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="pattern",
            type="string",
            description="File name matching pattern (glob format)",
            required=False,
            default="*",
        ),
    ]
    
    async def execute(
        self,
        path: str,
        recursive: bool = False,
        pattern: str = "*",
        **kwargs: Any,
    ) -> ToolResult:
        """执行目录列出"""
        try:
            dir_path = Path(path)
            
            if not dir_path.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"目录不存在: {path}",
                )
            
            if not dir_path.is_dir():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"路径不是目录: {path}",
                )
            
            items = []
            
            if recursive:
                for item in dir_path.rglob(pattern):
                    rel_path = item.relative_to(dir_path)
                    if item.is_dir():
                        items.append(f"📁 {rel_path}/")
                    else:
                        size = item.stat().st_size
                        items.append(f"📄 {rel_path} ({self._format_size(size)})")
            else:
                for item in sorted(dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
                    if not fnmatch.fnmatch(item.name, pattern):
                        continue
                    
                    if item.is_dir():
                        items.append(f"📁 {item.name}/")
                    else:
                        size = item.stat().st_size
                        items.append(f"📄 {item.name} ({self._format_size(size)})")
            
            output = f"目录: {path}\n\n"
            output += "\n".join(items) if items else "(空目录)"
            
            return ToolResult(
                success=True,
                output=output,
                data={
                    "path": str(dir_path),
                    "item_count": len(items),
                    "recursive": recursive,
                },
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=_safe_error_message("列出目录", e),
            )
    
    @staticmethod
    def _format_size(size: int) -> str:
        """格式化文件大小"""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"


@tool
class SearchInFileTool(BaseTool):
    """Search in file"""
    
    name = "search_in_file"
    description = "Search for text or regex patterns in file content"
    category = ToolCategory.SEARCH
    parameters = [
        ToolParameter(
            name="file_path",
            type="string",
            description="File path to search (absolute path)",
            required=True,
        ),
        ToolParameter(
            name="pattern",
            type="string",
            description="Search pattern (supports regex)",
            required=True,
        ),
        ToolParameter(
            name="context_lines",
            type="integer",
            description="Number of context lines to show around matches",
            required=False,
            default=2,
        ),
    ]
    
    async def execute(
        self,
        file_path: str,
        pattern: str,
        context_lines: int = 2,
        **kwargs: Any,
    ) -> ToolResult:
        """执行文件搜索"""
        import re
        
        try:
            path = Path(file_path)
            
            if not path.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"文件不存在: {file_path}",
                )
            
            # 读取文件（二进制模式）
            async with aiofiles.open(path, "rb") as f:
                raw_data = await f.read()
            
            # 智能检测编码并解码
            content, detected_encoding = decode_bytes(raw_data)
            lines = content.splitlines(keepends=True)
            
            # 编译正则表达式
            try:
                regex = re.compile(pattern)
            except re.error as e:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"无效的正则表达式: {e}",
                )
            
            # 搜索匹配
            matches = []
            for i, line in enumerate(lines):
                if regex.search(line):
                    matches.append(i)
            
            if not matches:
                return ToolResult(
                    success=True,
                    output=f"在文件中未找到匹配: {pattern}\n[编码: {detected_encoding}]",
                    data={"match_count": 0, "encoding": detected_encoding},
                )
            
            # 格式化输出
            output_lines = []
            shown_ranges = set()
            
            for match_line in matches:
                start = max(0, match_line - context_lines)
                end = min(len(lines), match_line + context_lines + 1)
                
                for i in range(start, end):
                    if i not in shown_ranges:
                        shown_ranges.add(i)
                        line_num = i + 1
                        line_content = lines[i].rstrip("\n\r")
                        prefix = ">>>" if i == match_line else "   "
                        output_lines.append(f"{prefix} {line_num:4d}→{line_content}")
            
            output = f"文件: {file_path}\n"
            output += f"找到 {len(matches)} 处匹配\n"
            output += f"编码: {detected_encoding}\n\n"
            output += "\n".join(output_lines)
            
            return ToolResult(
                success=True,
                output=output,
                data={
                    "file_path": str(path),
                    "pattern": pattern,
                    "match_count": len(matches),
                    "match_lines": [m + 1 for m in matches],
                    "encoding": detected_encoding,
                },
            )
            
        except Exception as e:
            logger.error(f"搜索文件失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=str(e),
            )


@tool
class DeleteFileTool(BaseTool):
    """Delete file"""
    
    name = "delete_file"
    description = "Delete a specified file or directory"
    category = ToolCategory.FILE
    dangerous = True
    parameters = [
        ToolParameter(
            name="file_path",
            type="string",
            description="File or directory path to delete (absolute path)",
            required=True,
        ),
        ToolParameter(
            name="recursive",
            type="boolean",
            description="Whether to recursively delete directory",
            required=False,
            default=False,
        ),
    ]
    
    async def execute(
        self,
        file_path: str,
        recursive: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        """执行文件删除"""
        try:
            path_validator = get_path_validator()
            is_valid, error_msg, resolved_path = path_validator.validate_path(
                file_path, operation="delete"
            )
            
            if not is_valid:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"路径安全验证失败: {error_msg}",
                )
            
            path = resolved_path
            
            if not path.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"路径不存在: {file_path}",
                )
            
            if path.is_file():
                path.unlink()
                logger.info(f"文件已删除: {file_path}")
                return ToolResult(
                    success=True,
                    output=f"文件已删除: {file_path}",
                )
            
            if path.is_dir():
                if not recursive and any(path.iterdir()):
                    return ToolResult(
                        success=False,
                        output="",
                        error="目录不为空，请使用 recursive=true 递归删除",
                    )
                
                shutil.rmtree(path)
                logger.info(f"目录已删除: {file_path}")
                return ToolResult(
                    success=True,
                    output=f"目录已删除: {file_path}",
                )
            
            return ToolResult(
                success=False,
                output="",
                error="未知路径类型",
            )
            
        except Exception as e:
            logger.error(f"删除失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=str(e),
            )


@tool
class GlobTool(BaseTool):
    """File pattern matching"""
    
    name = "glob"
    description = "Find files using glob pattern"
    category = ToolCategory.SEARCH
    parameters = [
        ToolParameter(
            name="pattern",
            type="string",
            description="Glob matching pattern (e.g. **/*.py)",
            required=True,
        ),
        ToolParameter(
            name="path",
            type="string",
            description="Root directory to search",
            required=False,
            default=".",
        ),
    ]
    
    async def execute(
        self,
        pattern: str,
        path: str = ".",
        **kwargs: Any,
    ) -> ToolResult:
        """执行 glob 搜索"""
        try:
            base_path = Path(path).resolve()
            
            if not base_path.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"目录不存在: {path}",
                )
            
            # 执行 glob
            matches = list(base_path.glob(pattern))
            
            # 排序（按修改时间）
            matches.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # 格式化输出
            output_lines = [f"模式: {pattern}", f"目录: {base_path}", ""]
            
            for match in matches[:100]:  # 限制输出数量
                rel_path = match.relative_to(base_path)
                if match.is_dir():
                    output_lines.append(f"📁 {rel_path}/")
                else:
                    output_lines.append(f"📄 {rel_path}")
            
            if len(matches) > 100:
                output_lines.append(f"\n... 共 {len(matches)} 个结果，仅显示前 100 个")
            
            return ToolResult(
                success=True,
                output="\n".join(output_lines),
                data={
                    "pattern": pattern,
                    "path": str(base_path),
                    "match_count": len(matches),
                    "matches": [str(m.relative_to(base_path)) for m in matches],
                },
            )
            
        except Exception as e:
            logger.error(f"Glob 搜索失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=str(e),
            )
