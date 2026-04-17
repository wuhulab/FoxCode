"""
FoxCode 智能错误分析器

提供错误堆栈解析、根因定位和修复建议功能。
支持多种编程语言的错误分析。

主要功能：
- 错误堆栈解析和根因定位
- 错误模式匹配和分类
- 自动修复建议生成
- 错误预防性检测
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ErrorSeverity(str, Enum):
    """错误严重程度"""
    CRITICAL = "critical"    # 严重错误，程序无法继续
    HIGH = "high"           # 高严重度，主要功能受影响
    MEDIUM = "medium"       # 中等严重度，部分功能受影响
    LOW = "low"             # 低严重度，小问题
    WARNING = "warning"     # 警告，不影响功能


class ErrorCategory(str, Enum):
    """错误类别"""
    SYNTAX = "syntax"               # 语法错误
    RUNTIME = "runtime"             # 运行时错误
    LOGIC = "logic"                 # 逻辑错误
    TYPE = "type"                   # 类型错误
    IMPORT = "import"               # 导入错误
    ATTRIBUTE = "attribute"         # 属性错误
    INDEX = "index"                 # 索引错误
    KEY = "key"                     # 键错误
    VALUE = "value"                 # 值错误
    NAME = "name"                   # 名称错误
    IO = "io"                       # IO 错误
    NETWORK = "network"             # 网络错误
    DATABASE = "database"           # 数据库错误
    AUTH = "auth"                   # 认证错误
    CONFIGURATION = "configuration"  # 配置错误
    DEPENDENCY = "dependency"       # 依赖错误
    UNKNOWN = "unknown"             # 未知错误


@dataclass
class StackFrame:
    """
    堆栈帧
    
    Attributes:
        file_path: 文件路径
        line_number: 行号
        function_name: 函数名
        module_name: 模块名
        code_line: 代码行内容
        locals: 局部变量（可选）
    """
    file_path: str
    line_number: int
    function_name: str
    module_name: str = ""
    code_line: str = ""
    locals: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "line_number": self.line_number,
            "function_name": self.function_name,
            "module_name": self.module_name,
            "code_line": self.code_line,
            "locals": self.locals,
        }


@dataclass
class ErrorReport:
    """
    错误报告
    
    Attributes:
        error_type: 错误类型
        error_message: 错误消息
        category: 错误类别
        severity: 严重程度
        stack_trace: 堆栈跟踪
        root_cause: 根因分析
        file_path: 出错文件路径
        line_number: 出错行号
        context: 上下文代码
        timestamp: 时间戳
        metadata: 元数据
    """
    error_type: str
    error_message: str
    category: ErrorCategory = ErrorCategory.UNKNOWN
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    stack_trace: list[StackFrame] = field(default_factory=list)
    root_cause: str = ""
    file_path: str = ""
    line_number: int = 0
    context: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_type": self.error_type,
            "error_message": self.error_message,
            "category": self.category.value,
            "severity": self.severity.value,
            "stack_trace": [f.to_dict() for f in self.stack_trace],
            "root_cause": self.root_cause,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class ErrorClassification:
    """
    错误分类
    
    Attributes:
        category: 错误类别
        severity: 严重程度
        is_recoverable: 是否可恢复
        common_causes: 常见原因
        related_patterns: 相关模式
    """
    category: ErrorCategory
    severity: ErrorSeverity
    is_recoverable: bool = True
    common_causes: list[str] = field(default_factory=list)
    related_patterns: list[str] = field(default_factory=list)


@dataclass
class FixSuggestion:
    """
    修复建议
    
    Attributes:
        title: 建议标题
        description: 建议描述
        code_fix: 代码修复（可选）
        confidence: 置信度
        priority: 优先级
        references: 参考链接
    """
    title: str
    description: str
    code_fix: str = ""
    confidence: float = 0.7
    priority: int = 1
    references: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "code_fix": self.code_fix,
            "confidence": self.confidence,
            "priority": self.priority,
            "references": self.references,
        }


@dataclass
class PotentialError:
    """
    潜在错误
    
    Attributes:
        file_path: 文件路径
        line_number: 行号
        error_type: 预测的错误类型
        description: 描述
        severity: 严重程度
        code_snippet: 代码片段
        suggestion: 建议修复
    """
    file_path: str
    line_number: int
    error_type: str
    description: str
    severity: ErrorSeverity = ErrorSeverity.WARNING
    code_snippet: str = ""
    suggestion: str = ""


class ErrorAnalyzerConfig(BaseModel):
    """
    错误分析器配置
    
    Attributes:
        max_stack_frames: 最大堆栈帧数
        enable_prevention: 是否启用预防性检测
        supported_languages: 支持的语言列表
        auto_fix_enabled: 是否启用自动修复
    """
    max_stack_frames: int = Field(default=50, ge=1)
    enable_prevention: bool = True
    supported_languages: list[str] = Field(
        default_factory=lambda: ["python", "javascript", "typescript", "java", "go"]
    )
    auto_fix_enabled: bool = False


class ErrorAnalyzer:
    """
    智能错误分析器
    
    提供错误堆栈解析、根因定位和修复建议功能。
    
    Example:
        >>> analyzer = ErrorAnalyzer()
        >>> report = analyzer.analyze_traceback(traceback_str)
        >>> suggestions = analyzer.suggest_fix(report, code_context)
    """

    # Python 错误类型到类别的映射
    PYTHON_ERROR_CATEGORIES = {
        "SyntaxError": ErrorCategory.SYNTAX,
        "IndentationError": ErrorCategory.SYNTAX,
        "TabError": ErrorCategory.SYNTAX,
        "TypeError": ErrorCategory.TYPE,
        "ValueError": ErrorCategory.VALUE,
        "KeyError": ErrorCategory.KEY,
        "IndexError": ErrorCategory.INDEX,
        "AttributeError": ErrorCategory.ATTRIBUTE,
        "NameError": ErrorCategory.NAME,
        "ImportError": ErrorCategory.IMPORT,
        "ModuleNotFoundError": ErrorCategory.IMPORT,
        "FileNotFoundError": ErrorCategory.IO,
        "PermissionError": ErrorCategory.IO,
        "IOError": ErrorCategory.IO,
        "OSError": ErrorCategory.IO,
        "ConnectionError": ErrorCategory.NETWORK,
        "TimeoutError": ErrorCategory.NETWORK,
        "RuntimeError": ErrorCategory.RUNTIME,
        "RecursionError": ErrorCategory.RUNTIME,
        "StopIteration": ErrorCategory.RUNTIME,
        "ZeroDivisionError": ErrorCategory.LOGIC,
        "OverflowError": ErrorCategory.LOGIC,
        "AssertionError": ErrorCategory.LOGIC,
        "NotImplementedError": ErrorCategory.LOGIC,
    }

    # 错误类型到严重程度的映射
    ERROR_SEVERITY_MAP = {
        "SyntaxError": ErrorSeverity.CRITICAL,
        "IndentationError": ErrorSeverity.CRITICAL,
        "ImportError": ErrorSeverity.HIGH,
        "ModuleNotFoundError": ErrorSeverity.HIGH,
        "TypeError": ErrorSeverity.HIGH,
        "AttributeError": ErrorSeverity.HIGH,
        "NameError": ErrorSeverity.HIGH,
        "KeyError": ErrorSeverity.MEDIUM,
        "IndexError": ErrorSeverity.MEDIUM,
        "ValueError": ErrorSeverity.MEDIUM,
        "FileNotFoundError": ErrorSeverity.MEDIUM,
        "PermissionError": ErrorSeverity.HIGH,
        "ConnectionError": ErrorSeverity.MEDIUM,
        "RuntimeError": ErrorSeverity.HIGH,
        "RecursionError": ErrorSeverity.HIGH,
        "ZeroDivisionError": ErrorSeverity.MEDIUM,
        "AssertionError": ErrorSeverity.MEDIUM,
        "Warning": ErrorSeverity.WARNING,
    }

    # 常见错误模式及其修复建议
    ERROR_FIXES = {
        "NameError": {
            "patterns": [
                (r"name '(\w+)' is not defined", "变量 '{var}' 未定义"),
            ],
            "fixes": [
                "检查变量是否已定义",
                "检查变量名拼写是否正确",
                "检查是否需要导入相关模块",
                "检查变量作用域",
            ],
        },
        "TypeError": {
            "patterns": [
                (r"'(\w+)' object is not callable", "'{var}' 对象不可调用"),
                (r"'(\w+)' object is not subscriptable", "'{var}' 对象不支持索引访问"),
                (r"unsupported operand type\(s\)", "不支持的操作类型"),
                (r"missing \d+ required positional argument", "缺少必需的位置参数"),
            ],
            "fixes": [
                "检查对象类型是否正确",
                "检查是否使用了错误的方法或操作符",
                "检查函数参数是否完整",
                "检查类型转换是否正确",
            ],
        },
        "AttributeError": {
            "patterns": [
                (r"'(\w+)' object has no attribute '(\w+)'", "'{var1}' 对象没有属性 '{var2}'"),
            ],
            "fixes": [
                "检查对象是否有该属性",
                "检查属性名拼写是否正确",
                "检查是否需要先初始化对象",
                "检查是否使用了正确的对象类型",
            ],
        },
        "KeyError": {
            "patterns": [
                (r"KeyError: '?(\w+)'?", "键 '{var}' 不存在"),
            ],
            "fixes": [
                "检查键是否存在",
                "使用 .get() 方法安全获取值",
                "检查键名拼写是否正确",
                "检查数据结构是否正确",
            ],
        },
        "IndexError": {
            "patterns": [
                (r"list index out of range", "列表索引超出范围"),
                (r"tuple index out of range", "元组索引超出范围"),
                (r"string index out of range", "字符串索引超出范围"),
            ],
            "fixes": [
                "检查索引是否在有效范围内",
                "检查列表/元组/字符串长度",
                "使用负索引或切片避免越界",
                "添加边界检查",
            ],
        },
        "ImportError": {
            "patterns": [
                (r"cannot import name '(\w+)' from '(\w+)'", "无法从 '{var2}' 导入 '{var1}'"),
                (r"No module named '(\w+)'", "模块 '{var}' 不存在"),
            ],
            "fixes": [
                "检查模块是否已安装",
                "检查模块名拼写是否正确",
                "使用 pip install 安装缺失的模块",
                "检查 Python 环境是否正确",
            ],
        },
        "FileNotFoundError": {
            "patterns": [
                (r"No such file or directory: '([^']+)'", "文件或目录不存在: '{var}'"),
            ],
            "fixes": [
                "检查文件路径是否正确",
                "检查文件是否存在",
                "使用绝对路径或正确的相对路径",
                "检查工作目录是否正确",
            ],
        },
        "SyntaxError": {
            "patterns": [
                (r"invalid syntax", "语法错误"),
                (r"unexpected EOF while parsing", "代码不完整"),
                (r"EOL while scanning string literal", "字符串未闭合"),
            ],
            "fixes": [
                "检查语法是否正确",
                "检查括号、引号是否匹配",
                "检查缩进是否正确",
                "检查是否有遗漏的符号",
            ],
        },
    }

    # 预防性检测规则
    PREVENTION_RULES = {
        "python": [
            {
                "pattern": r"except\s*:",
                "error": "Bare except",
                "description": "使用裸 except 会捕获所有异常，包括系统退出",
                "suggestion": "使用 except Exception as e: 或更具体的异常类型",
            },
            {
                "pattern": r"except\s+Exception\s*:",
                "error": "Broad exception",
                "description": "捕获过于宽泛的异常类型",
                "suggestion": "考虑捕获更具体的异常类型",
            },
            {
                "pattern": r"print\s*\(",
                "error": "Print statement",
                "description": "使用 print 进行调试输出",
                "suggestion": "考虑使用 logging 模块",
            },
            {
                "pattern": r"==\s*None",
                "error": "None comparison",
                "description": "使用 == 比较 None",
                "suggestion": "使用 is None 进行 None 比较",
            },
            {
                "pattern": r"!=\s*None",
                "error": "None comparison",
                "description": "使用 != 比较 None",
                "suggestion": "使用 is not None 进行 None 比较",
            },
            {
                "pattern": r"from\s+\w+\s+import\s+\*",
                "error": "Star import",
                "description": "使用星号导入会污染命名空间",
                "suggestion": "显式导入需要的名称",
            },
            {
                "pattern": r"eval\s*\(",
                "error": "Eval usage",
                "description": "使用 eval 存在安全风险",
                "suggestion": "避免使用 eval，考虑 ast.literal_eval",
            },
            {
                "pattern": r"exec\s*\(",
                "error": "Exec usage",
                "description": "使用 exec 存在安全风险",
                "suggestion": "避免使用 exec",
            },
        ],
    }

    def __init__(self, config: ErrorAnalyzerConfig | None = None):
        """
        初始化错误分析器
        
        Args:
            config: 分析器配置
        """
        self.config = config or ErrorAnalyzerConfig()
        logger.info("智能错误分析器初始化完成")

    def analyze_traceback(self, traceback_str: str) -> ErrorReport:
        """
        分析错误堆栈
        
        Args:
            traceback_str: 错误堆栈字符串
            
        Returns:
            错误报告
        """
        # 解析错误类型和消息
        error_type, error_message = self._parse_error_header(traceback_str)

        # 解析堆栈帧
        stack_frames = self._parse_stack_frames(traceback_str)

        # 分类错误
        category = self._categorize_error(error_type)
        severity = self._assess_severity(error_type, error_message)

        # 定位根因
        root_cause, file_path, line_number = self._locate_root_cause(
            stack_frames, error_type, error_message
        )

        # 获取上下文
        context = self._get_context(file_path, line_number) if file_path else ""

        return ErrorReport(
            error_type=error_type,
            error_message=error_message,
            category=category,
            severity=severity,
            stack_trace=stack_frames[:self.config.max_stack_frames],
            root_cause=root_cause,
            file_path=file_path,
            line_number=line_number,
            context=context,
            metadata={
                "traceback_length": len(traceback_str),
                "stack_depth": len(stack_frames),
            }
        )

    def _parse_error_header(self, traceback_str: str) -> tuple[str, str]:
        """解析错误类型和消息"""
        lines = traceback_str.strip().split("\n")

        # 最后一行通常包含错误类型和消息
        for line in reversed(lines):
            line = line.strip()
            if ":" in line and not line.startswith(" "):
                # 格式: ErrorType: error message
                parts = line.split(":", 1)
                if len(parts) == 2:
                    error_type = parts[0].strip()
                    error_message = parts[1].strip()
                    return error_type, error_message

        return "UnknownError", traceback_str[:200]

    def _parse_stack_frames(self, traceback_str: str) -> list[StackFrame]:
        """解析堆栈帧"""
        frames = []

        # Python 堆栈帧格式:
        # File "path/to/file.py", line X, in function_name
        #     code_line

        pattern = r'File "([^"]+)", line (\d+), in (\w+)'

        lines = traceback_str.split("\n")
        i = 0

        while i < len(lines):
            match = re.search(pattern, lines[i])
            if match:
                file_path = match.group(1)
                line_number = int(match.group(2))
                function_name = match.group(3)

                # 获取下一行的代码
                code_line = ""
                if i + 1 < len(lines):
                    code_line = lines[i + 1].strip()

                frames.append(StackFrame(
                    file_path=file_path,
                    line_number=line_number,
                    function_name=function_name,
                    code_line=code_line,
                ))

            i += 1

        return frames

    def _categorize_error(self, error_type: str) -> ErrorCategory:
        """分类错误"""
        return self.PYTHON_ERROR_CATEGORIES.get(error_type, ErrorCategory.UNKNOWN)

    def _assess_severity(self, error_type: str, error_message: str) -> ErrorSeverity:
        """评估错误严重程度"""
        severity = self.ERROR_SEVERITY_MAP.get(error_type, ErrorSeverity.MEDIUM)

        # 根据消息内容调整严重程度
        critical_keywords = ["security", "authentication", "permission", "critical"]
        for keyword in critical_keywords:
            if keyword in error_message.lower():
                return ErrorSeverity.CRITICAL

        return severity

    def _locate_root_cause(
        self,
        stack_frames: list[StackFrame],
        error_type: str,
        error_message: str,
    ) -> tuple[str, str, int]:
        """
        定位根因
        
        Returns:
            (根因描述, 文件路径, 行号)
        """
        if not stack_frames:
            return error_message, "", 0

        # 通常第一个用户代码帧是根因位置
        for frame in stack_frames:
            # 跳过标准库和第三方库
            if not any(skip in frame.file_path for skip in [
                "/lib/", "/site-packages/", "<", "built-in"
            ]):
                root_cause = f"在 {frame.file_path}:{frame.line_number} 的 {frame.function_name} 函数中发生错误"
                return root_cause, frame.file_path, frame.line_number

        # 如果没有找到用户代码，返回第一个帧
        frame = stack_frames[0]
        return f"在 {frame.file_path}:{frame.line_number} 发生错误", frame.file_path, frame.line_number

    def _get_context(self, file_path: str, line_number: int, context_lines: int = 5) -> str:
        """获取代码上下文"""
        try:
            path = Path(file_path)
            if not path.exists():
                return ""

            with open(path, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            start = max(0, line_number - context_lines - 1)
            end = min(len(lines), line_number + context_lines)

            context_parts = []
            for i in range(start, end):
                prefix = ">>> " if i == line_number - 1 else "    "
                context_parts.append(f"{prefix}{i + 1}: {lines[i].rstrip()}")

            return "\n".join(context_parts)

        except Exception as e:
            logger.debug(f"获取上下文失败: {e}")
            return ""

    def classify_error(self, error: Exception) -> ErrorClassification:
        """
        分类错误
        
        Args:
            error: 异常对象
            
        Returns:
            错误分类
        """
        error_type = type(error).__name__
        category = self._categorize_error(error_type)
        severity = self._assess_severity(error_type, str(error))

        # 获取常见原因
        common_causes = []
        if error_type in self.ERROR_FIXES:
            common_causes = self.ERROR_FIXES[error_type].get("fixes", [])

        # 判断是否可恢复
        is_recoverable = severity not in (ErrorSeverity.CRITICAL,)

        return ErrorClassification(
            category=category,
            severity=severity,
            is_recoverable=is_recoverable,
            common_causes=common_causes,
        )

    def suggest_fix(
        self,
        error_report: ErrorReport,
        code_context: str = "",
    ) -> list[FixSuggestion]:
        """
        生成修复建议
        
        Args:
            error_report: 错误报告
            code_context: 代码上下文
            
        Returns:
            修复建议列表
        """
        suggestions = []
        error_type = error_report.error_type
        error_message = error_report.error_message

        # 基于错误类型获取修复建议
        if error_type in self.ERROR_FIXES:
            fix_info = self.ERROR_FIXES[error_type]

            # 匹配错误模式
            for pattern, desc_template in fix_info.get("patterns", []):
                match = re.search(pattern, error_message)
                if match:
                    # 生成具体描述
                    description = desc_template
                    if match.groups():
                        for i, group in enumerate(match.groups()):
                            description = description.replace(f"{{var{i+1}}}", group)
                            description = description.replace("{var}", group)

                    suggestions.append(FixSuggestion(
                        title=f"修复 {error_type}",
                        description=description,
                        confidence=0.8,
                        priority=1,
                    ))
                    break

            # 添加通用修复建议
            for i, fix in enumerate(fix_info.get("fixes", [])):
                suggestions.append(FixSuggestion(
                    title=f"建议: {fix}",
                    description=fix,
                    confidence=0.6,
                    priority=i + 2,
                ))

        # 如果有代码上下文，尝试生成代码修复
        if code_context and error_report.file_path and error_report.line_number:
            code_fix = self._generate_code_fix(error_report, code_context)
            if code_fix:
                suggestions.insert(0, FixSuggestion(
                    title="自动生成的修复代码",
                    description="基于错误分析生成的修复建议",
                    code_fix=code_fix,
                    confidence=0.5,
                    priority=0,
                ))

        return suggestions

    def _generate_code_fix(
        self,
        error_report: ErrorReport,
        code_context: str,
    ) -> str:
        """生成代码修复"""
        error_type = error_report.error_type

        # 基于错误类型生成修复
        if error_type == "KeyError":
            # 提取键名
            match = re.search(r"KeyError: '?(\w+)'?", error_report.error_message)
            if match:
                key = match.group(1)
                return f"# 使用 .get() 方法安全获取值\nvalue = dict.get('{key}', default_value)"

        elif error_type == "AttributeError":
            match = re.search(r"'(\w+)' object has no attribute '(\w+)'", error_report.error_message)
            if match:
                obj_type, attr = match.groups()
                return f"# 检查属性是否存在\nif hasattr(obj, '{attr}'):\n    obj.{attr}()\nelse:\n    # 处理属性不存在的情况\n    pass"

        elif error_type == "IndexError":
            return "# 添加边界检查\nif 0 <= index < len(lst):\n    value = lst[index]\nelse:\n    # 处理索引越界\n    pass"

        elif error_type == "TypeError":
            if "not callable" in error_report.error_message:
                return "# 检查对象是否可调用\nif callable(obj):\n    obj()\nelse:\n    # 处理不可调用的情况\n    pass"

        return ""

    def detect_potential_errors(
        self,
        code: str,
        language: str = "python",
    ) -> list[PotentialError]:
        """
        检测潜在错误
        
        Args:
            code: 代码字符串
            language: 编程语言
            
        Returns:
            潜在错误列表
        """
        if not self.config.enable_prevention:
            return []

        potential_errors = []

        # 获取检测规则
        rules = self.PREVENTION_RULES.get(language, [])

        lines = code.split("\n")
        for i, line in enumerate(lines):
            for rule in rules:
                if re.search(rule["pattern"], line):
                    potential_errors.append(PotentialError(
                        file_path="",
                        line_number=i + 1,
                        error_type=rule["error"],
                        description=rule["description"],
                        severity=ErrorSeverity.WARNING,
                        code_snippet=line.strip(),
                        suggestion=rule["suggestion"],
                    ))

        # Python 语法检查
        if language == "python":
            syntax_errors = self._check_python_syntax(code)
            potential_errors.extend(syntax_errors)

        return potential_errors

    def _check_python_syntax(self, code: str) -> list[PotentialError]:
        """检查 Python 语法"""
        errors = []

        try:
            ast.parse(code)
        except SyntaxError as e:
            errors.append(PotentialError(
                file_path="",
                line_number=e.lineno or 1,
                error_type="SyntaxError",
                description=str(e.msg),
                severity=ErrorSeverity.CRITICAL,
                code_snippet=e.text or "",
                suggestion="修复语法错误",
            ))

        return errors

    def get_error_statistics(self, errors: list[ErrorReport]) -> dict[str, Any]:
        """
        获取错误统计信息
        
        Args:
            errors: 错误报告列表
            
        Returns:
            统计信息
        """
        if not errors:
            return {"total": 0}

        # 按类别统计
        category_counts = {}
        for error in errors:
            cat = error.category.value
            category_counts[cat] = category_counts.get(cat, 0) + 1

        # 按严重程度统计
        severity_counts = {}
        for error in errors:
            sev = error.severity.value
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        # 按错误类型统计
        type_counts = {}
        for error in errors:
            type_counts[error.error_type] = type_counts.get(error.error_type, 0) + 1

        return {
            "total": len(errors),
            "by_category": category_counts,
            "by_severity": severity_counts,
            "by_type": type_counts,
            "most_common": max(type_counts.items(), key=lambda x: x[1])[0] if type_counts else None,
        }


# 创建默认分析器实例
error_analyzer = ErrorAnalyzer()
