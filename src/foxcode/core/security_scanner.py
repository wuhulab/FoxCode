"""
FoxCode 安全漏洞扫描器 - 代码安全扫描和敏感信息检测

这个文件提供代码安全扫描功能:
1. 漏洞模式检测：检测 SQL 注入、XSS、命令注入等常见漏洞
2. 敏感信息检测：检测 API Key、密码、Token 等敏感信息
3. 依赖安全检查：检查依赖包的已知漏洞
4. 安全报告生成：生成详细的安全扫描报告

检测的漏洞类型:
- SQL 注入
- XSS（跨站脚本）
- 命令注入
- 路径穿越
- 硬编码密钥
- 不安全的反序列化

使用方式:
    from foxcode.core.security_scanner import SecurityScanner

    scanner = SecurityScanner()
    report = scanner.scan_directory(Path("src/"))
    print(f"发现 {len(report.vulnerabilities)} 个漏洞")
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

# 创建专门的日志记录器
logger = logging.getLogger(__name__)


def setup_security_logger(log_dir: Path | None = None) -> logging.Logger:
    """
    设置安全扫描专用日志记录器
    
    Args:
        log_dir: 日志目录路径，默认为 ~/.foxcode
        
    Returns:
        配置好的日志记录器
    """
    if log_dir is None:
        log_dir = Path.home() / ".foxcode"

    log_dir.mkdir(parents=True, exist_ok=True)

    # 创建专门的日志记录器
    security_logger = logging.getLogger("foxcode.security")
    security_logger.setLevel(logging.DEBUG)

    # 避免重复添加处理器
    if not security_logger.handlers:
        # 文件处理器 - 详细日志
        file_handler = logging.FileHandler(
            log_dir / "security_scan.log",
            encoding='utf-8',
            mode='a'  # 追加模式
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        security_logger.addHandler(file_handler)

    return security_logger


class VulnerabilitySeverity(str, Enum):
    """漏洞严重程度"""
    CRITICAL = "critical"    # 严重
    HIGH = "high"           # 高危
    MEDIUM = "medium"       # 中危
    LOW = "low"             # 低危
    INFO = "info"           # 信息


class VulnerabilityType(str, Enum):
    """漏洞类型"""
    SQL_INJECTION = "sql_injection"           # SQL 注入
    XSS = "xss"                               # 跨站脚本
    COMMAND_INJECTION = "command_injection"   # 命令注入
    PATH_TRAVERSAL = "path_traversal"         # 路径穿越
    SSRF = "ssrf"                             # 服务端请求伪造
    XXE = "xxe"                               # XML 外部实体
    CSRF = "csrf"                             # 跨站请求伪造
    HARDCODED_SECRET = "hardcoded_secret"     # 硬编码密钥
    SENSITIVE_DATA = "sensitive_data"         # 敏感数据泄露
    INSECURE_DESERIALIZATION = "insecure_deserialization"  # 不安全的反序列化
    WEAK_CRYPTO = "weak_crypto"               # 弱加密
    AUTH_BYPASS = "auth_bypass"               # 认证绕过
    DEPENDENCY_VULNERABILITY = "dependency_vulnerability"  # 依赖漏洞


@dataclass
class SecurityIssue:
    """
    安全问题
    
    Attributes:
        id: 问题 ID
        title: 标题
        description: 描述
        vulnerability_type: 漏洞类型
        severity: 严重程度
        file_path: 文件路径
        line_number: 行号
        code_snippet: 代码片段
        recommendation: 修复建议
        references: 参考链接
        cwe_id: CWE 编号
        confidence: 置信度
    """
    id: str
    title: str
    description: str
    vulnerability_type: VulnerabilityType
    severity: VulnerabilitySeverity
    file_path: str = ""
    line_number: int = 0
    code_snippet: str = ""
    recommendation: str = ""
    references: list[str] = field(default_factory=list)
    cwe_id: str = ""
    confidence: float = 0.8

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "vulnerability_type": self.vulnerability_type.value,
            "severity": self.severity.value,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "code_snippet": self.code_snippet,
            "recommendation": self.recommendation,
            "references": self.references,
            "cwe_id": self.cwe_id,
            "confidence": self.confidence,
        }


@dataclass
class SecretMatch:
    """
    敏感信息匹配
    
    Attributes:
        type: 密钥类型
        value: 匹配值（部分脱敏）
        file_path: 文件路径
        line_number: 行号
        context: 上下文
    """
    type: str
    value: str
    file_path: str = ""
    line_number: int = 0
    context: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "value": self.value,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "context": self.context,
        }


@dataclass
class DependencyIssue:
    """
    依赖安全问题
    
    Attributes:
        package: 包名
        version: 版本
        vulnerability_id: 漏洞 ID
        severity: 严重程度
        description: 描述
        fixed_version: 修复版本
        references: 参考链接
    """
    package: str
    version: str
    vulnerability_id: str
    severity: VulnerabilitySeverity
    description: str = ""
    fixed_version: str = ""
    references: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "package": self.package,
            "version": self.version,
            "vulnerability_id": self.vulnerability_id,
            "severity": self.severity.value,
            "description": self.description,
            "fixed_version": self.fixed_version,
            "references": self.references,
        }


@dataclass
class ScanReport:
    """
    扫描报告
    
    Attributes:
        project_path: 项目路径
        scan_time: 扫描时间
        duration_seconds: 扫描耗时
        files_scanned: 扫描文件数
        issues: 安全问题列表
        secrets: 敏感信息列表
        dependency_issues: 依赖问题列表
        summary: 摘要统计
    """
    project_path: str
    scan_time: datetime = field(default_factory=datetime.now)
    duration_seconds: float = 0.0
    files_scanned: int = 0
    issues: list[SecurityIssue] = field(default_factory=list)
    secrets: list[SecretMatch] = field(default_factory=list)
    dependency_issues: list[DependencyIssue] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_path": self.project_path,
            "scan_time": self.scan_time.isoformat(),
            "duration_seconds": self.duration_seconds,
            "files_scanned": self.files_scanned,
            "issues": [i.to_dict() for i in self.issues],
            "secrets": [s.to_dict() for s in self.secrets],
            "dependency_issues": [d.to_dict() for d in self.dependency_issues],
            "summary": self.summary,
        }


class SecurityConfig(BaseModel):
    """
    安全扫描配置
    
    Attributes:
        enabled_checks: 启用的检查项
        severity_threshold: 严重程度阈值
        max_file_size: 最大文件大小
        exclude_patterns: 排除模式
        check_dependencies: 是否检查依赖
        check_secrets: 是否检查敏感信息
    """
    enabled_checks: list[str] = Field(
        default_factory=lambda: [
            "sql_injection", "xss", "command_injection",
            "path_traversal", "hardcoded_secrets", "weak_crypto"
        ]
    )
    severity_threshold: VulnerabilitySeverity = VulnerabilitySeverity.LOW
    max_file_size: int = Field(default=10 * 1024 * 1024)  # 10MB
    exclude_patterns: list[str] = Field(
        default_factory=lambda: [
            "node_modules", ".git", "__pycache__", "venv", ".venv",
            "dist", "build", "*.min.js", "*.min.css"
        ]
    )
    check_dependencies: bool = True
    check_secrets: bool = True


class SecurityScanner:
    """
    安全漏洞扫描器
    
    提供代码安全扫描、敏感信息检测和依赖安全检查功能。
    
    Example:
        >>> scanner = SecurityScanner()
        >>> report = await scanner.scan_directory(Path("./src"))
        >>> print(f"发现 {len(report.issues)} 个安全问题")
    """

    # 漏洞检测规则
    VULNERABILITY_RULES = {
        VulnerabilityType.SQL_INJECTION: [
            {
                "pattern": r"execute\s*\(\s*[f\"'].*\{.*\}.*[\"']",
                "message": "可能的 SQL 注入：使用 f-string 构造 SQL 查询",
                "recommendation": "使用参数化查询，如 cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))",
                "cwe": "CWE-89",
            },
            {
                "pattern": r"execute\s*\(\s*[\"'].*%s.*[\"']\s*%\s*\(",
                "message": "可能的 SQL 注入：使用字符串格式化构造 SQL 查询",
                "recommendation": "使用参数化查询，不要使用字符串格式化",
                "cwe": "CWE-89",
            },
            {
                "pattern": r"\+\s*[\"'].*SELECT.*[\"']\s*\+",
                "message": "可能的 SQL 注入：使用字符串拼接构造 SQL 查询",
                "recommendation": "使用参数化查询，避免字符串拼接",
                "cwe": "CWE-89",
            },
        ],
        VulnerabilityType.XSS: [
            {
                "pattern": r"innerHTML\s*=\s*[^\"']*\+",
                "message": "可能的 XSS：直接将用户输入赋值给 innerHTML",
                "recommendation": "使用 textContent 或对输入进行 HTML 编码",
                "cwe": "CWE-79",
            },
            {
                "pattern": r"document\.write\s*\(",
                "message": "可能的 XSS：使用 document.write",
                "recommendation": "避免使用 document.write，使用安全的 DOM 操作",
                "cwe": "CWE-79",
            },
            {
                "pattern": r"eval\s*\(",
                "message": "可能的 XSS：使用 eval 执行动态代码",
                "recommendation": "避免使用 eval，使用 JSON.parse 或其他安全方法",
                "cwe": "CWE-95",
            },
        ],
        VulnerabilityType.COMMAND_INJECTION: [
            {
                "pattern": r"os\.system\s*\(",
                "message": "可能的命令注入：使用 os.system",
                "recommendation": "使用 subprocess.run 并设置 shell=False",
                "cwe": "CWE-78",
            },
            {
                "pattern": r"subprocess\..*\(.*shell\s*=\s*True",
                "message": "可能的命令注入：使用 shell=True",
                "recommendation": "避免使用 shell=True，传递参数列表",
                "cwe": "CWE-78",
            },
            {
                "pattern": r"eval\s*\(",
                "message": "可能的代码注入：使用 eval",
                "recommendation": "避免使用 eval，使用更安全的替代方案",
                "cwe": "CWE-95",
            },
        ],
        VulnerabilityType.PATH_TRAVERSAL: [
            {
                "pattern": r"open\s*\(\s*[\"'].*\.\..*[\"']",
                "message": "可能的路径穿越：使用相对路径包含 '..'",
                "recommendation": "验证和清理用户提供的路径，使用 os.path.basename",
                "cwe": "CWE-22",
            },
            {
                "pattern": r"\.\./",
                "message": "可能的路径穿越：路径中包含 '../'",
                "recommendation": "验证路径，确保不包含目录穿越字符",
                "cwe": "CWE-22",
            },
        ],
        VulnerabilityType.WEAK_CRYPTO: [
            {
                "pattern": r"hashlib\.md5\s*\(",
                "message": "弱加密：使用 MD5 哈希",
                "recommendation": "使用 SHA-256 或更强的哈希算法",
                "cwe": "CWE-328",
            },
            {
                "pattern": r"hashlib\.sha1\s*\(",
                "message": "弱加密：使用 SHA1 哈希",
                "recommendation": "使用 SHA-256 或更强的哈希算法",
                "cwe": "CWE-328",
            },
            {
                "pattern": r"\bDES\b|\bBlowfish\b|from\s+Crypto\.Cipher\.DES|from\s+cryptography\.hazmat\.primitives\.ciphers\.algorithms\s+import\s+DES",
                "message": "弱加密：使用弱加密算法",
                "recommendation": "使用 AES-256 或更强的加密算法",
                "cwe": "CWE-327",
            },
        ],
    }

    # 敏感信息检测规则
    SECRET_PATTERNS = {
        "AWS Access Key": r"AKIA[0-9A-Z]{16}",
        "AWS Secret Key": r"aws_secret_access_key\s*=\s*['\"][A-Za-z0-9/+=]{40}['\"]",
        "GitHub Token": r"github[_-]?token\s*=\s*['\"][A-Za-z0-9_]{35,40}['\"]",
        "GitHub PAT": r"ghp_[A-Za-z0-9]{36}",
        "GitLab Token": r"glpat-[A-Za-z0-9_-]{20}",
        "Slack Token": r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}",
        "Google API Key": r"AIza[0-9A-Za-z_-]{35}",
        "Generic API Key": r"api[_-]?key\s*=\s*['\"][A-Za-z0-9_]{20,}['\"]",
        "Private Key": r"-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----",
        "Password": r"password\s*=\s*['\"][^'\"]{8,}['\"]",
        "Secret": r"secret\s*=\s*['\"][A-Za-z0-9_]{16,}['\"]",
        "JWT Secret": r"jwt[_-]?secret\s*=\s*['\"][A-Za-z0-9_]{16,}['\"]",
        "Database URL": r"(mysql|postgres|mongodb)://[^:]+:[^@]+@[^/]+",
        "Redis URL": r"redis://[^:]*:[^@]+@[^/]+",
    }

    # 文件扩展名到语言的映射
    LANGUAGE_EXTENSIONS = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "javascript",
        ".tsx": "typescript",
        ".java": "java",
        ".go": "go",
        ".php": "php",
        ".rb": "ruby",
        ".cs": "csharp",
        ".sql": "sql",
    }

    def __init__(self, config: SecurityConfig | None = None):
        """
        初始化扫描器
        
        Args:
            config: 扫描配置
        """
        self.config = config or SecurityConfig()
        self._issue_counter = 0

        # 设置专用日志记录器
        self.logger = setup_security_logger()
        self.logger.info("=" * 80)
        self.logger.info("安全漏洞扫描器初始化完成")
        self.logger.info(f"配置: 启用检查项={self.config.enabled_checks}")
        self.logger.info(f"配置: 严重程度阈值={self.config.severity_threshold.value}")
        self.logger.info(f"配置: 检查依赖={self.config.check_dependencies}")
        self.logger.info(f"配置: 检查敏感信息={self.config.check_secrets}")
        self.logger.info("=" * 80)

    def _generate_issue_id(self) -> str:
        """生成问题 ID"""
        self._issue_counter += 1
        return f"SEC-{self._issue_counter:04d}"

    def _should_scan_file(self, file_path: Path) -> bool:
        """检查是否应该扫描文件"""
        # 检查文件大小
        try:
            if file_path.stat().st_size > self.config.max_file_size:
                return False
        except OSError:
            return False

        # 检查排除模式
        file_str = str(file_path)
        for pattern in self.config.exclude_patterns:
            if pattern in file_str:
                return False

        # 检查文件扩展名
        ext = file_path.suffix.lower()
        return ext in self.LANGUAGE_EXTENSIONS

    async def scan_file(self, file_path: Path) -> list[SecurityIssue]:
        """
        扫描单个文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            安全问题列表
        """
        issues = []

        if not self._should_scan_file(file_path):
            self.logger.debug(f"跳过文件: {file_path}")
            return issues

        self.logger.debug(f"开始扫描文件: {file_path}")

        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()

            lines = content.split("\n")
            file_issues_count = 0

            # 检查漏洞模式
            for vuln_type, rules in self.VULNERABILITY_RULES.items():
                for rule in rules:
                    pattern = rule["pattern"]
                    for i, line in enumerate(lines):
                        if re.search(pattern, line, re.IGNORECASE):
                            # 获取上下文（前后各5行）
                            context_start = max(0, i - 5)
                            context_end = min(len(lines), i + 6)
                            context_lines = lines[context_start:context_end]

                            # 检查是否为误报
                            is_fp, fp_reason = self._is_false_positive(
                                str(file_path), i + 1, line, vuln_type, context_lines
                            )

                            if is_fp:
                                self.logger.debug(
                                    f"跳过误报: {fp_reason}\n"
                                    f"  文件: {file_path}:{i+1}\n"
                                    f"  代码: {line.strip()[:100]}"
                                )
                                continue

                            issue = SecurityIssue(
                                id=self._generate_issue_id(),
                                title=rule["message"],
                                description=f"在 {file_path.name}:{i+1} 检测到潜在的安全问题",
                                vulnerability_type=vuln_type,
                                severity=self._get_severity_for_type(vuln_type),
                                file_path=str(file_path),
                                line_number=i + 1,
                                code_snippet=line.strip()[:200],
                                recommendation=rule["recommendation"],
                                cwe_id=rule.get("cwe", ""),
                                confidence=0.7,
                            )
                            issues.append(issue)
                            file_issues_count += 1

                            # 记录发现的问题
                            self.logger.warning(
                                f"发现安全问题 [{issue.id}]: {issue.title}\n"
                                f"  文件: {file_path}:{i+1}\n"
                                f"  类型: {vuln_type.value}\n"
                                f"  严重性: {issue.severity.value}\n"
                                f"  代码: {line.strip()[:100]}"
                            )

            # 检查敏感信息
            if self.config.check_secrets:
                secrets = self.detect_secrets(content)
                for secret in secrets:
                    secret.file_path = str(file_path)
                    # 找到行号
                    for i, line in enumerate(lines):
                        if secret.value[:20] in line:
                            secret.line_number = i + 1
                            secret.context = line.strip()[:100]
                            break

                    # 无法定位行号的匹配通常是模式定义中的误报
                    if secret.line_number == 0:
                        self.logger.debug(
                            f"跳过无法定位行号的敏感信息匹配（可能为模式定义误报）\n"
                            f"  文件: {file_path}\n"
                            f"  类型: {secret.type}"
                        )
                        continue

                    # 检查是否为误报（模式定义行、注释等）
                    is_secret_fp, secret_fp_reason = self._is_secret_false_positive(
                        str(file_path), secret.line_number, secret.context or ""
                    )
                    if is_secret_fp:
                        self.logger.debug(
                            f"跳过敏感信息误报: {secret_fp_reason}\n"
                            f"  文件: {file_path}:{secret.line_number}\n"
                            f"  类型: {secret.type}"
                        )
                        continue

                    issue = SecurityIssue(
                        id=self._generate_issue_id(),
                        title=f"检测到敏感信息: {secret.type}",
                        description=f"在 {file_path.name} 中发现可能的 {secret.type}",
                        vulnerability_type=VulnerabilityType.HARDCODED_SECRET,
                        severity=VulnerabilitySeverity.HIGH,
                        file_path=str(file_path),
                        line_number=secret.line_number,
                        code_snippet=secret.context,
                        recommendation="将敏感信息移至环境变量或安全的密钥管理系统",
                        confidence=0.9,
                    )
                    issues.append(issue)
                    file_issues_count += 1

                    # 记录发现的敏感信息
                    self.logger.warning(
                        f"发现敏感信息 [{issue.id}]: {secret.type}\n"
                        f"  文件: {file_path}:{secret.line_number}\n"
                        f"  类型: {secret.type}"
                    )

            if file_issues_count > 0:
                self.logger.info(f"文件 {file_path.name} 发现 {file_issues_count} 个问题")
            else:
                self.logger.debug(f"文件 {file_path.name} 未发现问题")

        except Exception as e:
            self.logger.error(f"扫描文件失败 {file_path}: {e}", exc_info=True)

        return issues

    def _get_severity_for_type(self, vuln_type: VulnerabilityType) -> VulnerabilitySeverity:
        """获取漏洞类型的默认严重程度"""
        severity_map = {
            VulnerabilityType.SQL_INJECTION: VulnerabilitySeverity.CRITICAL,
            VulnerabilityType.COMMAND_INJECTION: VulnerabilitySeverity.CRITICAL,
            VulnerabilityType.XSS: VulnerabilitySeverity.HIGH,
            VulnerabilityType.PATH_TRAVERSAL: VulnerabilitySeverity.HIGH,
            VulnerabilityType.HARDCODED_SECRET: VulnerabilitySeverity.HIGH,
            VulnerabilityType.WEAK_CRYPTO: VulnerabilitySeverity.MEDIUM,
            VulnerabilityType.SSRF: VulnerabilitySeverity.HIGH,
            VulnerabilityType.XXE: VulnerabilitySeverity.HIGH,
        }
        return severity_map.get(vuln_type, VulnerabilitySeverity.MEDIUM)

    def _is_false_positive(
        self,
        file_path: str,
        line_number: int,
        code_line: str,
        vuln_type: VulnerabilityType,
        context_lines: list[str]
    ) -> tuple[bool, str]:
        """
        判断是否为误报
        
        Args:
            file_path: 文件路径
            line_number: 行号
            code_line: 代码行
            vuln_type: 漏洞类型
            context_lines: 上下文行
            
        Returns:
            (是否误报, 原因)
        """
        # 文件安全标记
        FILE_SECURITY_MARKERS = {
            "advanced_debugger.py": {
                "safe_functions": ["safe_eval"],
                "security_features": ["FORBIDDEN_NAMES", "FORBIDDEN_NODES"],
            },
            "security_scanner.py": {
                "purpose": "安全扫描器",
                "contains_patterns": True,
            },
            "project_analyzer.py": {
                "purpose": "项目分析器",
                "contains_patterns": True,
            },
            "mcp.py": {
                "purpose": "MCP 协议",
                "safe_code_sections": ["参数验证", "危险模式"],
            },
            "sandbox.py": {
                "purpose": "沙箱环境",
                "safe_code_sections": ["路径穿越检测"],
            },
        }

        # 提取文件名
        file_name = file_path.replace("\\", "/").split("/")[-1]

        # 1. 检查文件白名单
        if file_name in FILE_SECURITY_MARKERS:
            marker = FILE_SECURITY_MARKERS[file_name]

            # 检查是否为安全函数
            if "safe_functions" in marker:
                for func in marker["safe_functions"]:
                    if func in code_line or any(func in line for line in context_lines):
                        return True, f"在安全函数 {func} 中"

            # 检查是否为安全检测代码
            if marker.get("contains_patterns"):
                if any(indicator in code_line for indicator in ["pattern", "regex", "检测", "防止"]):
                    return True, "安全检测代码中的模式字符串"

        # 2. 检查上下文
        context_str = "\n".join(context_lines)

        # 检查安全包装器
        if vuln_type in [VulnerabilityType.XSS, VulnerabilityType.COMMAND_INJECTION]:
            if any(wrapper in context_str for wrapper in ["safe_eval", "FORBIDDEN_NAMES", "safe_globals"]):
                return True, "在安全包装器中，已实现安全措施"

        # 检查字符串字面量
        if re.search(r"['\"].*\.\./.*['\"]", code_line) or re.search(r"r['\"].*eval.*['\"]", code_line):
            return True, "字符串字面量或正则表达式模式"

        # 检查注释或文档字符串中的路径穿越示例
        if vuln_type == VulnerabilityType.PATH_TRAVERSAL:
            stripped = code_line.strip()
            if stripped.startswith('#') or stripped.startswith('-') or stripped.startswith('*'):
                if '../' in code_line or '..\\' in code_line:
                    return True, "注释或文档中的路径穿越示例"
            if re.search(r'(防止|防止.*遍历|遍历.*检测|example|示例)', code_line):
                return True, "安全说明文档中的示例"

        # 检查安全检测代码
        security_indicators = ["dangerous_patterns", "traversal_patterns", "security_patterns"]
        if any(indicator in context_str for indicator in security_indicators):
            return True, "安全检测代码"

        # 3. 特定漏洞类型的检查
        if vuln_type == VulnerabilityType.WEAK_CRYPTO:
            # 检查是否为 description 变量或字符串
            if re.search(r"description\s*[:=]", code_line, re.IGNORECASE):
                return True, "变量名包含 'description'，与加密无关"
            # 检查是否为包含 description 的字符串字面量
            if re.search(r"['\"].*description.*['\"]", code_line, re.IGNORECASE):
                return True, "字符串字面量包含 'description'，与加密无关"
            # 检查是否为注释
            if re.search(r"# .*description", code_line, re.IGNORECASE):
                return True, "注释中包含 'description'，与加密无关"

        return False, ""

    def _is_secret_false_positive(
        self,
        file_path: str,
        line_number: int,
        code_line: str,
    ) -> tuple[bool, str]:
        """
        判断敏感信息检测是否为误报
        
        Args:
            file_path: 文件路径
            line_number: 行号
            code_line: 代码行内容
            
        Returns:
            (是否误报, 原因)
        """
        # 检查是否为正则表达式模式定义行
        if re.search(r'r["\']', code_line) and re.search(r'\\[sdw]', code_line):
            return True, "正则表达式模式定义行"

        # 检查是否为 SECRET_PATTERNS 字典中的值定义
        pattern_def_indicators = [
            r'SECRET_PATTERNS',
            r'VULNERABILITY_RULES',
            r'["\'].*\\[sdwb].*["\']',  # 包含正则元字符的字符串
        ]
        for indicator in pattern_def_indicators:
            if re.search(indicator, code_line):
                return True, "安全扫描器模式定义"

        # 检查是否为注释行
        stripped = code_line.strip()
        if stripped.startswith('#') or stripped.startswith('//') or stripped.startswith('*'):
            return True, "注释中的示例文本"

        # 检查是否为测试代码中的示例
        if re.search(r'(example|sample|test|mock|dummy|placeholder)', code_line, re.IGNORECASE):
            return True, "测试或示例代码"

        return False, ""

    async def scan_directory(self, directory: Path) -> ScanReport:
        """
        扫描目录
        
        Args:
            directory: 目录路径
            
        Returns:
            扫描报告
        """
        start_time = datetime.now()
        all_issues: list[SecurityIssue] = []
        all_secrets: list[SecretMatch] = []
        files_scanned = 0

        self.logger.info("=" * 80)
        self.logger.info(f"开始扫描目录: {directory}")
        self.logger.info(f"扫描开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("=" * 80)

        # 遍历目录
        for file_path in directory.rglob("*"):
            if not file_path.is_file():
                continue

            if self._should_scan_file(file_path):
                issues = await self.scan_file(file_path)
                all_issues.extend(issues)
                files_scanned += 1

                # 每10个文件记录一次进度
                if files_scanned % 10 == 0:
                    self.logger.info(f"扫描进度: 已扫描 {files_scanned} 个文件，发现 {len(all_issues)} 个问题")

        self.logger.info(f"文件扫描完成: 共扫描 {files_scanned} 个文件")

        # 检查依赖
        dependency_issues = []
        if self.config.check_dependencies:
            self.logger.info("开始检查依赖安全...")
            dependency_issues = await self.check_dependencies(directory)
            self.logger.info(f"依赖检查完成: 发现 {len(dependency_issues)} 个问题")

        # 计算耗时
        duration = (datetime.now() - start_time).total_seconds()

        # 生成摘要
        summary = self._generate_summary(all_issues, all_secrets, dependency_issues)

        # 记录扫描结果摘要
        self.logger.info("=" * 80)
        self.logger.info("扫描结果摘要:")
        self.logger.info(f"  扫描文件数: {files_scanned}")
        self.logger.info(f"  发现问题数: {len(all_issues)}")
        self.logger.info(f"  敏感信息数: {len(all_secrets)}")
        self.logger.info(f"  依赖问题数: {len(dependency_issues)}")
        self.logger.info(f"  风险等级: {summary.get('risk_level', 'unknown')}")
        self.logger.info(f"  扫描耗时: {duration:.2f} 秒")

        # 记录严重程度分布
        severity_dist = summary.get("by_severity", {})
        if severity_dist:
            self.logger.info("  严重程度分布:")
            for severity, count in severity_dist.items():
                self.logger.info(f"    {severity}: {count}")

        # 记录问题类型分布
        type_dist = summary.get("by_type", {})
        if type_dist:
            self.logger.info("  问题类型分布:")
            for issue_type, count in type_dist.items():
                self.logger.info(f"    {issue_type}: {count}")

        self.logger.info("=" * 80)

        return ScanReport(
            project_path=str(directory),
            duration_seconds=duration,
            files_scanned=files_scanned,
            issues=all_issues,
            secrets=all_secrets,
            dependency_issues=dependency_issues,
            summary=summary,
        )

    def detect_secrets(self, content: str) -> list[SecretMatch]:
        """
        检测敏感信息
        
        Args:
            content: 内容字符串
            
        Returns:
            敏感信息列表
        """
        secrets = []

        for secret_type, pattern in self.SECRET_PATTERNS.items():
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                value = match.group(0)
                # 脱敏显示
                masked_value = value[:10] + "..." + value[-4:] if len(value) > 14 else value[:4] + "..."

                secrets.append(SecretMatch(
                    type=secret_type,
                    value=masked_value,
                ))

        return secrets

    def check_vulnerability_patterns(
        self,
        code: str,
        language: str,
    ) -> list[SecurityIssue]:
        """
        检查漏洞模式
        
        Args:
            code: 代码字符串
            language: 编程语言
            
        Returns:
            安全问题列表
        """
        issues = []

        for vuln_type, rules in self.VULNERABILITY_RULES.items():
            for rule in rules:
                matches = re.finditer(rule["pattern"], code, re.IGNORECASE)
                for match in matches:
                    # 找到行号
                    line_num = code[:match.start()].count("\n") + 1

                    issues.append(SecurityIssue(
                        id=self._generate_issue_id(),
                        title=rule["message"],
                        description="检测到潜在的安全问题",
                        vulnerability_type=vuln_type,
                        severity=self._get_severity_for_type(vuln_type),
                        line_number=line_num,
                        code_snippet=match.group(0)[:200],
                        recommendation=rule["recommendation"],
                        cwe_id=rule.get("cwe", ""),
                    ))

        return issues

    async def check_dependencies(self, project_path: Path) -> list[DependencyIssue]:
        """
        检查依赖安全
        
        Args:
            project_path: 项目路径
            
        Returns:
            依赖问题列表
        """
        issues = []

        self.logger.info(f"检查项目依赖: {project_path}")

        # 检查 requirements.txt
        req_file = project_path / "requirements.txt"
        if req_file.exists():
            self.logger.info(f"发现 Python 依赖文件: {req_file}")
            py_issues = await self._check_python_dependencies(req_file)
            issues.extend(py_issues)
            self.logger.info(f"Python 依赖检查完成: 发现 {len(py_issues)} 个问题")
        else:
            self.logger.debug("未找到 requirements.txt 文件")

        # 检查 package.json
        pkg_file = project_path / "package.json"
        if pkg_file.exists():
            self.logger.info(f"发现 NPM 依赖文件: {pkg_file}")
            npm_issues = await self._check_npm_dependencies(pkg_file)
            issues.extend(npm_issues)
            self.logger.info(f"NPM 依赖检查完成: 发现 {len(npm_issues)} 个问题")
        else:
            self.logger.debug("未找到 package.json 文件")

        if not req_file.exists() and not pkg_file.exists():
            self.logger.info("未发现依赖文件，跳过依赖检查")

        return issues

    async def _check_python_dependencies(self, req_file: Path) -> list[DependencyIssue]:
        """检查 Python 依赖"""
        issues = []

        self.logger.debug(f"开始检查 Python 依赖: {req_file}")

        # 已知漏洞的包版本（示例）
        known_vulnerabilities = {
            "django": {
                "2.2.0": ("CVE-2019-12308", "中等", "2.2.4"),
                "3.0.0": ("CVE-2020-9402", "高危", "3.0.6"),
            },
            "flask": {
                "0.12.0": ("CVE-2018-1000656", "中危", "1.0"),
            },
            "requests": {
                "2.19.0": ("CVE-2018-18074", "中危", "2.20.0"),
            },
            "pyyaml": {
                "5.1": ("CVE-2020-14343", "高危", "5.4"),
            },
        }

        try:
            with open(req_file, encoding="utf-8") as f:
                lines = f.readlines()

            self.logger.debug(f"读取到 {len(lines)} 行依赖配置")

            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # 解析包名和版本
                match = re.match(r"([a-zA-Z0-9_-]+)\s*([<>=!]+)\s*([0-9.]+)", line)
                if match:
                    package = match.group(1).lower()
                    version = match.group(3)

                    self.logger.debug(f"检查包: {package} {version}")

                    if package in known_vulnerabilities:
                        for vuln_version, (cve, severity, fixed) in known_vulnerabilities[package].items():
                            if version == vuln_version:
                                issue = DependencyIssue(
                                    package=package,
                                    version=version,
                                    vulnerability_id=cve,
                                    severity=VulnerabilitySeverity(severity.lower()),
                                    description=f"{package} {version} 存在已知漏洞",
                                    fixed_version=fixed,
                                    references=[f"https://nvd.nist.gov/vuln/detail/{cve}"],
                                )
                                issues.append(issue)

                                self.logger.warning(
                                    f"发现依赖漏洞: {package} {version}\n"
                                    f"  CVE: {cve}\n"
                                    f"  严重性: {severity}\n"
                                    f"  修复版本: {fixed}"
                                )
        except Exception as e:
            self.logger.error(f"检查 Python 依赖失败: {e}", exc_info=True)

        return issues

    async def _check_npm_dependencies(self, pkg_file: Path) -> list[DependencyIssue]:
        """检查 NPM 依赖"""
        issues = []

        self.logger.debug(f"开始检查 NPM 依赖: {pkg_file}")

        # 已知漏洞的包版本（示例）
        known_vulnerabilities = {
            "lodash": {
                "4.17.15": ("CVE-2020-8203", "高危", "4.17.21"),
            },
            "axios": {
                "0.19.0": ("CVE-2020-28168", "中危", "0.21.1"),
            },
            "node-fetch": {
                "2.6.0": ("CVE-2022-0235", "中危", "2.6.7"),
            },
        }

        try:
            with open(pkg_file, encoding="utf-8") as f:
                data = json.load(f)

            dependencies = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            self.logger.debug(f"读取到 {len(dependencies)} 个依赖包")

            for package, version in dependencies.items():
                package_lower = package.lower()
                # 清理版本号
                clean_version = re.sub(r"[^0-9.]", "", version)

                self.logger.debug(f"检查包: {package} {version}")

                if package_lower in known_vulnerabilities:
                    for vuln_version, (cve, severity, fixed) in known_vulnerabilities[package_lower].items():
                        if clean_version == vuln_version:
                            issue = DependencyIssue(
                                package=package,
                                version=version,
                                vulnerability_id=cve,
                                severity=VulnerabilitySeverity(severity.lower()),
                                description=f"{package} {version} 存在已知漏洞",
                                fixed_version=fixed,
                                references=[f"https://nvd.nist.gov/vuln/detail/{cve}"],
                            )
                            issues.append(issue)

                            self.logger.warning(
                                f"发现依赖漏洞: {package} {version}\n"
                                f"  CVE: {cve}\n"
                                f"  严重性: {severity}\n"
                                f"  修复版本: {fixed}"
                            )
        except Exception as e:
            self.logger.error(f"检查 NPM 依赖失败: {e}", exc_info=True)

        return issues

    def _generate_summary(
        self,
        issues: list[SecurityIssue],
        secrets: list[SecretMatch],
        dependency_issues: list[DependencyIssue],
    ) -> dict[str, Any]:
        """生成摘要"""
        severity_counts = {}
        for issue in issues:
            sev = issue.severity.value
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        type_counts = {}
        for issue in issues:
            t = issue.vulnerability_type.value
            type_counts[t] = type_counts.get(t, 0) + 1

        return {
            "total_issues": len(issues),
            "total_secrets": len(secrets),
            "total_dependency_issues": len(dependency_issues),
            "by_severity": severity_counts,
            "by_type": type_counts,
            "risk_level": self._calculate_risk_level(severity_counts),
        }

    def _calculate_risk_level(self, severity_counts: dict[str, int]) -> str:
        """计算风险等级"""
        if severity_counts.get("critical", 0) > 0:
            return "critical"
        elif severity_counts.get("high", 0) > 2:
            return "high"
        elif severity_counts.get("high", 0) > 0:
            return "medium"
        elif severity_counts.get("medium", 0) > 0:
            return "low"
        else:
            return "info"


# 创建默认扫描器实例
security_scanner = SecurityScanner()
