"""
FoxCode 安全漏洞扫描器

提供代码安全扫描、敏感信息检测和依赖安全检查功能。

主要功能：
- 常见漏洞模式检测（SQL注入、XSS等）
- 敏感信息检测（API Key、密码等）
- 依赖安全检查
- 安全报告生成
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


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
                "pattern": r"DES|Blowfish",
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
        logger.info("安全漏洞扫描器初始化完成")
    
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
            return issues
        
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            
            lines = content.split("\n")
            
            # 检查漏洞模式
            for vuln_type, rules in self.VULNERABILITY_RULES.items():
                for rule in rules:
                    pattern = rule["pattern"]
                    for i, line in enumerate(lines):
                        if re.search(pattern, line, re.IGNORECASE):
                            issues.append(SecurityIssue(
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
                            ))
            
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
                    
                    issues.append(SecurityIssue(
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
                    ))
            
        except Exception as e:
            logger.debug(f"扫描文件失败 {file_path}: {e}")
        
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
        
        # 遍历目录
        for file_path in directory.rglob("*"):
            if not file_path.is_file():
                continue
            
            if self._should_scan_file(file_path):
                issues = await self.scan_file(file_path)
                all_issues.extend(issues)
                files_scanned += 1
        
        # 检查依赖
        dependency_issues = []
        if self.config.check_dependencies:
            dependency_issues = await self.check_dependencies(directory)
        
        # 计算耗时
        duration = (datetime.now() - start_time).total_seconds()
        
        # 生成摘要
        summary = self._generate_summary(all_issues, all_secrets, dependency_issues)
        
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
        
        # 检查 requirements.txt
        req_file = project_path / "requirements.txt"
        if req_file.exists():
            issues.extend(await self._check_python_dependencies(req_file))
        
        # 检查 package.json
        pkg_file = project_path / "package.json"
        if pkg_file.exists():
            issues.extend(await self._check_npm_dependencies(pkg_file))
        
        return issues
    
    async def _check_python_dependencies(self, req_file: Path) -> list[DependencyIssue]:
        """检查 Python 依赖"""
        issues = []
        
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
            with open(req_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    
                    # 解析包名和版本
                    match = re.match(r"([a-zA-Z0-9_-]+)\s*([<>=!]+)\s*([0-9.]+)", line)
                    if match:
                        package = match.group(1).lower()
                        version = match.group(3)
                        
                        if package in known_vulnerabilities:
                            for vuln_version, (cve, severity, fixed) in known_vulnerabilities[package].items():
                                if version == vuln_version:
                                    issues.append(DependencyIssue(
                                        package=package,
                                        version=version,
                                        vulnerability_id=cve,
                                        severity=VulnerabilitySeverity(severity.lower()),
                                        description=f"{package} {version} 存在已知漏洞",
                                        fixed_version=fixed,
                                        references=[f"https://nvd.nist.gov/vuln/detail/{cve}"],
                                    ))
        except Exception as e:
            logger.debug(f"检查 Python 依赖失败: {e}")
        
        return issues
    
    async def _check_npm_dependencies(self, pkg_file: Path) -> list[DependencyIssue]:
        """检查 NPM 依赖"""
        issues = []
        
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
            with open(pkg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            dependencies = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            
            for package, version in dependencies.items():
                package_lower = package.lower()
                # 清理版本号
                clean_version = re.sub(r"[^0-9.]", "", version)
                
                if package_lower in known_vulnerabilities:
                    for vuln_version, (cve, severity, fixed) in known_vulnerabilities[package_lower].items():
                        if clean_version == vuln_version:
                            issues.append(DependencyIssue(
                                package=package,
                                version=version,
                                vulnerability_id=cve,
                                severity=VulnerabilitySeverity(severity.lower()),
                                description=f"{package} {version} 存在已知漏洞",
                                fixed_version=fixed,
                                references=[f"https://nvd.nist.gov/vuln/detail/{cve}"],
                            ))
        except Exception as e:
            logger.debug(f"检查 NPM 依赖失败: {e}")
        
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
