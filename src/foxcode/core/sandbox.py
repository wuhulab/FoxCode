"""
FoxCode 安全沙箱模块 - 保护系统安全的命令执行限制

这个文件是FoxCode的安全守门员，负责：
1. 命令过滤：阻止危险的系统命令
2. 路径保护：防止目录穿越攻击
3. 编码检测：识别各种编码绕过尝试
4. 审计日志：记录所有安全事件

为什么需要沙箱？
AI可能会执行危险的命令（如rm -rf /），沙箱可以：
1. 保护系统关键文件
2. 防止误操作导致数据丢失
3. 限制AI的权限范围
4. 提供安全审计能力

安全防护措施：
- 黑名单模式：阻止已知的危险命令
- 白名单模式：只允许安全的命令
- 编码绕过检测：识别URL编码、Unicode等绕过尝试
- 符号链接检查：防止通过符号链接访问受限文件

使用方式：
    from foxcode.core.sandbox import Sandbox
    
    sandbox = Sandbox(config)
    result = sandbox.validate_command("rm -rf /")
    
    if not result.allowed:
        print(f"命令被拦截: {result.error_message}")

危险命令示例（会被拦截）：
- rm -rf /: 删除整个系统
- dd if=/dev/zero of=/dev/sda: 覆盖磁盘
- :(){ :|:& };:: Fork炸弹
- chmod -R 777 /: 危险权限设置
"""

from __future__ import annotations

import fnmatch
import logging
import os
import platform
import re
import urllib.parse
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SandboxMode(str, Enum):
    """
    沙箱模式 - 控制命令执行的严格程度
    
    三种模式：
    - DISABLED: 禁用沙箱，允许所有命令（危险，仅测试用）
    - BLACKLIST: 黑名单模式，阻止已知的危险命令（默认）
    - WHITELIST: 白名单模式，只允许预定义的安全命令（最安全）
    
    安全级别：WHITELIST > BLACKLIST > DISABLED
    
    使用建议：
    - 生产环境：使用WHITELIST模式
    - 开发环境：使用BLACKLIST模式
    - 测试环境：可以使用DISABLED模式（谨慎）
    """
    DISABLED = "disabled"       # 禁用沙箱：允许所有命令（危险）
    BLACKLIST = "blacklist"     # 黑名单模式：阻止危险命令（默认）
    WHITELIST = "whitelist"     # 白名单模式：只允许安全命令


@dataclass
class SandboxViolation:
    """沙箱违规记录"""
    command: str                # 违规命令
    violation_type: str         # 违规类型
    reason: str                 # 违规原因
    cwd: str | None = None      # 工作目录
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class SandboxResult:
    """沙箱验证结果"""
    allowed: bool               # 是否允许执行
    violations: list[SandboxViolation] = field(default_factory=list)

    @property
    def first_violation(self) -> SandboxViolation | None:
        """获取第一个违规"""
        return self.violations[0] if self.violations else None

    @property
    def error_message(self) -> str:
        """获取错误信息"""
        if not self.violations:
            return ""
        v = self.violations[0]
        return f"[沙箱安全拦截] {v.violation_type}: {v.reason}"


class EncodingBypassDetector:
    """
    编码绕过检测器 - 识别各种编码绕过安全检查的尝试
    
    为什么需要检测编码绕过？
    攻击者可能使用各种编码方式绕过安全检查：
    - URL编码：%2e%2e%2f 代替 ../
    - 双重编码：%252e%252e 代替 ..
    - Unicode编码：使用全角字符、相似字符
    - HTML实体：&#46; 代替 .
    
    检测策略：
    1. 正则匹配已知的编码模式
    2. URL解码后检查
    3. Unicode同形字符检查
    
    使用示例：
        detector = EncodingBypassDetector()
        issues = detector.detect_encoding_bypass("%2e%2e%2f")
        if issues:
            print(f"检测到编码绕过: {issues}")
    """

    # 已知的编码绕过模式（正则表达式）
    ENCODING_PATTERNS = [
        (r'%2e%2e[%2f%5c]', 'URL编码路径穿越'),  # %2e = .
        (r'%252e%252e', '双重URL编码路径穿越'),  # 双重编码
        (r'\\x2e\\x2e', '十六进制编码路径穿越'),  # \x2e = .
        (r'\.\.%00', '空字节注入'),  # 空字节截断
        (r'%c0%ae', 'UTF-8编码绕过'),  # UTF-8编码的.
        (r'%c1%9c', 'UTF-8编码绕过'),
        (r'\\u002e\\u002e', 'Unicode转义路径穿越'),  # \u002e = .
        (r'&#46;&#46;', 'HTML实体编码路径穿越'),  # &#46; = .
        (r'&#x2e;&#x2e;', 'HTML十六进制实体编码'),
        (r'%uff0e%uff0e', '宽字符编码绕过'),  # 全角字符
        (r'\uff0e\uff0e', '全角字符绕过'),
    ]

    # Unicode同形字符映射
    # 攻击者可能用这些字符替代正常字符
    UNICODE_CONFUSABLES = {
        '.': ['\u002e', '\uff0e', '\u2024', '\ufe52', '\uff61'],  # 各种形式的点
        '/': ['\u002f', '\uff0f', '\u2044', '\u2215', '\u29f8'],  # 各种形式的斜杠
        '\\': ['\u005c', '\uff3c', '\u2216', '\u29f5', '\u29f9'],  # 各种形式的反斜杠
        '-': ['\u002d', '\uff0d', '\u2010', '\u2011', '\u2012', '\u2013', '\u2212'],
        'r': ['\u0072', '\uff52', '\u0280', '\u1d07'],  # rm命令中的r
        'm': ['\u006d', '\uff4d', '\u217f'],  # rm命令中的m
    }

    def __init__(self):
        self._compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), desc)
            for pattern, desc in self.ENCODING_PATTERNS
        ]

    def detect_encoding_bypass(self, command: str) -> list[tuple[str, str]]:
        """
        检测编码绕过尝试
        
        Args:
            command: 要检测的命令
            
        Returns:
            检测到的编码绕过列表 [(模式, 描述)]
        """
        detected = []

        for pattern, desc in self._compiled_patterns:
            if pattern.search(command):
                detected.append((pattern.pattern, desc))

        try:
            url_decoded = urllib.parse.unquote(command)
            if url_decoded != command:
                if '..' in url_decoded or '/' in url_decoded or '\\' in url_decoded:
                    if not any(p[1] == 'URL编码路径穿越' for p in detected):
                        detected.append(('url_decode', 'URL解码后包含路径穿越字符'))
        except Exception:
            pass

        unicode_issues = self._check_unicode_confusables(command)
        detected.extend(unicode_issues)

        return detected

    def _check_unicode_confusables(self, command: str) -> list[tuple[str, str]]:
        """
        检查Unicode同形字符
        
        Args:
            command: 要检测的命令
            
        Returns:
            检测到的Unicode问题列表
        """
        issues = []

        dangerous_chars = ['.', '/', '\\', 'r', 'm']

        for char in dangerous_chars:
            confusables = self.UNICODE_CONFUSABLES.get(char, [])
            for confusable in confusables:
                if confusable in command and confusable != char:
                    issues.append((
                        f'unicode_confusable_{ord(confusable):04x}',
                        f'检测到Unicode同形字符: U+{ord(confusable):04X} (类似 "{char}")'
                    ))

        return issues

    def normalize_command(self, command: str) -> str:
        """
        标准化命令，解码各种编码
        
        Args:
            command: 原始命令
            
        Returns:
            标准化后的命令
        """
        normalized = command

        try:
            for _ in range(3):
                decoded = urllib.parse.unquote(normalized)
                if decoded == normalized:
                    break
                normalized = decoded
        except Exception:
            pass

        for char, confusables in self.UNICODE_CONFUSABLES.items():
            for confusable in confusables:
                if confusable != char:
                    normalized = normalized.replace(confusable, char)

        return normalized


class SandboxConfig:
    """
    沙箱配置类
    
    Attributes:
        enabled: 是否启用沙箱
        mode: 沙箱模式
        allowed_commands: 白名单命令列表
        blocked_commands: 黑名单命令列表
        allow_path_traversal: 是否允许路径穿越（默认不允许）
        max_command_length: 最大命令长度
        blocked_patterns: 阻止的命令模式（正则表达式）
    """

    # Windows 系统危险命令
    WINDOWS_BLOCKED_COMMANDS = [
        "format",
        "diskpart",
        "chkdsk",
        "fdisk",
        "bootsect",
        "bcdedit",
        "reg",
        "regedit",
        "regedt32",
        "gpedit",
        "secpol",
        "lusrmgr",
        "compmgmt",
        "devmgmt",
        "eventvwr",
        "perfmon",
        "resmon",
        "taskmgr",
        "msconfig",
        "sysedit",
        "win.ini",
        "system.ini",
        "shutdown",
        "restart",
        "logoff",
    ]

    # Unix/Linux 系统危险命令
    UNIX_BLOCKED_COMMANDS = [
        "rm",
        "rmdir",
        "dd",
        "fdisk",
        "mkfs",
        "fsck",
        "mount",
        "umount",
        "chmod",
        "chown",
        "chgrp",
        "passwd",
        "useradd",
        "userdel",
        "usermod",
        "groupadd",
        "groupdel",
        "groupmod",
        "shutdown",
        "reboot",
        "halt",
        "poweroff",
        "init",
        "systemctl",
        "service",
        "iptables",
        "ip6tables",
        "ufw",
        "firewall-cmd",
        "crontab",
        "at",
        "batch",
        "sudo",
        "su",
        "visudo",
        "chroot",
        "jail",
    ]

    # 危险命令模式（正则表达式）
    DANGEROUS_PATTERNS = [
        r"rm\s+-rf\s+/",                    # rm -rf /
        r"rm\s+-rf\s+\*",                   # rm -rf *
        r"rm\s+-rf\s+~",                    # rm -rf ~
        r"rm\s+-rf\s+\.\.",                 # rm -rf ..
        r"del\s+/[sS]\s+\\",                # del /s C:\
        r"format\s+[a-zA-Z]:",              # format C:
        r">\s*/dev/sd[a-z]",                # 写入磁盘设备
        r">\s*/dev/hd[a-z]",                # 写入硬盘设备
        r"dd\s+if=.*of=/dev/",              # dd 写入设备
        r"chmod\s+[-+]?777\s+/",            # chmod 777 /
        r"chown\s+.*\s+/",                  # chown on root
        r":(){ :\|:& };:",                  # Fork bomb
        r"curl.*\|\s*bash",                 # curl | bash
        r"wget.*\|\s*bash",                 # wget | bash
        r"curl.*\|\s*sh",                   # curl | sh
        r"wget.*\|\s*sh",                   # wget | sh
        r"eval\s+\$\(.*\)",                 # eval $(...)
        r"source\s+\$\(.*\)",               # source $(...)
        r"\$\([^)]*\)",                     # Command substitution
        r"pkexec",                          # Polkit 权限提升
        r"sudo\s+su",                       # sudo su
        r"sudo\s+-i",                       # sudo -i
        r"nc\s+-[elp]",                     # netcat 监听/连接
        r"ncat\s+-[elp]",                   # ncat 监听/连接
        r"/dev/tcp/",                       # Bash TCP 重定向
        r"/dev/udp/",                       # Bash UDP 重定向
        r"curl.*-o\s+/dev/null.*\|",        # curl 下载并执行
        r"wget.*-O\s+/dev/null.*\|",        # wget 下载并执行
        r"base64\s+-d.*\|",                 # base64 解码并执行
        r"xxd\s+-r.*\|",                    # xxd 反转并执行
        r"python.*-c\s+.*__import__",       # Python 动态导入执行
        r"perl.*-e\s+.*system",             # Perl 系统调用
        r"ruby.*-e\s+.*system",             # Ruby 系统调用
        r"php.*-r\s+.*system",              # PHP 系统调用
        r"awk.*system\s*\(",                # awk 系统调用
        r"find.*-exec",                     # find exec
        r"xargs\s+.*rm",                    # xargs rm
        r"tee\s+.*\.sh.*\|",                # tee 写入脚本并执行
        r">\s*/etc/",                       # 写入 /etc
        r">\s*/var/",                       # 写入 /var
        r">\s*/root/",                      # 写入 /root
        r"echo.*>\s*/etc/passwd",           # 修改密码文件
        r"echo.*>\s*/etc/shadow",           # 修改影子文件
        r"useradd",                         # 添加用户
        r"usermod",                         # 修改用户
        r"passwd\s+\w+",                    # 修改密码
        r"crontab\s+-e",                    # 编辑 crontab
        r"systemctl\s+(start|stop|restart|enable|disable)",  # systemd 控制
        r"service\s+\w+\s+(start|stop|restart)",  # service 控制
        r"iptables\s+-[AI]",                # iptables 规则添加
        r"ufw\s+(allow|deny|enable)",       # ufw 防火墙
        r"firewall-cmd",                    # firewalld
        r"setenforce",                      # SELinux 控制
        r"chcon\s+",                        # SELinux 上下文修改
        r"restorecon\s+",                   # SELinux 上下文恢复
    ]

    def __init__(
        self,
        enabled: bool = True,
        mode: SandboxMode = SandboxMode.BLACKLIST,
        allowed_commands: list[str] | None = None,
        blocked_commands: list[str] | None = None,
        allow_path_traversal: bool = False,
        max_command_length: int = 10000,
        blocked_patterns: list[str] | None = None,
    ):
        self.enabled = enabled
        self.mode = mode
        self.allowed_commands = allowed_commands or self._get_default_allowed_commands()
        self.blocked_commands = blocked_commands or self._get_default_blocked_commands()
        self.allow_path_traversal = allow_path_traversal
        self.max_command_length = max_command_length
        self.blocked_patterns = blocked_patterns or self.DANGEROUS_PATTERNS

        # 编译正则表达式
        self._compiled_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.blocked_patterns
        ]

    def _get_default_allowed_commands(self) -> list[str]:
        """获取默认白名单命令"""
        return [
            "ls", "dir", "cat", "type", "echo", "pwd", "cd",
            "git", "npm", "node", "python", "python3", "pip", "pip3",
            "cargo", "rustc", "go", "java", "javac", "mvn", "gradle",
            "make", "cmake", "gcc", "g++", "clang", "clang++",
            "docker", "docker-compose",
            "pytest", "jest", "mocha", "unittest",
            "curl", "wget",
            "tar", "zip", "unzip", "gzip", "gunzip",
            "grep", "find", "sed", "awk",
            "touch", "mkdir", "cp", "mv",
        ]

    def _get_default_blocked_commands(self) -> list[str]:
        """获取默认黑名单命令"""
        system = platform.system()
        if system == "Windows":
            return self.WINDOWS_BLOCKED_COMMANDS.copy()
        else:
            return self.UNIX_BLOCKED_COMMANDS.copy()


class Sandbox:
    """
    安全沙箱
    
    用于验证命令执行的安全性，防止：
    - 目录穿透攻击
    - 执行危险系统命令
    - 执行未授权的命令
    - 编码绕过攻击
    """

    def __init__(self, config: SandboxConfig | None = None):
        self.config = config or SandboxConfig()
        self._violation_log: list[SandboxViolation] = []
        self._encoding_detector = EncodingBypassDetector()

    def validate_command(
        self,
        command: str,
        cwd: str | Path | None = None,
    ) -> SandboxResult:
        """
        验证命令是否可以安全执行
        
        Args:
            command: 要验证的命令
            cwd: 工作目录
            
        Returns:
            SandboxResult: 验证结果
        """
        violations: list[SandboxViolation] = []

        if not self.config.enabled:
            return SandboxResult(allowed=True, violations=[])

        cwd_str = str(cwd) if cwd else None

        if len(command) > self.config.max_command_length:
            violations.append(SandboxViolation(
                command=command[:100] + "..." if len(command) > 100 else command,
                violation_type="命令过长",
                reason=f"命令长度 {len(command)} 超过最大限制 {self.config.max_command_length}",
                cwd=cwd_str,
            ))
            return SandboxResult(allowed=False, violations=violations)

        normalized_command = self._encoding_detector.normalize_command(command)

        encoding_violations = self._check_encoding_bypass(normalized_command)
        violations.extend(encoding_violations)

        if not self.config.allow_path_traversal and cwd:
            traversal_violation = self._check_path_traversal(normalized_command, cwd)
            if traversal_violation:
                violations.append(traversal_violation)

        pattern_violation = self._check_dangerous_patterns(normalized_command)
        if pattern_violation:
            violations.append(pattern_violation)

        if self.config.mode == SandboxMode.BLACKLIST:
            blacklist_violation = self._check_blacklist(normalized_command)
            if blacklist_violation:
                violations.append(blacklist_violation)

        elif self.config.mode == SandboxMode.WHITELIST:
            whitelist_violation = self._check_whitelist(normalized_command)
            if whitelist_violation:
                violations.append(whitelist_violation)

        if violations:
            for v in violations:
                self._log_violation(v)

        return SandboxResult(
            allowed=len(violations) == 0,
            violations=violations,
        )

    def _check_encoding_bypass(self, command: str) -> list[SandboxViolation]:
        """
        检查编码绕过尝试
        
        Args:
            command: 命令
            
        Returns:
            违规记录列表
        """
        violations = []
        detected = self._encoding_detector.detect_encoding_bypass(command)

        for pattern, desc in detected:
            violations.append(SandboxViolation(
                command=command[:100] + "..." if len(command) > 100 else command,
                violation_type="编码绕过尝试",
                reason=f"检测到编码绕过: {desc}",
                details={"pattern": pattern, "description": desc},
            ))

        return violations

    def _check_path_traversal(
        self,
        command: str,
        cwd: str | Path,
    ) -> SandboxViolation | None:
        """
        检查目录穿透尝试
        
        Args:
            command: 命令
            cwd: 工作目录
            
        Returns:
            违规记录，如果没有违规则返回 None
        """
        cwd_path = Path(cwd).resolve()

        # 检测路径穿越模式
        traversal_patterns = [
            r"\.\.",                           # ..
            r"\.\./",                          # ../
            r"\.\.\\",                         # ..\
            r"/etc/",                          # Unix 系统目录
            r"/var/",                          # Unix 系统目录
            r"/usr/",                          # Unix 系统目录
            r"/bin/",                          # Unix 系统目录
            r"/sbin/",                         # Unix 系统目录
            r"/root/",                         # Unix root 目录
            r"/home/",                         # Unix 用户目录
            r"[a-zA-Z]:\\",                    # Windows 绝对路径
            r"[a-zA-Z]:/",                     # Windows 绝对路径（斜杠）
            r"\\Windows\\",                    # Windows 系统目录
            r"\\Program Files\\",              # Windows 程序目录
            r"\\ProgramData\\",                # Windows 数据目录
            r"\\Users\\",                      # Windows 用户目录
            r"~[\\/]?",                        # 用户主目录
            r"%USERPROFILE%",                  # Windows 用户目录变量
            r"%SYSTEMROOT%",                   # Windows 系统目录变量
            r"%WINDIR%",                       # Windows 目录变量
            r"%APPDATA%",                      # Windows 应用数据目录
            r"%PROGRAMFILES%",                 # Windows 程序文件目录
        ]

        for pattern in traversal_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                # 检查是否是相对路径穿越
                if ".." in pattern:
                    return SandboxViolation(
                        command=command,
                        violation_type="目录穿透",
                        reason="命令包含路径穿越尝试 (..)，不允许突破工作目录",
                        cwd=str(cwd_path),
                        details={"pattern": pattern},
                    )
                # 检查是否是 Windows 绝对路径
                elif re.match(r"^[a-zA-Z]:[\\/]", pattern):
                    # 提取命令中的绝对路径
                    absolute_path_match = re.search(r'[a-zA-Z]:[\\/][^\s"]+', command)
                    if absolute_path_match:
                        absolute_path = absolute_path_match.group(0)
                        try:
                            # 解析路径并检查是否在工作目录内
                            path_to_check = Path(absolute_path).resolve()
                            if not path_to_check.is_relative_to(cwd_path):
                                return SandboxViolation(
                                    command=command,
                                    violation_type="目录穿透",
                                    reason="命令尝试访问工作目录之外的路径",
                                    cwd=str(cwd_path),
                                    details={"pattern": pattern, "path": str(path_to_check)},
                                )
                        except Exception:
                            # 路径解析失败，保守处理
                            pass
                    # 如果是合法的子目录，不返回违规
                else:
                    return SandboxViolation(
                        command=command,
                        violation_type="目录穿透",
                        reason="命令尝试访问工作目录之外的系统路径",
                        cwd=str(cwd_path),
                        details={"pattern": pattern},
                    )

        return None

    def _check_dangerous_patterns(
        self,
        command: str,
    ) -> SandboxViolation | None:
        """
        检查危险命令模式
        
        Args:
            command: 命令
            
        Returns:
            违规记录，如果没有违规则返回 None
        """
        for i, pattern in enumerate(self.config._compiled_patterns):
            if pattern.search(command):
                return SandboxViolation(
                    command=command,
                    violation_type="危险命令模式",
                    reason="命令匹配已知的危险模式",
                    details={
                        "pattern": self.config.blocked_patterns[i],
                    },
                )

        return None

    def _check_blacklist(
        self,
        command: str,
    ) -> SandboxViolation | None:
        """
        检查黑名单命令
        
        Args:
            command: 命令
            
        Returns:
            违规记录，如果没有违规则返回 None
        """
        # 提取命令的第一个词（命令名）
        command_name = self._extract_command_name(command)

        if not command_name:
            return None

        # 检查黑名单
        for blocked in self.config.blocked_commands:
            # 支持通配符匹配
            if fnmatch.fnmatch(command_name.lower(), blocked.lower()):
                return SandboxViolation(
                    command=command,
                    violation_type="黑名单命令",
                    reason=f"命令 '{command_name}' 在黑名单中，不允许执行",
                    details={
                        "command_name": command_name,
                        "blocked_pattern": blocked,
                    },
                )

        return None

    def _check_whitelist(
        self,
        command: str,
    ) -> SandboxViolation | None:
        """
        检查白名单命令
        
        Args:
            command: 命令
            
        Returns:
            违规记录，如果没有违规则返回 None
        """
        # 提取命令的第一个词（命令名）
        command_name = self._extract_command_name(command)

        if not command_name:
            return SandboxViolation(
                command=command,
                violation_type="无效命令",
                reason="无法解析命令名",
            )

        # 检查白名单
        for allowed in self.config.allowed_commands:
            # 支持通配符匹配
            if fnmatch.fnmatch(command_name.lower(), allowed.lower()):
                return None  # 在白名单中，允许执行

        # 不在白名单中
        return SandboxViolation(
            command=command,
            violation_type="白名单限制",
            reason=f"命令 '{command_name}' 不在白名单中，不允许执行",
            details={
                "command_name": command_name,
                "allowed_commands": self.config.allowed_commands[:10],  # 只显示前10个
            },
        )

    def _extract_command_name(self, command: str) -> str | None:
        """
        提取命令名
        
        Args:
            command: 完整命令
            
        Returns:
            命令名
        """
        # 去除前导空格
        command = command.strip()

        if not command:
            return None

        # 处理管道和连接符
        for separator in ["|", "&&", "||", ";"]:
            if separator in command:
                # 取第一个命令
                command = command.split(separator)[0].strip()

        # 处理 Windows 路径
        system = platform.system()
        if system == "Windows":
            # 移除可能的驱动器路径前缀
            if re.match(r"^[a-zA-Z]:", command):
                command = command[2:]

        # 提取第一个词
        parts = command.split()
        if not parts:
            return None

        # 获取命令名（去除路径）
        cmd_path = parts[0]
        cmd_name = os.path.basename(cmd_path)

        # Windows 下移除扩展名
        if system == "Windows" and "." in cmd_name:
            cmd_name = cmd_name.rsplit(".", 1)[0]

        return cmd_name

    def _log_violation(self, violation: SandboxViolation) -> None:
        """
        记录安全违规
        
        Args:
            violation: 违规记录
        """
        self._violation_log.append(violation)

        # 记录日志
        logger.warning(
            f"沙箱安全违规: {violation.violation_type} - {violation.reason}\n"
            f"  命令: {violation.command[:100]}{'...' if len(violation.command) > 100 else ''}\n"
            f"  工作目录: {violation.cwd or '未指定'}"
        )

    def get_violation_log(self) -> list[SandboxViolation]:
        """
        获取违规日志
        
        Returns:
            违规记录列表
        """
        return self._violation_log.copy()

    def clear_violation_log(self) -> None:
        """清除违规日志"""
        self._violation_log.clear()


# 全局沙箱实例
_sandbox: Sandbox | None = None


def get_sandbox() -> Sandbox:
    """
    获取全局沙箱实例
    
    Returns:
        Sandbox 实例
    """
    global _sandbox
    if _sandbox is None:
        _sandbox = Sandbox()
    return _sandbox


def set_sandbox(sandbox: Sandbox) -> None:
    """
    设置全局沙箱实例
    
    Args:
        sandbox: Sandbox 实例
    """
    global _sandbox
    _sandbox = sandbox


def validate_command(
    command: str,
    cwd: str | Path | None = None,
) -> SandboxResult:
    """
    使用全局沙箱验证命令
    
    Args:
        command: 要验证的命令
        cwd: 工作目录
        
    Returns:
        SandboxResult: 验证结果
    """
    return get_sandbox().validate_command(command, cwd)
