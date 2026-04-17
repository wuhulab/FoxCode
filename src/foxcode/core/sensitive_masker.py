"""
FoxCode 敏感信息脱敏模块

提供敏感信息检测和脱敏功能，用于：
- 日志输出脱敏
- 配置信息脱敏
- 错误信息脱敏
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SensitivePattern:
    """
    敏感信息模式定义
    
    Attributes:
        name: 模式名称
        pattern: 正则表达式模式
        replacement: 替换字符串
        description: 描述
    """
    name: str
    pattern: re.Pattern
    replacement: str = "***MASKED***"
    description: str = ""


class SensitiveDataMasker:
    """
    敏感数据脱敏器
    
    检测并脱敏各种敏感信息，包括：
    - API Keys
    - 密码
    - Token
    - 身份证号
    - 手机号
    - 银行卡号
    - 邮箱
    - IP 地址
    - 文件路径
    """

    DEFAULT_PATTERNS = [
        SensitivePattern(
            name="api_key_generic",
            pattern=re.compile(
                r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?',
                re.IGNORECASE
            ),
            replacement=r'\1=***API_KEY_MASKED***',
            description="通用 API Key"
        ),
        SensitivePattern(
            name="api_key_bearer",
            pattern=re.compile(
                r'(?i)Bearer\s+([a-zA-Z0-9_\-\.]{20,})',
                re.IGNORECASE
            ),
            replacement=r'Bearer ***TOKEN_MASKED***',
            description="Bearer Token"
        ),
        SensitivePattern(
            name="openai_key",
            pattern=re.compile(
                r'sk-[a-zA-Z0-9]{20,}',
                re.IGNORECASE
            ),
            replacement="sk-***OPENAI_KEY_MASKED***",
            description="OpenAI API Key"
        ),
        SensitivePattern(
            name="anthropic_key",
            pattern=re.compile(
                r'sk-ant-[a-zA-Z0-9\-]{20,}',
                re.IGNORECASE
            ),
            replacement="sk-ant-***ANTHROPIC_KEY_MASKED***",
            description="Anthropic API Key"
        ),
        SensitivePattern(
            name="password",
            pattern=re.compile(
                r'(?i)(password|passwd|pwd)\s*[=:]\s*["\']?([^\s"\']{4,})["\']?',
                re.IGNORECASE
            ),
            replacement=r'\1=***PASSWORD_MASKED***',
            description="密码"
        ),
        SensitivePattern(
            name="secret",
            pattern=re.compile(
                r'(?i)(secret|secret_key|secretkey)\s*[=:]\s*["\']?([a-zA-Z0-9_\-]{8,})["\']?',
                re.IGNORECASE
            ),
            replacement=r'\1=***SECRET_MASKED***',
            description="密钥"
        ),
        SensitivePattern(
            name="token",
            pattern=re.compile(
                r'(?i)(token|access_token|refresh_token|auth_token)\s*[=:]\s*["\']?([a-zA-Z0-9_\-\.]{10,})["\']?',
                re.IGNORECASE
            ),
            replacement=r'\1=***TOKEN_MASKED***',
            description="令牌"
        ),
        SensitivePattern(
            name="id_card_cn",
            pattern=re.compile(
                r'\b[1-9]\d{5}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b'
            ),
            replacement="***ID_CARD_MASKED***",
            description="中国身份证号"
        ),
        SensitivePattern(
            name="phone_cn",
            pattern=re.compile(
                r'\b1[3-9]\d{9}\b'
            ),
            replacement="***PHONE_MASKED***",
            description="中国手机号"
        ),
        SensitivePattern(
            name="bank_card",
            pattern=re.compile(
                r'\b\d{16,19}\b'
            ),
            replacement="***BANK_CARD_MASKED***",
            description="银行卡号"
        ),
        SensitivePattern(
            name="email",
            pattern=re.compile(
                r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'
            ),
            replacement="***EMAIL_MASKED***",
            description="邮箱地址"
        ),
        SensitivePattern(
            name="ip_address",
            pattern=re.compile(
                r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
            ),
            replacement="***IP_MASKED***",
            description="IP 地址"
        ),
        SensitivePattern(
            name="aws_key",
            pattern=re.compile(
                r'(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}',
                re.IGNORECASE
            ),
            replacement="***AWS_KEY_MASKED***",
            description="AWS Access Key"
        ),
        SensitivePattern(
            name="private_key",
            pattern=re.compile(
                r'-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----[\s\S]*?-----END\s+(?:RSA\s+)?PRIVATE\s+KEY-----',
                re.IGNORECASE
            ),
            replacement="***PRIVATE_KEY_MASKED***",
            description="私钥"
        ),
        SensitivePattern(
            name="connection_string",
            pattern=re.compile(
                r'(?i)(mysql|postgres|mongodb|redis)://[^\s<>"\']+(?::[^\s<>"\']*)?@[^\s<>"\']+',
                re.IGNORECASE
            ),
            replacement=r'\1://***USER***:***PASSWORD***@***HOST***/',
            description="数据库连接字符串"
        ),
    ]

    SENSITIVE_FIELD_NAMES = {
        'password', 'passwd', 'pwd', 'secret', 'secret_key', 'secretkey',
        'api_key', 'apikey', 'token', 'access_token', 'refresh_token',
        'auth_token', 'private_key', 'privatekey', 'credential', 'credentials',
        'app_secret', 'appsecret', 'client_secret', 'clientsecret',
        'aws_access_key_id', 'aws_secret_access_key', 'aws_session_token',
        'database_url', 'db_url', 'db_password',
    }

    def __init__(self, custom_patterns: list[SensitivePattern] | None = None):
        """
        初始化敏感数据脱敏器
        
        Args:
            custom_patterns: 自定义敏感信息模式
        """
        self.patterns = self.DEFAULT_PATTERNS.copy()
        if custom_patterns:
            self.patterns.extend(custom_patterns)

    def mask(self, text: str) -> str:
        """
        脱敏文本中的敏感信息
        
        Args:
            text: 原始文本
            
        Returns:
            脱敏后的文本
        """
        if not text:
            return text

        masked_text = text

        for pattern in self.patterns:
            try:
                masked_text = pattern.pattern.sub(pattern.replacement, masked_text)
            except Exception as e:
                logger.debug(f"脱敏模式 {pattern.name} 应用失败: {e}")

        return masked_text

    def mask_dict(self, data: dict[str, Any], depth: int = 0) -> dict[str, Any]:
        """
        脱敏字典中的敏感信息
        
        Args:
            data: 原始字典
            depth: 当前深度（防止无限递归）
            
        Returns:
            脱敏后的字典
        """
        if depth > 10:
            return data

        masked_data = {}

        for key, value in data.items():
            key_lower = key.lower().replace('-', '_').replace(' ', '_')

            if key_lower in self.SENSITIVE_FIELD_NAMES:
                masked_data[key] = "***MASKED***"
            elif isinstance(value, str):
                masked_data[key] = self.mask(value)
            elif isinstance(value, dict):
                masked_data[key] = self.mask_dict(value, depth + 1)
            elif isinstance(value, list):
                masked_data[key] = [
                    self.mask_dict(item, depth + 1) if isinstance(item, dict)
                    else self.mask(item) if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                masked_data[key] = value

        return masked_data

    def mask_path(self, path: str, show_filename: bool = True) -> str:
        """
        脱敏文件路径
        
        Args:
            path: 文件路径
            show_filename: 是否显示文件名
            
        Returns:
            脱敏后的路径
        """
        if not path:
            return path

        try:
            from pathlib import Path
            p = Path(path)

            if show_filename and p.name:
                return f"***PATH***/{p.name}"
            else:
                return "***PATH***"
        except Exception:
            return "***PATH***"

    def detect_sensitive_data(self, text: str) -> list[dict[str, Any]]:
        """
        检测文本中的敏感信息
        
        Args:
            text: 要检测的文本
            
        Returns:
            检测到的敏感信息列表
        """
        detected = []

        for pattern in self.patterns:
            matches = pattern.pattern.findall(text)
            if matches:
                detected.append({
                    "type": pattern.name,
                    "description": pattern.description,
                    "count": len(matches) if isinstance(matches, list) else 1,
                })

        return detected


class SensitiveLogFilter(logging.Filter):
    """
    敏感信息日志过滤器
    
    自动脱敏日志输出中的敏感信息，包括：
    - API Keys、密码、令牌
    - 文件路径
    - IP 地址
    - 个人信息
    """

    PATH_PATTERNS = [
        re.compile(r'[A-Za-z]:\\[^\s<>:"|?*]+', re.IGNORECASE),  # Windows 路径
        re.compile(r'/[^\s<>:"|?*]+/[^\s<>:"|?*]+'),  # Unix 路径
        re.compile(r'~[^\s]*'),  # 用户主目录
        re.compile(r'\.\.?/[^\s]*'),  # 相对路径
    ]

    def __init__(
        self,
        masker: SensitiveDataMasker | None = None,
        mask_paths: bool = True,
        mask_ips: bool = True,
    ):
        """
        初始化日志过滤器
        
        Args:
            masker: 敏感数据脱敏器实例
            mask_paths: 是否脱敏路径
            mask_ips: 是否脱敏 IP 地址
        """
        super().__init__()
        self.masker = masker or SensitiveDataMasker()
        self.mask_paths = mask_paths
        self.mask_ips = mask_ips

    def filter(self, record: logging.LogRecord) -> bool:
        """
        过滤日志记录
        
        Args:
            record: 日志记录
            
        Returns:
            是否通过过滤
        """
        if record.msg and isinstance(record.msg, str):
            record.msg = self._mask_all(record.msg)

        if record.args:
            if isinstance(record.args, dict):
                record.args = self._mask_args_dict(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self._mask_all(arg) if isinstance(arg, str) else arg
                    for arg in record.args
                )

        return True

    def _mask_all(self, text: str) -> str:
        """
        应用所有脱敏规则
        
        Args:
            text: 原始文本
            
        Returns:
            脱敏后的文本
        """
        if not text:
            return text

        text = self.masker.mask(text)

        if self.mask_paths:
            text = self._mask_paths(text)

        return text

    def _mask_paths(self, text: str) -> str:
        """
        脱敏路径
        
        Args:
            text: 原始文本
            
        Returns:
            脱敏后的文本
        """
        for pattern in self.PATH_PATTERNS:
            matches = pattern.findall(text)
            for match in matches:
                try:
                    from pathlib import Path
                    p = Path(match)
                    if p.name:
                        masked = f"***PATH***/{p.name}"
                    else:
                        masked = "***PATH***"
                    text = text.replace(match, masked)
                except Exception:
                    text = text.replace(match, "***PATH***")

        return text

    def _mask_args_dict(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        脱敏字典参数
        
        Args:
            args: 参数字典
            
        Returns:
            脱敏后的字典
        """
        masked = {}
        for key, value in args.items():
            if isinstance(value, str):
                masked[key] = self._mask_all(value)
            elif isinstance(value, dict):
                masked[key] = self.masker.mask_dict(value)
            else:
                masked[key] = value
        return masked


_masker: SensitiveDataMasker | None = None


def get_masker() -> SensitiveDataMasker:
    """
    获取全局敏感数据脱敏器实例
    
    Returns:
        SensitiveDataMasker 实例
    """
    global _masker
    if _masker is None:
        _masker = SensitiveDataMasker()
    return _masker


def mask_sensitive(text: str) -> str:
    """
    脱敏文本中的敏感信息（便捷函数）
    
    Args:
        text: 原始文本
        
    Returns:
        脱敏后的文本
    """
    return get_masker().mask(text)


def mask_sensitive_dict(data: dict[str, Any]) -> dict[str, Any]:
    """
    脱敏字典中的敏感信息（便捷函数）
    
    Args:
        data: 原始字典
        
    Returns:
        脱敏后的字典
    """
    return get_masker().mask_dict(data)


def setup_sensitive_log_filter(
    logger_name: str | None = None,
    masker: SensitiveDataMasker | None = None,
    mask_paths: bool = True,
) -> SensitiveLogFilter:
    """
    为指定日志器设置敏感信息过滤器
    
    Args:
        logger_name: 日志器名称，为 None 则使用根日志器
        masker: 敏感数据脱敏器实例
        mask_paths: 是否脱敏路径
        
    Returns:
        创建的过滤器实例
    """
    log = logging.getLogger(logger_name) if logger_name else logging.getLogger()
    filter_instance = SensitiveLogFilter(masker, mask_paths=mask_paths)
    log.addFilter(filter_instance)
    return filter_instance


def setup_global_log_filter() -> None:
    """
    为所有日志器设置全局敏感信息过滤器
    
    这应该在应用程序启动时调用
    """
    root_logger = logging.getLogger()

    for handler in root_logger.handlers:
        if not any(isinstance(f, SensitiveLogFilter) for f in handler.filters):
            handler.addFilter(SensitiveLogFilter())

    if not any(isinstance(f, SensitiveLogFilter) for f in root_logger.filters):
        root_logger.addFilter(SensitiveLogFilter())

    for name in logging.root.manager.loggerDict:
        logger_instance = logging.getLogger(name)
        if not any(isinstance(f, SensitiveLogFilter) for f in logger_instance.filters):
            logger_instance.addFilter(SensitiveLogFilter())
