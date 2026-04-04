"""
FoxCode 公司模式配置模块

定义公司模式相关的配置模型，包括：
- QQbot 配置
- 安全验证配置
- 内容过滤配置
- 日志记录配置

安全说明：
- 敏感信息（如 API Key、Secret）应通过环境变量配置
- 禁止在配置文件中直接存储敏感信息
"""

from __future__ import annotations

import os
import logging
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


def _get_env_or_default(env_var: str, default: str = "") -> str:
    """
    从环境变量获取敏感配置值
    
    优先从环境变量读取，如果不存在则返回默认值。
    敏感信息应通过环境变量配置，而不是硬编码在配置文件中。
    
    Args:
        env_var: 环境变量名称
        default: 默认值（应为空字符串）
        
    Returns:
        配置值
    """
    value = os.environ.get(env_var, default)
    if not value and default:
        logger.warning(
            f"环境变量 {env_var} 未设置，使用默认值。"
            "建议通过环境变量配置敏感信息。"
        )
    return value


SENSITIVE_ENV_MAPPING = {
    "app_id": "FOXCODE_QQBOT_APP_ID",
    "app_secret": "FOXCODE_QQBOT_APP_SECRET",
    "access_token": "FOXCODE_QQBOT_ACCESS_TOKEN",
    "signature_secret": "FOXCODE_SIGNATURE_SECRET",
}


class CompanyModeStatus(str, Enum):
    """公司模式状态枚举"""
    DISABLED = "disabled"       # 已禁用
    ENABLED = "enabled"         # 已启用
    STARTING = "starting"       # 启动中
    STOPPING = "stopping"       # 停止中
    ERROR = "error"             # 错误状态


class QQbotConfig(BaseModel):
    """
    QQbot 配置模型
    
    配置官方 QQbot API 连接参数
    
    安全说明：
    - app_id、app_secret、access_token 等敏感信息应通过环境变量配置
    - 环境变量名称：FOXCODE_QQBOT_APP_ID, FOXCODE_QQBOT_APP_SECRET, FOXCODE_QQBOT_ACCESS_TOKEN
    - 禁止在配置文件中直接存储这些敏感信息
    """
    # 基础配置（从环境变量读取）
    app_id: str = Field(default="", description="QQ机器人 App ID（建议通过环境变量 FOXCODE_QQBOT_APP_ID 配置）")
    app_secret: str = Field(default="", description="QQ机器人 App Secret（建议通过环境变量 FOXCODE_QQBOT_APP_SECRET 配置）")
    access_token: str = Field(default="", description="访问令牌（建议通过环境变量 FOXCODE_QQBOT_ACCESS_TOKEN 配置）")
    
    @field_validator("app_id", mode="before")
    @classmethod
    def validate_app_id(cls, v: str) -> str:
        """优先从环境变量读取 app_id"""
        env_value = _get_env_or_default(SENSITIVE_ENV_MAPPING["app_id"])
        return env_value if env_value else v
    
    @field_validator("app_secret", mode="before")
    @classmethod
    def validate_app_secret(cls, v: str) -> str:
        """优先从环境变量读取 app_secret"""
        env_value = _get_env_or_default(SENSITIVE_ENV_MAPPING["app_secret"])
        return env_value if env_value else v
    
    @field_validator("access_token", mode="before")
    @classmethod
    def validate_access_token(cls, v: str) -> str:
        """优先从环境变量读取 access_token"""
        env_value = _get_env_or_default(SENSITIVE_ENV_MAPPING["access_token"])
        return env_value if env_value else v
    
    # API 端点配置
    api_base_url: str = Field(
        default="https://api.sgroup.qq.com",
        description="QQbot API 基础 URL"
    )
    sandbox_url: str = Field(
        default="https://sandbox.api.sgroup.qq.com",
        description="沙箱环境 API URL（用于测试）"
    )
    use_sandbox: bool = Field(default=False, description="是否使用沙箱环境")
    
    # 连接配置
    websocket_url: str = Field(
        default="wss://api.sgroup.qq.com/websocket",
        description="WebSocket 连接 URL"
    )
    heartbeat_interval: int = Field(default=30, ge=10, le=120, description="心跳间隔（秒）")
    reconnect_attempts: int = Field(default=5, ge=1, le=10, description="重连尝试次数")
    reconnect_delay: int = Field(default=5, ge=1, le=60, description="重连延迟（秒）")
    
    # 消息配置
    max_message_length: int = Field(default=2000, ge=1, description="最大消息长度")
    message_timeout: int = Field(default=30, ge=5, le=120, description="消息超时时间（秒）")
    
    # 权限配置
    allowed_guilds: list[str] = Field(
        default_factory=list,
        description="允许的频道 ID 列表（为空则允许所有）"
    )
    allowed_channels: list[str] = Field(
        default_factory=list,
        description="允许的子频道 ID 列表（为空则允许所有）"
    )
    admin_users: list[str] = Field(
        default_factory=list,
        description="管理员用户 ID 列表"
    )
    
    def get_effective_api_url(self) -> str:
        """获取有效的 API URL"""
        return self.sandbox_url if self.use_sandbox else self.api_base_url
    
    def is_guild_allowed(self, guild_id: str) -> bool:
        """检查频道是否被允许"""
        if not self.allowed_guilds:
            return True
        return guild_id in self.allowed_guilds
    
    def is_channel_allowed(self, channel_id: str) -> bool:
        """检查子频道是否被允许"""
        if not self.allowed_channels:
            return True
        return channel_id in self.allowed_channels
    
    def is_admin(self, user_id: str) -> bool:
        """检查用户是否为管理员"""
        return user_id in self.admin_users


class SecurityLevel(str, Enum):
    """安全级别枚举"""
    LOW = "low"           # 低安全级别（仅基本过滤）
    MEDIUM = "medium"     # 中等安全级别（推荐）
    HIGH = "high"         # 高安全级别（严格过滤）
    STRICT = "strict"     # 严格模式（最严格过滤）


class ContentFilterConfig(BaseModel):
    """
    内容过滤配置
    
    配置输入输出内容的过滤规则
    """
    # 安全级别
    security_level: SecurityLevel = Field(
        default=SecurityLevel.MEDIUM,
        description="安全级别"
    )
    
    # 敏感词过滤
    enable_sensitive_words: bool = Field(default=True, description="是否启用敏感词过滤")
    sensitive_words: list[str] = Field(
        default_factory=lambda: [
            "密码", "口令", "token", "secret", "key",
            "身份证", "手机号", "银行卡", "信用卡",
        ],
        description="敏感词列表"
    )
    sensitive_word_replacement: str = Field(default="***", description="敏感词替换字符")
    
    # 正则表达式过滤
    enable_regex_filter: bool = Field(default=True, description="是否启用正则过滤")
    blocked_patterns: list[str] = Field(
        default_factory=lambda: [
            r'\b\d{17,19}x?\b',                          # 身份证号
            r'\b1[3-9]\d{9}\b',                          # 手机号
            r'\b\d{16,19}\b',                            # 银行卡号
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',  # 邮箱
            r'(?i)password\s*[=:]\s*\S+',                # 密码赋值
            r'(?i)api[_-]?key\s*[=:]\s*\S+',             # API Key
            r'(?i)secret\s*[=:]\s*\S+',                  # Secret
            r'(?i)token\s*[=:]\s*\S+',                   # Token
        ],
        description="阻止的正则表达式模式"
    )
    
    # 命令注入防护
    enable_command_injection_filter: bool = Field(
        default=True,
        description="是否启用命令注入过滤"
    )
    command_injection_patterns: list[str] = Field(
        default_factory=lambda: [
            r';\s*(rm|del|format|shutdown|reboot)',
            r'\|\s*(rm|del|format|shutdown|reboot)',
            r'`[^`]*`',
            r'\$\([^)]*\)',
            r'\$\{[^}]*\}',
            r'<\([^)]*\)',
        ],
        description="命令注入模式"
    )
    
    # XSS 防护
    enable_xss_filter: bool = Field(default=True, description="是否启用 XSS 过滤")
    xss_patterns: list[str] = Field(
        default_factory=lambda: [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'<iframe[^>]*>',
            r'<object[^>]*>',
            r'<embed[^>]*>',
        ],
        description="XSS 攻击模式"
    )
    
    # 路径穿越防护
    enable_path_traversal_filter: bool = Field(
        default=True,
        description="是否启用路径穿越过滤"
    )
    path_traversal_patterns: list[str] = Field(
        default_factory=lambda: [
            r'\.\./',
            r'\.\.\\',
            r'/etc/',
            r'/var/',
            r'/root/',
            r'\\Windows\\',
            r'\\System32\\',
        ],
        description="路径穿越模式"
    )
    
    # SQL 注入防护
    enable_sql_injection_filter: bool = Field(
        default=True,
        description="是否启用 SQL 注入过滤"
    )
    sql_injection_patterns: list[str] = Field(
        default_factory=lambda: [
            r"(?i)(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE)\b)",
            r"(?i)(\b(UNION|JOIN)\s+\b)",
            r"(?i)(\bWHERE\s+.*\bOR\b.*=)",
            r"(?i)(\bWHERE\s+.*\bAND\b.*=)",
            r"--\s*$",
            r"/\*.*\*/",
            r"(?i)(\bEXEC\b|\bEXECUTE\b)",
        ],
        description="SQL 注入模式"
    )
    
    # URL 过滤
    enable_url_filter: bool = Field(default=True, description="是否启用 URL 过滤")
    allowed_url_schemes: list[str] = Field(
        default_factory=lambda: ["http", "https"],
        description="允许的 URL 协议"
    )
    blocked_domains: list[str] = Field(
        default_factory=lambda: [
            "malware.com",
            "phishing.com",
        ],
        description="阻止的域名列表"
    )
    
    # 文件类型过滤
    enable_file_type_filter: bool = Field(default=True, description="是否启用文件类型过滤")
    allowed_file_extensions: list[str] = Field(
        default_factory=lambda: [
            ".txt", ".md", ".json", ".yaml", ".yml", ".toml",
            ".py", ".js", ".ts", ".java", ".go", ".rs", ".c", ".cpp",
            ".html", ".css", ".xml", ".sql",
            ".png", ".jpg", ".jpeg", ".gif", ".svg",
        ],
        description="允许的文件扩展名"
    )
    
    # 速率限制
    enable_rate_limit: bool = Field(default=True, description="是否启用速率限制")
    max_requests_per_minute: int = Field(default=60, ge=1, description="每分钟最大请求数")
    max_requests_per_hour: int = Field(default=1000, ge=1, description="每小时最大请求数")
    max_message_length: int = Field(default=4000, ge=1, description="最大消息长度")
    
    def get_max_allowed_level(self) -> dict[str, Any]:
        """根据安全级别获取最大允许值"""
        limits = {
            SecurityLevel.LOW: {
                "max_requests_per_minute": 120,
                "max_requests_per_hour": 2000,
                "max_message_length": 8000,
            },
            SecurityLevel.MEDIUM: {
                "max_requests_per_minute": 60,
                "max_requests_per_hour": 1000,
                "max_message_length": 4000,
            },
            SecurityLevel.HIGH: {
                "max_requests_per_minute": 30,
                "max_requests_per_hour": 500,
                "max_message_length": 2000,
            },
            SecurityLevel.STRICT: {
                "max_requests_per_minute": 10,
                "max_requests_per_hour": 200,
                "max_message_length": 1000,
            },
        }
        return limits.get(self.security_level, limits[SecurityLevel.MEDIUM])


class SecurityConfig(BaseModel):
    """
    安全验证配置
    
    配置身份验证和授权机制
    
    安全说明：
    - signature_secret 等敏感信息应通过环境变量配置
    - 环境变量名称：FOXCODE_SIGNATURE_SECRET
    - 禁止在配置文件中直接存储这些敏感信息
    """
    # 身份验证
    enable_authentication: bool = Field(default=True, description="是否启用身份验证")
    auth_timeout: int = Field(default=300, ge=60, description="认证超时时间（秒）")
    session_timeout: int = Field(default=3600, ge=300, description="会话超时时间（秒）")
    
    # 授权配置
    enable_authorization: bool = Field(default=True, description="是否启用授权")
    require_admin_for_sensitive_ops: bool = Field(
        default=True,
        description="敏感操作是否需要管理员权限"
    )
    
    # IP 白名单
    enable_ip_whitelist: bool = Field(default=False, description="是否启用 IP 白名单")
    ip_whitelist: list[str] = Field(
        default_factory=list,
        description="IP 白名单列表"
    )
    
    # 签名验证
    enable_signature_verification: bool = Field(
        default=True,
        description="是否启用签名验证"
    )
    signature_secret: str = Field(default="", description="签名密钥（建议通过环境变量 FOXCODE_SIGNATURE_SECRET 配置）")
    signature_algorithm: str = Field(default="sha256", description="签名算法")
    
    @field_validator("signature_secret", mode="before")
    @classmethod
    def validate_signature_secret(cls, v: str) -> str:
        """优先从环境变量读取 signature_secret"""
        env_value = _get_env_or_default(SENSITIVE_ENV_MAPPING["signature_secret"])
        return env_value if env_value else v
    
    # 审计日志
    enable_audit_log: bool = Field(default=True, description="是否启用审计日志")
    audit_log_retention_days: int = Field(default=90, ge=1, description="审计日志保留天数")
    log_sensitive_operations: bool = Field(default=True, description="是否记录敏感操作")
    
    # 安全事件通知
    enable_security_alerts: bool = Field(default=True, description="是否启用安全告警")
    alert_webhook_url: str = Field(default="", description="告警 Webhook URL")
    alert_email: list[str] = Field(
        default_factory=list,
        description="告警邮箱列表"
    )


class QQbotLogConfig(BaseModel):
    """
    QQbot 日志配置
    
    配置交互日志记录
    
    安全说明：
    - 敏感信息脱敏使用正则匹配和字段名检测双重机制
    - 脱敏后的日志仍可能包含部分敏感信息，建议定期审计
    """
    # 日志开关
    enable_logging: bool = Field(default=True, description="是否启用日志记录")
    log_all_interactions: bool = Field(default=True, description="是否记录所有交互")
    log_security_events: bool = Field(default=True, description="是否记录安全事件")
    
    # 日志存储
    log_dir: str = Field(default=".foxcode/logs/qqbot", description="日志存储目录")
    max_log_file_size: int = Field(default=10 * 1024 * 1024, description="单个日志文件最大大小（字节）")
    max_log_files: int = Field(default=30, ge=1, description="最大日志文件数量")
    log_rotation: str = Field(default="daily", description="日志轮转策略: daily, hourly, size")
    
    # 日志格式
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="日志格式"
    )
    log_level: str = Field(default="INFO", description="日志级别")
    
    # 敏感信息处理
    mask_sensitive_data: bool = Field(default=True, description="是否脱敏敏感数据")
    sensitive_fields: list[str] = Field(
        default_factory=lambda: [
            # 认证相关
            "password", "passwd", "pwd", "pass",
            "token", "access_token", "refresh_token", "auth_token", "bearer_token",
            "secret", "app_secret", "client_secret", "signature_secret",
            "key", "api_key", "api_secret", "private_key", "public_key",
            "credential", "credentials",
            # 个人信息
            "ssn", "social_security_number",
            "credit_card", "card_number", "cvv", "cvc",
            "bank_account", "account_number",
            "id_card", "identity_card",
            # 联系方式
            "email", "phone", "mobile", "telephone",
            "address", "street_address",
            # 其他敏感字段
            "session_id", "session_key",
            "authorization", "auth",
            "cookie", "session",
        ],
        description="敏感字段列表（用于日志脱敏）"
    )
    # 敏感值模式（正则表达式）
    sensitive_patterns: list[str] = Field(
        default_factory=lambda: [
            # 身份证号
            r'\b\d{17,19}[xX]?\b',
            # 手机号
            r'\b1[3-9]\d{9}\b',
            # 银行卡号
            r'\b\d{16,19}\b',
            # 邮箱
            r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',
            # API Key 格式（常见格式）
            r'\b[a-zA-Z0-9_-]{32,}\b',
            # JWT Token
            r'\beyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*\b',
        ],
        description="敏感值正则模式列表（用于日志脱敏）"
    )
    # 脱敏替换字符
    mask_replacement: str = Field(default="***MASKED***", description="敏感信息替换字符")
    
    # 日志导出
    enable_export: bool = Field(default=False, description="是否启用日志导出")
    export_format: str = Field(default="json", description="导出格式: json, csv")
    export_interval: int = Field(default=24, ge=1, description="导出间隔（小时）")


class CompanyModeConfig(BaseModel):
    """
    公司模式配置
    
    整合所有公司模式相关配置
    """
    # 模式状态
    enabled: bool = Field(default=False, description="是否启用公司模式")
    status: CompanyModeStatus = Field(
        default=CompanyModeStatus.DISABLED,
        description="公司模式状态"
    )
    
    # 子配置
    qqbot: QQbotConfig = Field(default_factory=QQbotConfig, description="QQbot 配置")
    content_filter: ContentFilterConfig = Field(
        default_factory=ContentFilterConfig,
        description="内容过滤配置"
    )
    security: SecurityConfig = Field(default_factory=SecurityConfig, description="安全配置")
    logging: QQbotLogConfig = Field(default_factory=QQbotLogConfig, description="日志配置")
    
    # 长期工作模式配置
    long_work_mode: bool = Field(default=False, description="是否启用长期工作模式")
    report_interval: int = Field(default=1, ge=1, description="报告间隔（每个流程完成后）")
    max_concurrent_tasks: int = Field(default=3, ge=1, le=10, description="最大并发任务数")
    
    # 目标子文件夹配置
    target_subfolders: list[str] = Field(
        default_factory=list,
        description="目标子文件夹列表"
    )
    auto_detect_subfolders: bool = Field(
        default=True,
        description="是否自动检测子文件夹"
    )
    
    def is_enabled(self) -> bool:
        """检查公司模式是否启用"""
        return self.enabled and self.status == CompanyModeStatus.ENABLED
    
    def can_start_qqbot(self) -> bool:
        """检查是否可以启动 QQbot"""
        if not self.enabled:
            return False
        if not self.qqbot.app_id or not self.qqbot.app_secret:
            return False
        return True
    
    def get_effective_security_level(self) -> SecurityLevel:
        """获取有效的安全级别"""
        return self.content_filter.security_level
    
    def security_health_check(self) -> dict[str, Any]:
        """
        安全健康检查
        
        检查配置中的安全问题，返回检查结果和建议。
        
        Returns:
            健康检查结果字典，包含：
            - is_healthy: 是否健康
            - issues: 问题列表
            - warnings: 警告列表
            - recommendations: 建议列表
        """
        issues: list[str] = []
        warnings: list[str] = []
        recommendations: list[str] = []
        
        # 检查敏感信息配置
        if not os.environ.get("FOXCODE_QQBOT_APP_ID") and self.qqbot.app_id:
            warnings.append("app_id 未通过环境变量配置，建议使用环境变量 FOXCODE_QQBOT_APP_ID")
        
        if not os.environ.get("FOXCODE_QQBOT_APP_SECRET") and self.qqbot.app_secret:
            issues.append("app_secret 未通过环境变量配置，存在泄露风险")
            recommendations.append("使用环境变量 FOXCODE_QQBOT_APP_SECRET 配置 app_secret")
        
        if not os.environ.get("FOXCODE_SIGNATURE_SECRET") and self.security.signature_secret:
            issues.append("signature_secret 未通过环境变量配置，存在泄露风险")
            recommendations.append("使用环境变量 FOXCODE_SIGNATURE_SECRET 配置签名密钥")
        
        # 检查 IP 白名单
        if not self.security.enable_ip_whitelist:
            warnings.append("IP 白名单未启用，任何 IP 都可以访问")
            recommendations.append("生产环境建议启用 IP 白名单")
        
        # 检查安全级别
        if self.content_filter.security_level == SecurityLevel.LOW:
            warnings.append("安全级别设置为 LOW，安全防护较弱")
            recommendations.append("生产环境建议使用 MEDIUM 或更高级别")
        
        # 检查速率限制
        if not self.content_filter.enable_rate_limit:
            warnings.append("速率限制未启用，可能遭受 DoS 攻击")
            recommendations.append("启用速率限制以防止滥用")
        
        # 检查审计日志
        if not self.security.enable_audit_log:
            warnings.append("审计日志未启用，无法追踪安全事件")
            recommendations.append("启用审计日志以记录安全事件")
        
        # 检查日志脱敏
        if not self.logging.mask_sensitive_data:
            issues.append("日志敏感信息脱敏未启用，可能泄露敏感信息")
            recommendations.append("启用日志敏感信息脱敏")
        
        # 检查会话超时
        if self.security.session_timeout > 7200:  # 2小时
            warnings.append(f"会话超时时间过长 ({self.security.session_timeout}秒)")
            recommendations.append("建议会话超时时间不超过 2 小时")
        
        # 检查签名算法
        if self.security.signature_algorithm not in ["sha256", "sha384", "sha512"]:
            issues.append(f"签名算法 {self.security.signature_algorithm} 不安全")
            recommendations.append("使用 sha256 或更强的签名算法")
        
        return {
            "is_healthy": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "recommendations": recommendations,
            "checks_performed": 10,
            "issues_count": len(issues),
            "warnings_count": len(warnings),
        }
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "enabled": self.enabled,
            "status": self.status.value,
            "qqbot": self.qqbot.model_dump(),
            "content_filter": self.content_filter.model_dump(),
            "security": self.security.model_dump(),
            "logging": self.logging.model_dump(),
            "long_work_mode": self.long_work_mode,
            "report_interval": self.report_interval,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "target_subfolders": self.target_subfolders,
            "auto_detect_subfolders": self.auto_detect_subfolders,
        }
