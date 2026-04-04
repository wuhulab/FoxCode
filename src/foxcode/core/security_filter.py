"""
FoxCode 安全过滤模块

提供内容安全验证和过滤功能，包括：
- 敏感词过滤
- 正则表达式过滤
- 命令注入防护
- XSS 防护
- SQL 注入防护
- 路径穿越防护
- 速率限制

安全说明：
- 路径穿越防护使用规范化路径验证
- 正则表达式匹配有超时保护
- 所有过滤操作都有性能限制
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import secrets
import signal
import threading
import time
import urllib.parse
from asyncio import Lock
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from foxcode.core.company_mode_config import (
    ContentFilterConfig,
    SecurityConfig,
    SecurityLevel,
)

logger = logging.getLogger(__name__)


# ReDoS 防护配置
REGEX_TIMEOUT_SECONDS = 1.0  # 正则匹配超时时间（秒）
MAX_REGEX_COMPLEXITY = 1000  # 最大正则复杂度（嵌套深度）
MAX_INPUT_LENGTH = 100000    # 最大输入长度（字符）
MAX_CONCURRENT_REGEX_MATCHES = 10  # 最大并发正则匹配数量（防止资源耗尽）


class RegexTimeoutError(Exception):
    """正则匹配超时异常"""
    pass


# 全局正则匹配信号量，限制并发正则匹配数量
_regex_semaphore = threading.Semaphore(MAX_CONCURRENT_REGEX_MATCHES)


UNICODE_CONFUSABLES = {
    '.': ['\uff0e', '\u2024', '\ufe52', '\uff61', '\u002e', '\u3002', '\u02d0', '\u02d1'],
    '/': ['\uff0f', '\u2044', '\u2215', '\u29f8', '\u002f', '\u2571', '\u27cb', '\u29f6'],
    '\\': ['\uff3c', '\u2216', '\u29f5', '\u29f9', '\u005c', '\u27cd', '\u29f7', '\u29fc'],
    '-': ['\uff0d', '\u2010', '\u2011', '\u2012', '\u2013', '\u2212', '\u002d', '\u02d7', '\u02d8'],
    '<': ['\uff1c', '\u2039', '\u3008', '\u27e8', '\u300a', '\u003c'],
    '>': ['\uff1e', '\u203a', '\u3009', '\u27e9', '\u300b', '\u003e'],
    "'": ['\u2018', '\u2019', '\u201b', '\uff07', '\u02b9', '\u02bb', '\u02bd'],
    '"': ['\u201c', '\u201d', '\u201e', '\uff02', '\u02ba', '\u02dd', '\u02ee'],
    '=': ['\uff1d', '\u2261', '\u2557', '\u207c', '\u208c', '\u003d'],
    ';': ['\uff1b', '\u037e', '\u061b', '\u1363', '\u1802', '\u1803'],
    '|': ['\uff5c', '\u01c0', '\u2223', '\u2758', '\u2759', '\u275a', '\u007c'],
    '&': ['\uff06', '\u214b', '\ufe60', '\u0026'],
    ':': ['\uff1a', '\u02d0', '\u0589', '\u2236', '\u003a'],
    '@': ['\uff20', '\uFE6B', '\u0040'],
    '!': ['\uff01', '\u01C3', '\u01C5', '\u0021'],
    '?': ['\uff1f', '\u01BF', '\u0021', '\u003f'],
    '(': ['\uff08', '\u207d', '\u208d', '\u2768', '\u276a', '\u0028'],
    ')': ['\uff09', '\u207e', '\u208e', '\u2769', '\u276b', '\u0029'],
    '[': ['\uff3b', '\u27e6', '\u27e8', '\u27ea', '\u300c', '\u005b'],
    ']': ['\uff3d', '\u27e7', '\u27e9', '\u27eb', '\u300d', '\u005d'],
    '{': ['\uff5b', '\u2774', '\u2983', '\u2985', '\u007b'],
    '}': ['\uff5d', '\u2775', '\u2984', '\u2986', '\u007d'],
    '$': ['\uff04', '\uFE69', '\u0024'],
    '#': ['\uff03', '\uFE5F', '\u0023'],
    '%': ['\uff05', '\u066a', '\u0025'],
    '+': ['\uff0b', '\u29fa', '\u002b'],
    ',': ['\uff0c', '\u201a', '\u3001', '\u002c'],
    '0': ['\uff10', '\u0660', '\u06F0', '\u0030'],
    '1': ['\uff11', '\u0661', '\u06F1', '\u0031'],
    'a': ['\uff41', '\u0430', '\u03b1', '\u0061'],
    'c': ['\uff43', '\u0441', '\u0063'],
    'e': ['\uff45', '\u0435', '\u03b5', '\u0065'],
    'i': ['\uff49', '\u0456', '\u03b9', '\u0131', '\u0069'],
    'o': ['\uff4f', '\u043e', '\u03bf', '\u006f'],
    'p': ['\uff50', '\u0440', '\u03c1', '\u0070'],
    's': ['\uff53', '\u0455', '\u03c3', '\u0073'],
    'x': ['\uff58', '\u0445', '\u03c7', '\u0078'],
    ' ': ['\u00a0', '\u1680', '\u2000', '\u2001', '\u2002', '\u2003', '\u2004', '\u2005', '\u2006', '\u2007', '\u2008', '\u2009', '\u200a', '\u202f', '\u205f', '\u3000', '\u0020'],
}


def safe_regex_search(
    pattern: re.Pattern,
    text: str,
    timeout: float = REGEX_TIMEOUT_SECONDS,
) -> re.Match | None:
    """
    安全的正则匹配（带超时保护和并发限制）
    
    防止 ReDoS 攻击，限制正则匹配的执行时间和并发数量。
    使用信号量限制并发正则匹配数量，防止资源耗尽。
    
    Args:
        pattern: 编译后的正则表达式
        text: 要匹配的文本
        timeout: 超时时间（秒）
        
    Returns:
        匹配结果，如果超时则返回 None
        
    Raises:
        RegexTimeoutError: 如果匹配超时
    """
    # 限制输入长度，防止超长输入导致性能问题
    if len(text) > MAX_INPUT_LENGTH:
        text = text[:MAX_INPUT_LENGTH]
        logger.debug(f"输入文本过长，已截断至 {MAX_INPUT_LENGTH} 字符")
    
    result: re.Match | None = None
    exception: Exception | None = None
    
    def match_worker():
        nonlocal result, exception
        try:
            result = pattern.search(text)
        except Exception as e:
            exception = e
    
    # 使用信号量限制并发正则匹配数量
    acquired = _regex_semaphore.acquire(blocking=True, timeout=5.0)
    if not acquired:
        logger.warning("正则匹配并发限制达到，无法获取信号量")
        raise RegexTimeoutError("正则匹配并发限制达到，请稍后重试")
    
    try:
        thread = threading.Thread(target=match_worker, daemon=True)
        thread.start()
        thread.join(timeout=timeout)
        
        if thread.is_alive():
            # 线程仍在运行，表示超时
            logger.warning(f"正则匹配超时: pattern={pattern.pattern[:50]}..., timeout={timeout}s")
            raise RegexTimeoutError(f"正则匹配超时（{timeout}秒）")
        
        if exception:
            raise exception
        
        return result
    finally:
        _regex_semaphore.release()


def safe_regex_findall(
    pattern: re.Pattern,
    text: str,
    timeout: float = REGEX_TIMEOUT_SECONDS,
) -> list:
    """
    安全的正则查找所有匹配（带超时保护和并发限制）
    
    使用信号量限制并发正则匹配数量，防止资源耗尽。
    
    Args:
        pattern: 编译后的正则表达式
        text: 要匹配的文本
        timeout: 超时时间（秒）
        
    Returns:
        所有匹配结果的列表
    """
    # 限制输入长度
    if len(text) > MAX_INPUT_LENGTH:
        text = text[:MAX_INPUT_LENGTH]
        logger.debug(f"输入文本过长，已截断至 {MAX_INPUT_LENGTH} 字符")
    
    result: list = []
    exception: Exception | None = None
    
    def match_worker():
        nonlocal result, exception
        try:
            result = pattern.findall(text)
        except Exception as e:
            exception = e
    
    # 使用信号量限制并发正则匹配数量
    acquired = _regex_semaphore.acquire(blocking=True, timeout=5.0)
    if not acquired:
        logger.warning("正则匹配并发限制达到，无法获取信号量")
        return []
    
    try:
        thread = threading.Thread(target=match_worker, daemon=True)
        thread.start()
        thread.join(timeout=timeout)
        
        if thread.is_alive():
            logger.warning(f"正则查找超时: pattern={pattern.pattern[:50]}...")
            return []
        
        if exception:
            return []
        
        return result
    finally:
        _regex_semaphore.release()


def normalize_unicode_confusables(text: str) -> str:
    """
    标准化 Unicode 同形字符
    
    Args:
        text: 原始文本
        
    Returns:
        标准化后的文本
    """
    normalized = text
    for standard, confusables in UNICODE_CONFUSABLES.items():
        for confusable in confusables:
            normalized = normalized.replace(confusable, standard)
    return normalized


def detect_encoding_bypass(text: str) -> list[tuple[str, str]]:
    """
    检测编码绕过尝试
    
    Args:
        text: 要检测的文本
        
    Returns:
        检测到的编码绕过列表 [(类型, 描述)]
    """
    detected = []
    
    encoding_patterns = [
        (r'%2e%2e', 'URL编码路径穿越'),
        (r'%252e', '双重URL编码'),
        (r'%c0%ae', 'UTF-8编码绕过'),
        (r'%uff0e', '宽字符编码'),
        (r'&#46;', 'HTML实体编码'),
        (r'&#x2e;', 'HTML十六进制实体'),
        (r'\\x2e', '十六进制转义'),
        (r'\\u002e', 'Unicode转义'),
    ]
    
    for pattern, desc in encoding_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            detected.append((pattern, desc))
    
    try:
        url_decoded = urllib.parse.unquote(text)
        if url_decoded != text:
            if '..' in url_decoded or '<' in url_decoded or '>' in url_decoded:
                detected.append(('url_decode', 'URL解码后包含危险字符'))
    except Exception:
        pass
    
    for standard, confusables in UNICODE_CONFUSABLES.items():
        for confusable in confusables:
            if confusable in text:
                detected.append((
                    f'unicode_confusable_{ord(confusable):04x}',
                    f'Unicode同形字符 U+{ord(confusable):04X} (类似 "{standard}")'
                ))
    
    return detected


def validate_path_security(
    path: str,
    base_dir: str | Path | None = None,
    allow_absolute: bool = False,
) -> tuple[bool, str, str | None]:
    """
    验证路径安全性
    
    使用规范化路径验证来检测路径穿越攻击。
    这比简单的正则匹配更可靠，因为它处理了所有编码变体。
    
    Args:
        path: 要验证的路径
        base_dir: 基础目录（如果提供，路径必须在此目录内）
        allow_absolute: 是否允许绝对路径
        
    Returns:
        (是否安全, 原因消息, 规范化后的路径)
    """
    if not path:
        return False, "路径为空", None
    
    try:
        # 1. 标准化 Unicode 同形字符
        normalized = normalize_unicode_confusables(path)
        
        # 2. URL 解码（处理编码绕过）
        try:
            decoded = urllib.parse.unquote(normalized)
            # 多次解码处理双重编码
            for _ in range(3):
                new_decoded = urllib.parse.unquote(decoded)
                if new_decoded == decoded:
                    break
                decoded = new_decoded
        except Exception:
            decoded = normalized
        
        # 3. 转换为 Path 对象并规范化
        path_obj = Path(decoded)
        
        # 4. 检查是否为绝对路径
        if path_obj.is_absolute() and not allow_absolute:
            return False, "不允许使用绝对路径", None
        
        # 5. 规范化路径（解析 .. 和 .）
        try:
            # 使用 resolve() 获取绝对路径（解析符号链接）
            # 但在 Windows 上可能需要处理驱动器号
            resolved_path = path_obj.resolve()
        except Exception as e:
            return False, f"路径解析失败: {e}", None
        
        # 6. 如果提供了基础目录，检查路径是否在基础目录内
        if base_dir:
            base_path = Path(base_dir).resolve()
            try:
                # 检查解析后的路径是否在基础目录内
                resolved_path.relative_to(base_path)
            except ValueError:
                return False, f"路径穿越检测：路径 '{path}' 超出允许的目录范围", None
        
        # 7. 检查路径中是否仍包含可疑模式
        path_str = str(resolved_path)
        suspicious_patterns = [
            r'\.\.',  # 父目录引用
            r'/etc/',  # Linux 敏感目录
            r'/var/',  # Linux 敏感目录
            r'/root/',  # Linux root 目录
            r'/proc/',  # Linux 进程信息
            r'\\Windows\\',  # Windows 系统目录
            r'\\System32\\',  # Windows 系统目录
            r'\\Program Files\\',  # Windows 程序目录
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, path_str, re.IGNORECASE):
                # 即使有 base_dir，也要检查路径是否真的在 base_dir 内
                if base_dir:
                    try:
                        resolved_path.relative_to(base_path)
                        # 路径确实在 base_dir 内，允许通过
                        continue
                    except ValueError:
                        return False, f"路径包含可疑模式且超出基础目录: {pattern}", None
                else:
                    return False, f"路径包含可疑模式: {pattern}", None
        
        return True, "路径验证通过", str(resolved_path)
        
    except Exception as e:
        # 不记录详细异常信息，防止路径信息泄露
        logger.error("路径验证异常")
        return False, "路径验证异常", None


def mask_sensitive_data(
    text: str,
    sensitive_fields: list[str] | None = None,
    sensitive_patterns: list[str] | None = None,
    replacement: str = "***MASKED***",
) -> str:
    """
    脱敏敏感数据
    
    对日志或输出中的敏感信息进行脱敏处理。
    使用字段名匹配和正则模式匹配双重机制。
    
    Args:
        text: 要脱敏的文本
        sensitive_fields: 敏感字段名列表
        sensitive_patterns: 敏感值正则模式列表
        replacement: 替换字符串
        
    Returns:
        脱敏后的文本
    """
    if not text:
        return text
    
    # 默认敏感字段
    default_fields = [
        "password", "passwd", "pwd", "pass",
        "token", "access_token", "refresh_token", "auth_token", "bearer_token",
        "secret", "app_secret", "client_secret", "signature_secret",
        "key", "api_key", "api_secret", "private_key", "public_key",
        "credential", "credentials",
        "ssn", "social_security_number",
        "credit_card", "card_number", "cvv", "cvc",
        "bank_account", "account_number",
        "id_card", "identity_card",
        "session_id", "session_key",
        "authorization", "auth",
        "cookie", "session",
    ]
    
    # 默认敏感值模式
    default_patterns = [
        r'\b\d{17,19}[xX]?\b',  # 身份证号
        r'\b1[3-9]\d{9}\b',  # 手机号
        r'\b\d{16,19}\b',  # 银行卡号
        r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',  # 邮箱
        r'\beyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*\b',  # JWT
    ]
    
    fields = sensitive_fields or default_fields
    patterns = sensitive_patterns or default_patterns
    
    result = text
    
    # 1. 字段名匹配脱敏（匹配 "field": "value" 或 field=value 格式）
    for field in fields:
        # JSON 格式: "field": "value"
        json_pattern = rf'("{field}"\s*:\s*")[^"]*(")'
        result = re.sub(json_pattern, rf'\1{replacement}\2', result, flags=re.IGNORECASE)
        
        # 键值对格式: field=value
        kv_pattern = rf'({field}\s*=\s*)[^\s,;]+'
        result = re.sub(kv_pattern, rf'\1{replacement}', result, flags=re.IGNORECASE)
        
        # URL 参数格式: field=value&
        url_pattern = rf'({field}=)[^&]*'
        result = re.sub(url_pattern, rf'\1{replacement}', result, flags=re.IGNORECASE)
    
    # 2. 正则模式匹配脱敏
    for pattern in patterns:
        try:
            result = re.sub(pattern, replacement, result)
        except re.error:
            continue
    
    return result


class SensitiveDataFilter(logging.Filter):
    """
    敏感数据日志过滤器
    
    在日志输出前自动脱敏敏感信息。
    """
    
    def __init__(
        self,
        sensitive_fields: list[str] | None = None,
        sensitive_patterns: list[str] | None = None,
        replacement: str = "***MASKED***",
    ):
        super().__init__()
        self.sensitive_fields = sensitive_fields
        self.sensitive_patterns = sensitive_patterns
        self.replacement = replacement
    
    def filter(self, record: logging.LogRecord) -> bool:
        """过滤日志记录，脱敏敏感信息"""
        # 脱敏消息
        if record.msg:
            record.msg = mask_sensitive_data(
                str(record.msg),
                self.sensitive_fields,
                self.sensitive_patterns,
                self.replacement,
            )
        
        # 脱敏参数
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: mask_sensitive_data(str(v), self.sensitive_fields, self.sensitive_patterns, self.replacement)
                    if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    mask_sensitive_data(str(arg), self.sensitive_fields, self.sensitive_patterns, self.replacement)
                    if isinstance(arg, str) else arg
                    for arg in record.args
                )
        
        return True


def setup_sensitive_data_logging(
    logger_name: str | None = None,
    sensitive_fields: list[str] | None = None,
    sensitive_patterns: list[str] | None = None,
) -> None:
    """
    设置敏感数据日志过滤
    
    为指定的日志记录器添加敏感数据过滤器。
    
    Args:
        logger_name: 日志记录器名称，为 None 则设置根日志记录器
        sensitive_fields: 敏感字段列表
        sensitive_patterns: 敏感值模式列表
    """
    target_logger = logging.getLogger(logger_name)
    
    # 检查是否已存在过滤器
    for existing_filter in target_logger.filters:
        if isinstance(existing_filter, SensitiveDataFilter):
            return
    
    # 添加过滤器
    sensitive_filter = SensitiveDataFilter(
        sensitive_fields=sensitive_fields,
        sensitive_patterns=sensitive_patterns,
    )
    target_logger.addFilter(sensitive_filter)
    
    logger.debug(f"已为日志记录器 '{logger_name or 'root'}' 添加敏感数据过滤器")


class FilterResult(str, Enum):
    """过滤结果枚举"""
    SAFE = "safe"               # 安全
    FILTERED = "filtered"       # 已过滤
    BLOCKED = "blocked"         # 已阻止
    WARNING = "warning"         # 警告


@dataclass
class FilteredContent:
    """过滤后的内容"""
    original: str                           # 原始内容
    filtered: str                           # 过滤后内容
    result: FilterResult                    # 过滤结果
    matched_rules: list[str] = field(default_factory=list)  # 匹配的规则
    warnings: list[str] = field(default_factory=list)       # 警告信息
    metadata: dict[str, Any] = field(default_factory=dict)  # 元数据
    
    @property
    def is_safe(self) -> bool:
        """是否安全"""
        return self.result == FilterResult.SAFE
    
    @property
    def is_blocked(self) -> bool:
        """是否被阻止"""
        return self.result == FilterResult.BLOCKED
    
    @property
    def was_filtered(self) -> bool:
        """是否被过滤"""
        return self.result == FilterResult.FILTERED


@dataclass
class SecurityEvent:
    """安全事件记录"""
    event_type: str                         # 事件类型
    severity: str                           # 严重程度: low, medium, high, critical
    source: str                             # 来源
    content: str                            # 相关内容
    matched_pattern: str | None = None      # 匹配的模式
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


class ContentFilter:
    """
    内容过滤器
    
    对输入输出内容进行安全过滤
    """
    
    def __init__(self, config: ContentFilterConfig):
        """
        初始化内容过滤器
        
        Args:
            config: 内容过滤配置
        """
        self.config = config
        self._compiled_patterns: dict[str, list[re.Pattern]] = {}
        self._compile_patterns()
        
        # 安全事件记录
        self._security_events: list[SecurityEvent] = []
        
        logger.info(f"内容过滤器初始化完成，安全级别: {config.security_level.value}")
    
    def _compile_patterns(self) -> None:
        """编译所有正则表达式模式，包含复杂度验证防止 ReDoS 攻击"""
        # 正则模式复杂度限制
        max_pattern_length = 1000  # 限制模式最大长度
        max_nesting_depth = 5  # 限制嵌套深度
        max_repetition_nesting = 3  # 限制重复嵌套深度
        
        def _validate_pattern_complexity(pattern: str, name: str) -> bool:
            """验证正则表达式复杂度，防止 ReDoS 攻击"""
            if len(pattern) > max_pattern_length:
                logger.warning(f"{name} 模式过长 ({len(pattern)} 字符)，跳过: {pattern[:50]}...")
                return False
            
            # 检测危险的重复嵌套模式 (如 (a+)+ 或 (a*)+)
            dangerous_patterns = [
                r'\([^)]*[+*][^)]*\)[+*]',  # (a+)+ 或 (a*)+
                r'\([^)]*[+*][^)]*\)\{',    # (a+){n,m}
                r'\(\?:[^)]*[+*][^)]*\)[+*]',  # (?:a+)+
            ]
            for dangerous in dangerous_patterns:
                if re.search(dangerous, pattern):
                    logger.warning(f"{name} 模式包含危险的重复嵌套，可能导致 ReDoS: {pattern[:50]}...")
                    return False
            
            # 检查嵌套深度
            depth = 0
            max_depth_seen = 0
            for char in pattern:
                if char == '(':
                    depth += 1
                    max_depth_seen = max(max_depth_seen, depth)
                elif char == ')':
                    depth -= 1
            if max_depth_seen > max_nesting_depth:
                logger.warning(f"{name} 模式嵌套深度过大 ({max_depth_seen})，跳过: {pattern[:50]}...")
                return False
            
            return True
        
        def _safe_compile(pattern: str, flags: int, name: str) -> re.Pattern | None:
            """安全编译正则表达式"""
            try:
                if not _validate_pattern_complexity(pattern, name):
                    return None
                return re.compile(pattern, flags)
            except re.error as e:
                logger.warning(f"{name} 正则编译失败: {e}, 模式: {pattern[:50]}...")
                return None
        
        # 敏感词模式
        if self.config.enable_sensitive_words:
            compiled_words = []
            for word in self.config.sensitive_words:
                if len(word) > max_pattern_length:
                    logger.warning(f"敏感词过长 ({len(word)} 字符)，跳过: {word[:50]}...")
                    continue
                try:
                    pattern = re.compile(re.escape(word), re.IGNORECASE)
                    compiled_words.append(pattern)
                except re.error as e:
                    logger.warning(f"敏感词正则编译失败: {e}")
            self._compiled_patterns["sensitive_words"] = compiled_words
        
        # 正则过滤模式
        if self.config.enable_regex_filter:
            compiled_regex = []
            for pattern in self.config.blocked_patterns:
                compiled = _safe_compile(pattern, re.IGNORECASE, "正则过滤")
                if compiled:
                    compiled_regex.append(compiled)
            self._compiled_patterns["regex"] = compiled_regex
        
        # 命令注入模式
        if self.config.enable_command_injection_filter:
            compiled_cmd = []
            for pattern in self.config.command_injection_patterns:
                compiled = _safe_compile(pattern, re.IGNORECASE, "命令注入")
                if compiled:
                    compiled_cmd.append(compiled)
            self._compiled_patterns["command_injection"] = compiled_cmd
        
        # XSS 模式
        if self.config.enable_xss_filter:
            compiled_xss = []
            for pattern in self.config.xss_patterns:
                compiled = _safe_compile(pattern, re.IGNORECASE | re.DOTALL, "XSS")
                if compiled:
                    compiled_xss.append(compiled)
            self._compiled_patterns["xss"] = compiled_xss
        
        # 路径穿越模式
        if self.config.enable_path_traversal_filter:
            compiled_path = []
            for pattern in self.config.path_traversal_patterns:
                compiled = _safe_compile(pattern, re.IGNORECASE, "路径穿越")
                if compiled:
                    compiled_path.append(compiled)
            self._compiled_patterns["path_traversal"] = compiled_path
        
        # SQL 注入模式
        if self.config.enable_sql_injection_filter:
            compiled_sql = []
            for pattern in self.config.sql_injection_patterns:
                compiled = _safe_compile(pattern, re.IGNORECASE, "SQL注入")
                if compiled:
                    compiled_sql.append(compiled)
            self._compiled_patterns["sql_injection"] = compiled_sql
        
        logger.debug(f"已编译 {len(self._compiled_patterns)} 类过滤模式")
    
    def filter(self, content: str, context: dict[str, Any] | None = None) -> FilteredContent:
        """
        过滤内容
        
        Args:
            content: 要过滤的内容
            context: 上下文信息
            
        Returns:
            过滤后的内容对象
        """
        if not content:
            return FilteredContent(
                original=content,
                filtered=content,
                result=FilterResult.SAFE,
            )
        
        original = content
        filtered = content
        matched_rules: list[str] = []
        warnings: list[str] = []
        blocked = False
        
        encoding_issues = detect_encoding_bypass(content)
        if encoding_issues:
            for issue_type, issue_desc in encoding_issues:
                matched_rules.append(f"encoding_bypass:{issue_type}")
                warnings.append(f"检测到编码绕过尝试: {issue_desc}")
            
            self._record_security_event(
                event_type="encoding_bypass_attempt",
                severity="high",
                source=context.get("source", "unknown") if context else "unknown",
                content=original[:200],
                matched_pattern=encoding_issues[0][0] if encoding_issues else None,
            )
            
            if self.config.security_level in [SecurityLevel.HIGH, SecurityLevel.STRICT]:
                blocked = True
                warnings.append("检测到编码绕过尝试，内容已阻止")
        
        normalized_content = normalize_unicode_confusables(filtered)
        
        if len(content) > self.config.max_message_length:
            warnings.append(f"消息长度超过限制 ({len(content)} > {self.config.max_message_length})")
            filtered = filtered[:self.config.max_message_length] + "..."
            matched_rules.append("max_length_exceeded")
        
        if self.config.enable_sensitive_words:
            filtered, words_found = self._filter_sensitive_words(filtered)
            if words_found:
                matched_rules.append(f"sensitive_words:{','.join(words_found)}")
                warnings.append(f"发现敏感词: {', '.join(words_found)}")
        
        if self.config.enable_regex_filter:
            filtered, patterns_matched = self._filter_regex_patterns(filtered, "regex")
            if patterns_matched:
                matched_rules.append(f"regex_patterns:{len(patterns_matched)}")
                warnings.append(f"匹配到 {len(patterns_matched)} 个阻止模式")
        
        if self.config.enable_command_injection_filter:
            result, cmd_patterns = self._check_command_injection(normalized_content)
            if cmd_patterns:
                matched_rules.append(f"command_injection:{','.join(cmd_patterns)}")
                self._record_security_event(
                    event_type="command_injection_attempt",
                    severity="high",
                    source=context.get("source", "unknown") if context else "unknown",
                    content=original[:200],
                    matched_pattern=cmd_patterns[0] if cmd_patterns else None,
                )
                if self.config.security_level in [SecurityLevel.HIGH, SecurityLevel.STRICT]:
                    blocked = True
                    warnings.append("检测到命令注入尝试，内容已阻止")
        
        if self.config.enable_xss_filter:
            filtered, xss_patterns = self._filter_xss(filtered)
            if xss_patterns:
                matched_rules.append(f"xss:{','.join(xss_patterns)}")
                warnings.append("检测到 XSS 攻击模式")
                self._record_security_event(
                    event_type="xss_attempt",
                    severity="medium",
                    source=context.get("source", "unknown") if context else "unknown",
                    content=original[:200],
                    matched_pattern=xss_patterns[0] if xss_patterns else None,
                )
        
        if self.config.enable_path_traversal_filter:
            result, path_patterns = self._check_path_traversal(normalized_content)
            if path_patterns:
                matched_rules.append(f"path_traversal:{','.join(path_patterns)}")
                warnings.append("检测到路径穿越尝试")
                self._record_security_event(
                    event_type="path_traversal_attempt",
                    severity="high",
                    source=context.get("source", "unknown") if context else "unknown",
                    content=original[:200],
                    matched_pattern=path_patterns[0] if path_patterns else None,
                )
                if self.config.security_level in [SecurityLevel.HIGH, SecurityLevel.STRICT]:
                    blocked = True
                    warnings.append("检测到路径穿越尝试，内容已阻止")
        
        if self.config.enable_sql_injection_filter:
            result, sql_patterns = self._check_sql_injection(normalized_content)
            if sql_patterns:
                matched_rules.append(f"sql_injection:{','.join(sql_patterns)}")
                warnings.append("检测到 SQL 注入尝试")
                self._record_security_event(
                    event_type="sql_injection_attempt",
                    severity="critical",
                    source=context.get("source", "unknown") if context else "unknown",
                    content=original[:200],
                    matched_pattern=sql_patterns[0] if sql_patterns else None,
                )
                blocked = True
                warnings.append("检测到 SQL 注入尝试，内容已阻止")
        
        if self.config.enable_url_filter:
            filtered, url_warnings = self._filter_urls(filtered)
            if url_warnings:
                matched_rules.append("url_filter")
                warnings.extend(url_warnings)
        
        if self.config.enable_file_type_filter:
            result, file_warnings = self._check_file_types(filtered)
            if file_warnings:
                matched_rules.append("file_type_filter")
                warnings.extend(file_warnings)
        
        if blocked:
            result = FilterResult.BLOCKED
        elif matched_rules:
            result = FilterResult.FILTERED
        elif warnings:
            result = FilterResult.WARNING
        else:
            result = FilterResult.SAFE
        
        return FilteredContent(
            original=original,
            filtered=filtered,
            result=result,
            matched_rules=matched_rules,
            warnings=warnings,
            metadata={"context": context},
        )
    
    def _filter_sensitive_words(self, content: str) -> tuple[str, list[str]]:
        """
        过滤敏感词
        
        使用安全的正则匹配，防止 ReDoS 攻击。
        
        Args:
            content: 内容
            
        Returns:
            (过滤后内容, 发现的敏感词列表)
        """
        found_words = []
        patterns = self._compiled_patterns.get("sensitive_words", [])
        
        for pattern in patterns:
            try:
                # 使用安全的正则匹配
                matches = safe_regex_findall(pattern, content)
                if matches:
                    found_words.extend(matches)
                    content = pattern.sub(self.config.sensitive_word_replacement, content)
            except RegexTimeoutError:
                logger.warning(f"敏感词匹配超时，跳过该模式: {pattern.pattern[:30]}...")
                continue
            except Exception as e:
                logger.debug(f"敏感词匹配异常: {e}")
                continue
        
        return content, list(set(found_words))
    
    def _filter_regex_patterns(
        self,
        content: str,
        pattern_type: str
    ) -> tuple[str, list[str]]:
        """
        使用正则表达式过滤
        
        使用安全的正则匹配，防止 ReDoS 攻击。
        
        Args:
            content: 内容
            pattern_type: 模式类型
            
        Returns:
            (过滤后内容, 匹配的模式列表)
        """
        matched = []
        patterns = self._compiled_patterns.get(pattern_type, [])
        
        for pattern in patterns:
            try:
                # 使用安全的正则匹配
                if safe_regex_search(pattern, content):
                    matched.append(pattern.pattern)
                    # 根据安全级别决定处理方式
                    if self.config.security_level in [SecurityLevel.HIGH, SecurityLevel.STRICT]:
                        content = pattern.sub("[FILTERED]", content)
            except RegexTimeoutError:
                logger.warning(f"正则匹配超时，跳过该模式: {pattern.pattern[:30]}...")
                continue
            except Exception as e:
                logger.debug(f"正则匹配异常: {e}")
                continue
        
        return content, matched
    
    def _check_command_injection(self, content: str) -> tuple[bool, list[str]]:
        """
        检查命令注入
        
        使用安全的正则匹配，防止 ReDoS 攻击。
        
        Args:
            content: 内容
            
        Returns:
            (是否检测到注入, 匹配的模式列表)
        """
        matched = []
        patterns = self._compiled_patterns.get("command_injection", [])
        
        for pattern in patterns:
            try:
                if safe_regex_search(pattern, content):
                    matched.append(pattern.pattern)
            except RegexTimeoutError:
                logger.warning(f"命令注入检测超时，跳过该模式: {pattern.pattern[:30]}...")
                continue
            except Exception as e:
                logger.debug(f"命令注入检测异常: {e}")
                continue
        
        return len(matched) > 0, matched
    
    def _filter_xss(self, content: str) -> tuple[str, list[str]]:
        """
        过滤 XSS 攻击
        
        使用安全的正则匹配，防止 ReDoS 攻击。
        
        Args:
            content: 内容
            
        Returns:
            (过滤后内容, 匹配的模式列表)
        """
        matched = []
        patterns = self._compiled_patterns.get("xss", [])
        
        for pattern in patterns:
            try:
                if safe_regex_search(pattern, content):
                    matched.append(pattern.pattern)
                    # 移除危险内容
                    content = pattern.sub("", content)
            except RegexTimeoutError:
                logger.warning(f"XSS 检测超时，跳过该模式: {pattern.pattern[:30]}...")
                continue
            except Exception as e:
                logger.debug(f"XSS 检测异常: {e}")
                continue
        
        return content, matched
    
    def _check_path_traversal(self, content: str) -> tuple[bool, list[str]]:
        """
        检查路径穿越
        
        使用规范化路径验证来检测路径穿越攻击。
        这比简单的正则匹配更可靠。
        
        Args:
            content: 内容
            
        Returns:
            (是否检测到穿越, 匹配的模式列表)
        """
        matched = []
        
        # 首先使用正则模式快速检测
        patterns = self._compiled_patterns.get("path_traversal", [])
        for pattern in patterns:
            if pattern.search(content):
                matched.append(pattern.pattern)
        
        # 如果检测到可能的路径穿越，使用更严格的验证
        if matched:
            # 尝试从内容中提取路径
            path_patterns = [
                r'(?:file://|/|[A-Za-z]:\\)([^\s<>"\']*)',  # 文件路径
                r'(?:path\s*[:=]\s*)["\']?([^\s"\']+)["\']?',  # path=xxx
            ]
            
            for path_pattern in path_patterns:
                for match in re.finditer(path_pattern, content, re.IGNORECASE):
                    potential_path = match.group(1) if match.lastindex else match.group(0)
                    is_safe, reason, _ = validate_path_security(potential_path)
                    if not is_safe:
                        matched.append(f"validated:{reason}")
        
        return len(matched) > 0, matched
    
    def _check_sql_injection(self, content: str) -> tuple[bool, list[str]]:
        """
        检查 SQL 注入
        
        使用安全的正则匹配，防止 ReDoS 攻击。
        
        Args:
            content: 内容
            
        Returns:
            (是否检测到注入, 匹配的模式列表)
        """
        matched = []
        patterns = self._compiled_patterns.get("sql_injection", [])
        
        for pattern in patterns:
            try:
                if safe_regex_search(pattern, content):
                    matched.append(pattern.pattern)
            except RegexTimeoutError:
                logger.warning(f"SQL 注入检测超时，跳过该模式: {pattern.pattern[:30]}...")
                continue
            except Exception as e:
                logger.debug(f"SQL 注入检测异常: {e}")
                continue
        
        return len(matched) > 0, matched
    
    def _filter_urls(self, content: str) -> tuple[str, list[str]]:
        """
        过滤 URL
        
        Args:
            content: 内容
            
        Returns:
            (过滤后内容, 警告列表)
        """
        warnings = []
        
        # 检查 URL 协议
        url_pattern = re.compile(r'(https?://[^\s]+)', re.IGNORECASE)
        
        def check_url(match):
            url = match.group(1)
            # 检查协议
            scheme = url.split("://")[0].lower()
            if scheme not in self.config.allowed_url_schemes:
                warnings.append(f"不允许的 URL 协议: {scheme}")
                return "[BLOCKED_URL]"
            
            # 检查域名
            for blocked_domain in self.config.blocked_domains:
                if blocked_domain in url:
                    warnings.append(f"阻止的域名: {blocked_domain}")
                    return "[BLOCKED_URL]"
            
            return url
        
        content = url_pattern.sub(check_url, content)
        return content, warnings
    
    def _check_file_types(self, content: str) -> tuple[bool, list[str]]:
        """
        检查文件类型
        
        Args:
            content: 内容
            
        Returns:
            (是否检测到不允许的类型, 警告列表)
        """
        warnings = []
        file_pattern = re.compile(r'\.([a-zA-Z0-9]+)(?:\s|$|\"|\')')
        
        matches = file_pattern.findall(content)
        for ext in matches:
            ext_lower = f".{ext.lower()}"
            if ext_lower not in self.config.allowed_file_extensions:
                warnings.append(f"不允许的文件类型: {ext_lower}")
        
        return len(warnings) > 0, warnings
    
    def _record_security_event(
        self,
        event_type: str,
        severity: str,
        source: str,
        content: str,
        matched_pattern: str | None = None,
    ) -> None:
        """
        记录安全事件
        
        Args:
            event_type: 事件类型
            severity: 严重程度
            source: 来源
            content: 相关内容
            matched_pattern: 匹配的模式
        """
        event = SecurityEvent(
            event_type=event_type,
            severity=severity,
            source=source,
            content=content[:500],
            matched_pattern=matched_pattern,
        )
        self._security_events.append(event)
        
        log_msg = f"安全事件: {event_type} [{severity}] 来源: {source}"
        if matched_pattern:
            log_msg += f" 模式: {matched_pattern}"
        logger.warning(log_msg)
    
    def get_security_events(
        self,
        event_type: str | None = None,
        severity: str | None = None,
        limit: int = 100,
    ) -> list[SecurityEvent]:
        """
        获取安全事件记录
        
        Args:
            event_type: 事件类型过滤
            severity: 严重程度过滤
            limit: 最大返回数量
            
        Returns:
            安全事件列表
        """
        events = self._security_events
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if severity:
            events = [e for e in events if e.severity == severity]
        
        return events[-limit:]
    
    def clear_security_events(self) -> None:
        """清除安全事件记录"""
        self._security_events.clear()
        logger.info("安全事件记录已清除")


class RateLimiter:
    """
    速率限制器（线程安全）
    
    控制请求频率，防止滥用
    
    特性：
    - 每分钟/每小时请求限制
    - 自动清理过期记录
    - 阻塞超限请求
    - 线程安全（使用锁保护共享数据）
    """
    
    AUTO_CLEANUP_INTERVAL = 300  # 自动清理间隔（秒）
    MAX_RECORDS_PER_IDENTIFIER = 1000  # 每个标识符最大记录数
    
    def __init__(self, config: ContentFilterConfig):
        """
        初始化速率限制器
        
        Args:
            config: 内容过滤配置
        """
        self.config = config
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._blocked_until: dict[str, float] = {}
        self._last_cleanup: float = time.time()
        
        # 线程锁，保护共享数据
        self._lock = threading.Lock()
        
        self._start_auto_cleanup()
    
    def _start_auto_cleanup(self) -> None:
        """启动自动清理机制"""
        def cleanup_worker():
            while True:
                try:
                    time.sleep(self.AUTO_CLEANUP_INTERVAL)
                    self.cleanup_expired_records()
                except Exception as e:
                    logger.debug(f"自动清理异常: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
        logger.debug("速率限制自动清理线程已启动")
    
    def check_rate_limit(self, identifier: str) -> tuple[bool, str]:
        """
        检查速率限制（线程安全）
        
        Args:
            identifier: 标识符（如用户 ID、IP 地址）
            
        Returns:
            (是否允许, 原因消息)
        """
        if not self.config.enable_rate_limit:
            return True, "速率限制未启用"
        
        current_time = time.time()
        
        # 使用锁保护共享数据访问
        with self._lock:
            if current_time - self._last_cleanup > self.AUTO_CLEANUP_INTERVAL:
                self._cleanup_expired_records_unlocked()
                self._last_cleanup = current_time
            
            if identifier in self._blocked_until:
                if current_time < self._blocked_until[identifier]:
                    remaining = int(self._blocked_until[identifier] - current_time)
                    return False, f"请求过于频繁，请等待 {remaining} 秒"
                else:
                    del self._blocked_until[identifier]
            
            requests = self._requests[identifier]
            
            minute_ago = current_time - 60
            hour_ago = current_time - 3600
            
            # 过滤过期请求
            requests[:] = [t for t in requests if t > hour_ago]
            
            if len(requests) > self.MAX_RECORDS_PER_IDENTIFIER:
                requests[:] = requests[-self.MAX_RECORDS_PER_IDENTIFIER:]
            
            minute_requests = [t for t in requests if t > minute_ago]
            if len(minute_requests) >= self.config.max_requests_per_minute:
                self._blocked_until[identifier] = current_time + 60
                return False, f"每分钟请求次数超过限制 ({self.config.max_requests_per_minute})"
            
            if len(requests) >= self.config.max_requests_per_hour:
                self._blocked_until[identifier] = current_time + 300
                return False, f"每小时请求次数超过限制 ({self.config.max_requests_per_hour})"
            
            # 记录本次请求
            requests.append(current_time)
            
            return True, "请求允许"
    
    def _cleanup_expired_records_unlocked(self, max_age_hours: int = 2) -> int:
        """
        清理过期记录（内部方法，调用者需持有锁）
        
        Args:
            max_age_hours: 最大保留时间（小时）
            
        Returns:
            清理的记录数量
        """
        current_time = time.time()
        cutoff_time = current_time - (max_age_hours * 3600)
        
        cleaned = 0
        
        for identifier in list(self._requests.keys()):
            requests = self._requests[identifier]
            original_len = len(requests)
            requests[:] = [t for t in requests if t > cutoff_time]
            
            if not requests:
                del self._requests[identifier]
            
            cleaned += original_len - len(requests)
        
        for identifier in list(self._blocked_until.keys()):
            if current_time > self._blocked_until[identifier]:
                del self._blocked_until[identifier]
                cleaned += 1
        
        if cleaned > 0:
            logger.debug(f"清理了 {cleaned} 条过期速率限制记录")
        
        return cleaned
    
    def cleanup_expired_records(self, max_age_hours: int = 2) -> int:
        """
        清理过期记录（线程安全）
        
        Args:
            max_age_hours: 最大保留时间（小时）
            
        Returns:
            清理的记录数量
        """
        with self._lock:
            return self._cleanup_expired_records_unlocked(max_age_hours)
    
    def get_status(self, identifier: str) -> dict[str, Any]:
        """
        获取速率限制状态
        
        Args:
            identifier: 标识符
            
        Returns:
            状态信息
        """
        current_time = time.time()
        requests = self._requests.get(identifier, [])
        
        minute_ago = current_time - 60
        hour_ago = current_time - 3600
        
        minute_requests = len([t for t in requests if t > minute_ago])
        hour_requests = len([t for t in requests if t > hour_ago])
        
        blocked = identifier in self._blocked_until and current_time < self._blocked_until[identifier]
        remaining = 0
        if blocked:
            remaining = int(self._blocked_until[identifier] - current_time)
        
        return {
            "identifier": identifier,
            "minute_requests": minute_requests,
            "hour_requests": hour_requests,
            "max_per_minute": self.config.max_requests_per_minute,
            "max_per_hour": self.config.max_requests_per_hour,
            "is_blocked": blocked,
            "blocked_remaining_seconds": remaining,
        }
    
    def reset(self, identifier: str | None = None) -> None:
        """
        重置速率限制
        
        Args:
            identifier: 标识符，为 None 则重置所有
        """
        if identifier:
            self._requests.pop(identifier, None)
            self._blocked_until.pop(identifier, None)
        else:
            self._requests.clear()
            self._blocked_until.clear()


class SecurityValidator:
    """
    安全验证器
    
    提供身份验证和签名验证功能
    """
    
    def __init__(self, config: SecurityConfig):
        """
        初始化安全验证器
        
        Args:
            config: 安全配置
        """
        self.config = config
        self._sessions: dict[str, dict[str, Any]] = {}
    
    def verify_signature(
        self,
        data: str,
        signature: str,
        timestamp: str | None = None,
    ) -> tuple[bool, str]:
        """
        验证签名
        
        Args:
            data: 原始数据
            signature: 签名
            timestamp: 时间戳（可选）
            
        Returns:
            (是否验证通过, 原因消息)
        """
        if not self.config.enable_signature_verification:
            return True, "签名验证未启用"
        
        if not self.config.signature_secret:
            logger.warning("签名密钥未配置")
            return False, "签名密钥未配置"
        
        allowed_algorithms = {'sha256', 'sha384', 'sha512', 'sha3_256', 'sha3_384', 'sha3_512'}
        algorithm = self.config.signature_algorithm.lower()
        
        if algorithm not in allowed_algorithms:
            logger.error(f"不安全的签名算法: {algorithm}，只允许: {allowed_algorithms}")
            return False, f"签名算法不安全: {algorithm}，请使用 sha256 或更强的算法"
        
        try:
            if timestamp:
                sign_data = f"{timestamp}{data}"
            else:
                sign_data = data
            
            hash_func = getattr(hashlib, algorithm, None)
            if hash_func is None:
                return False, f"不支持的签名算法: {algorithm}"
            
            expected_signature = hmac.new(
                self.config.signature_secret.encode(),
                sign_data.encode(),
                hash_func,
            ).hexdigest()
            
            if hmac.compare_digest(signature, expected_signature):
                return True, "签名验证通过"
            else:
                # 不记录签名值，只记录验证失败事件
                logger.warning("签名验证失败: 签名不匹配")
                return False, "签名验证失败"
                
        except Exception as e:
            # 不记录异常详情，防止信息泄露
            logger.error("签名验证异常")
            return False, "签名验证异常"
    
    def generate_signature(
        self,
        data: str,
        timestamp: str | None = None,
    ) -> str:
        """
        生成签名
        
        Args:
            data: 原始数据
            timestamp: 时间戳（可选）
            
        Returns:
            签名字符串
        """
        if not self.config.signature_secret:
            raise ValueError("签名密钥未配置")
        
        allowed_algorithms = {'sha256', 'sha384', 'sha512', 'sha3_256', 'sha3_384', 'sha3_512'}
        algorithm = self.config.signature_algorithm.lower()
        
        if algorithm not in allowed_algorithms:
            raise ValueError(f"签名算法不安全: {algorithm}，请使用 sha256 或更强的算法")
        
        if timestamp:
            sign_data = f"{timestamp}{data}"
        else:
            sign_data = data
        
        hash_func = getattr(hashlib, algorithm, None)
        if hash_func is None:
            raise ValueError(f"不支持的签名算法: {algorithm}")
        
        signature = hmac.new(
            self.config.signature_secret.encode(),
            sign_data.encode(),
            hash_func,
        ).hexdigest()
        
        return signature
    
    def check_ip_whitelist(self, ip_address: str) -> tuple[bool, str]:
        """
        检查 IP 白名单
        
        Args:
            ip_address: IP 地址
            
        Returns:
            (是否允许, 原因消息)
        """
        if not self.config.enable_ip_whitelist:
            return True, "IP 白名单未启用"
        
        if not self.config.ip_whitelist:
            return True, "IP 白名单为空，允许所有 IP"
        
        if ip_address in self.config.ip_whitelist:
            return True, f"IP {ip_address} 在白名单中"
        else:
            logger.warning(f"IP {ip_address} 不在白名单中")
            return False, f"IP {ip_address} 不在白名单中"
    
    def create_session(
        self,
        user_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        创建会话（使用高熵随机数生成会话 ID）
        
        使用 secrets.token_urlsafe() 生成高熵会话 ID，
        防止会话 ID 被猜测或暴力破解。
        
        Args:
            user_id: 用户 ID
            metadata: 元数据
            
        Returns:
            会话 ID
        """
        # 使用 secrets 模块生成高熵会话 ID（32 字节 = 43 个 URL 安全字符）
        session_id = secrets.token_urlsafe(32)
        
        # 添加会话指纹（用于检测会话劫持）
        session_fingerprint = self._generate_session_fingerprint(metadata)
        
        self._sessions[session_id] = {
            "user_id": user_id,
            "created_at": time.time(),
            "last_activity": time.time(),
            "metadata": metadata or {},
            "fingerprint": session_fingerprint,
            "regenerated": False,  # 标记是否已重新生成（用于会话固定攻击防护）
        }
        
        logger.debug(f"创建会话: {session_id[:16]}... 用户: {user_id}")
        return session_id
    
    def _generate_session_fingerprint(self, metadata: dict[str, Any] | None) -> str:
        """
        生成会话指纹
        
        用于检测会话劫持攻击。
        
        Args:
            metadata: 会话元数据
            
        Returns:
            会话指纹字符串
        """
        fingerprint_data = []
        
        if metadata:
            # 包含用户代理、IP 等信息（如果提供）
            if "user_agent" in metadata:
                fingerprint_data.append(str(metadata["user_agent"]))
            if "ip_address" in metadata:
                fingerprint_data.append(str(metadata["ip_address"]))
        
        # 添加随机盐值
        fingerprint_data.append(secrets.token_hex(8))
        
        # 生成指纹哈希
        fingerprint_str = "|".join(fingerprint_data)
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()[:32]
    
    def validate_session(
        self,
        session_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        """
        验证会话（包含会话固定攻击防护）
        
        Args:
            session_id: 会话 ID
            metadata: 当前请求的元数据（用于指纹验证）
            
        Returns:
            (是否有效, 原因消息, 会话数据)
        """
        if not self.config.enable_authentication:
            return True, "身份验证未启用", None
        
        if session_id not in self._sessions:
            return False, "会话不存在", None
        
        session = self._sessions[session_id]
        current_time = time.time()
        
        # 检查会话是否过期
        if current_time - session["last_activity"] > self.config.session_timeout:
            del self._sessions[session_id]
            return False, "会话已过期", None
        
        # 验证会话指纹（检测会话劫持）
        if metadata and "fingerprint" in session:
            current_fingerprint = self._generate_session_fingerprint(metadata)
            # 简化指纹验证：只检查 IP 和 User-Agent 是否变化
            if metadata.get("check_fingerprint", False):
                stored_fp = session.get("fingerprint", "")
                if stored_fp and not self._compare_fingerprints(stored_fp, current_fingerprint):
                    logger.warning(f"会话指纹不匹配，可能的会话劫持: {session_id[:16]}...")
                    # 不立即删除会话，但记录警告
                    # 可以根据安全策略选择是否删除
        
        # 更新最后活动时间
        session["last_activity"] = current_time
        
        return True, "会话有效", session
    
    def _compare_fingerprints(self, stored: str, current: str) -> bool:
        """
        安全比较会话指纹（使用常量时间比较）
        
        Args:
            stored: 存储的指纹
            current: 当前指纹
            
        Returns:
            是否匹配
        """
        # 使用 hmac.compare_digest 防止时序攻击
        try:
            return hmac.compare_digest(stored[:16], current[:16])
        except Exception:
            return False
    
    def regenerate_session(self, old_session_id: str) -> str | None:
        """
        重新生成会话 ID（防止会话固定攻击）
        
        在用户登录或权限提升后调用此方法。
        
        Args:
            old_session_id: 旧的会话 ID
            
        Returns:
            新的会话 ID，如果失败则返回 None
        """
        if old_session_id not in self._sessions:
            return None
        
        session_data = self._sessions[old_session_id].copy()
        
        # 删除旧会话
        del self._sessions[old_session_id]
        
        # 生成新会话 ID
        new_session_id = secrets.token_urlsafe(32)
        
        # 重置所有可能被攻击者影响的字段
        # 标记会话已重新生成
        session_data["regenerated"] = True
        session_data["last_activity"] = time.time()
        
        # 重新生成会话指纹，防止会话劫持
        # 保留 metadata 但重新生成指纹（因为攻击者可能已经获取了旧指纹）
        old_metadata = session_data.get("metadata", {})
        session_data["fingerprint"] = self._generate_session_fingerprint(old_metadata)
        
        # 清除可能被攻击者设置的可疑字段
        suspicious_keys = ["csrf_token", "oauth_state", "temp_data"]
        for key in suspicious_keys:
            session_data.pop(key, None)
        
        # 保存新会话
        self._sessions[new_session_id] = session_data
        
        logger.debug(f"会话重新生成: {old_session_id[:16]}... -> {new_session_id[:16]}...")
        return new_session_id
    
    def invalidate_session(self, session_id: str) -> bool:
        """
        使会话失效
        
        Args:
            session_id: 会话 ID
            
        Returns:
            是否成功
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.debug(f"会话已失效: {session_id}")
            return True
        return False
    
    def cleanup_expired_sessions(self) -> int:
        """
        清理过期会话
        
        Returns:
            清理的会话数量
        """
        current_time = time.time()
        expired = [
            sid for sid, session in self._sessions.items()
            if current_time - session["last_activity"] > self.config.session_timeout
        ]
        
        for sid in expired:
            del self._sessions[sid]
        
        if expired:
            logger.info(f"清理了 {len(expired)} 个过期会话")
        
        return len(expired)


class SecurityManager:
    """
    安全管理器
    
    整合所有安全功能
    """
    
    def __init__(
        self,
        content_filter_config: ContentFilterConfig,
        security_config: SecurityConfig,
    ):
        """
        初始化安全管理器
        
        Args:
            content_filter_config: 内容过滤配置
            security_config: 安全配置
        """
        self.content_filter = ContentFilter(content_filter_config)
        self.rate_limiter = RateLimiter(content_filter_config)
        self.validator = SecurityValidator(security_config)
        
        self._security_config = security_config
        
        logger.info("安全管理器初始化完成")
    
    def validate_request(
        self,
        content: str,
        identifier: str,
        ip_address: str | None = None,
        session_id: str | None = None,
        signature: str | None = None,
        timestamp: str | None = None,
    ) -> tuple[bool, FilteredContent, str]:
        """
        验证请求
        
        整合所有安全检查
        
        Args:
            content: 请求内容
            identifier: 标识符
            ip_address: IP 地址
            session_id: 会话 ID
            signature: 签名
            timestamp: 时间戳
            
        Returns:
            (是否通过, 过滤结果, 原因消息)
        """
        # 1. IP 白名单检查
        if ip_address:
            allowed, msg = self.validator.check_ip_whitelist(ip_address)
            if not allowed:
                return False, FilteredContent(
                    original=content,
                    filtered="",
                    result=FilterResult.BLOCKED,
                ), msg
        
        # 2. 会话验证
        if session_id:
            valid, msg, _ = self.validator.validate_session(session_id)
            if not valid:
                return False, FilteredContent(
                    original=content,
                    filtered="",
                    result=FilterResult.BLOCKED,
                ), msg
        
        # 3. 签名验证
        if signature:
            valid, msg = self.validator.verify_signature(content, signature, timestamp)
            if not valid:
                return False, FilteredContent(
                    original=content,
                    filtered="",
                    result=FilterResult.BLOCKED,
                ), msg
        
        # 4. 速率限制检查
        allowed, msg = self.rate_limiter.check_rate_limit(identifier)
        if not allowed:
            return False, FilteredContent(
                original=content,
                filtered="",
                result=FilterResult.BLOCKED,
            ), msg
        
        # 5. 内容过滤
        filtered = self.content_filter.filter(content, {"identifier": identifier})
        
        if filtered.is_blocked:
            return False, filtered, "内容被安全策略阻止"
        
        return True, filtered, "请求通过安全验证"
    
    def get_security_report(self) -> dict[str, Any]:
        """
        获取安全报告
        
        Returns:
            安全报告字典
        """
        events = self.content_filter.get_security_events(limit=100)
        
        # 统计事件类型
        event_stats: dict[str, int] = defaultdict(int)
        severity_stats: dict[str, int] = defaultdict(int)
        
        for event in events:
            event_stats[event.event_type] += 1
            severity_stats[event.severity] += 1
        
        return {
            "total_security_events": len(events),
            "event_types": dict(event_stats),
            "severity_distribution": dict(severity_stats),
            "recent_events": [
                {
                    "type": e.event_type,
                    "severity": e.severity,
                    "source": e.source,
                    "timestamp": e.timestamp,
                }
                for e in events[-10:]
            ],
            "active_sessions": len(self.validator._sessions),
        }
