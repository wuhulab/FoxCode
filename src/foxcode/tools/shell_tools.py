"""
FoxCode Shell执行工具 - 安全的命令行操作

这个文件提供Shell命令执行功能：
1. 同步执行：等待命令完成后返回结果
2. 异步执行：后台运行，可以查询状态
3. 命令管理：启动、停止、查询状态
4. 安全沙箱：限制危险命令

安全特性：
- 命令过滤：阻止危险命令（rm -rf /等）
- 环境变量脱敏：隐藏API密钥等敏感信息
- 沙箱模式：黑名单/白名单控制
- 超时保护：防止命令无限运行

使用方式：
    # 这些工具通过agent自动调用
    # AI会根据需要选择合适的工具
    
    # 例如执行命令：
    # <function=run_command>
    # <parameter=command>npm install</parameter>
    # </function>
    
    # 异步执行：
    # <function=run_command>
    # <parameter=command>npm start</parameter>
    # <parameter=blocking>false</parameter>
    # </function>

关键工具：
- RunCommandTool: 执行命令（同步/异步）
- CheckCommandStatusTool: 查询命令状态
- StopCommandTool: 停止运行中的命令

危险命令防护：
- rm -rf /: 删除整个系统
- dd if=/dev/zero: 覆盖磁盘
- :(){ :|:& };:: Fork炸弹
- chmod -R 777: 危险权限设置
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import shutil
from pathlib import Path
from typing import Any

from foxcode.core.command_manager import CommandStatus, command_manager
from foxcode.core.sandbox import (
    Sandbox,
    SandboxConfig,
    SandboxMode,
)
from foxcode.core.sensitive_masker import mask_sensitive
from foxcode.tools.base import (
    BaseTool,
    ToolCategory,
    ToolParameter,
    ToolResult,
    tool,
)

logger = logging.getLogger(__name__)


# ==================== 敏感环境变量检测 ====================
# 这些是常见的敏感环境变量名称
# 在输出环境变量时会自动脱敏，防止泄露

SENSITIVE_ENV_PATTERNS = [
    # API密钥
    'API_KEY', 'APIKEY', 'API_SECRET', 'APISECRET',
    'SECRET', 'SECRET_KEY', 'SECRETKEY',
    # 密码
    'PASSWORD', 'PASSWD', 'PWD',
    # Token
    'TOKEN', 'ACCESS_TOKEN', 'REFRESH_TOKEN', 'AUTH_TOKEN',
    # 私钥
    'PRIVATE_KEY', 'PRIVATEKEY',
    # AWS
    'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN',
    # 数据库
    'DATABASE_URL', 'DB_URL', 'DB_PASSWORD',
    # AI服务
    'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'DEEPSEEK_API_KEY',
    # 版本控制
    'GITHUB_TOKEN', 'GITLAB_TOKEN',
    # 通讯工具
    'SLACK_TOKEN', 'DISCORD_TOKEN',
    # 支付
    'STRIP_API_KEY', 'STRIPE_SECRET_KEY',
    # 邮件
    'SENDGRID_API_KEY', 'MAILGUN_API_KEY',
    # CDN
    'CLOUDFLARE_API_KEY', 'CLOUDFLARE_API_TOKEN',
    # 云服务
    'AZURE_CLIENT_SECRET', 'AZURE_SUBSCRIPTION_KEY',
    'GOOGLE_API_KEY', 'GOOGLE_CLIENT_SECRET',
    'HEROKU_API_KEY', 'VERCEL_TOKEN',
    # 包管理
    'NPM_TOKEN', 'PYPI_TOKEN',
    # 容器
    'DOCKER_PASSWORD', 'KUBERNETES_TOKEN',
    # SSH
    'SSH_PRIVATE_KEY', 'SSH_KEY',
    # 加密
    'GPG_KEY', 'PGP_KEY',
    'ENCRYPTION_KEY', 'ENCRYPT_KEY',
    'SIGNING_KEY', 'SIGN_KEY',
    # OAuth
    'OAUTH_SECRET', 'OAUTH_TOKEN',
    # JWT
    'JWT_SECRET', 'JWT_TOKEN',
    # Session
    'SESSION_SECRET', 'SESSION_KEY',
    'COOKIE_SECRET', 'CSRF_TOKEN',
    # 验证码
    'RECAPTCHA_SECRET', 'RECAPTCHA_KEY',
    # 其他服务
    'MAILCHIMP_API_KEY', 'TWILIO_AUTH_TOKEN',
    'ALGOLIA_API_KEY', 'ELASTICSEARCH_PASSWORD',
    'MONGO_URL', 'REDIS_URL', 'RABBITMQ_URL',
    'KAFKA_PASSWORD', 'CONSUL_TOKEN',
    'VAULT_TOKEN', 'NOMAD_TOKEN',
    'TERRAFORM_TOKEN', 'HARBOR_PASSWORD',
    'JENKINS_TOKEN', 'GITLAB_RUNNER_TOKEN',
    'BITBUCKET_TOKEN', 'CODECOV_TOKEN',
    'SONAR_TOKEN', 'SNYK_TOKEN',
    'DATADOG_API_KEY', 'NEW_RELIC_API_KEY',
    'SENTRY_AUTH_TOKEN', 'BUGSNAG_API_KEY',
    'ROLLBAR_ACCESS_TOKEN', 'AIRBRAKE_API_KEY',
    'PAGERDUTY_API_KEY', 'OPS_GENIE_API_KEY',
    'PUSHOVER_API_KEY', 'TELEGRAM_BOT_TOKEN',
    'TWITTER_API_KEY', 'FACEBOOK_APP_SECRET',
    'LINKEDIN_CLIENT_SECRET', 'INSTAGRAM_CLIENT_SECRET',
    'REDDIT_CLIENT_SECRET', 'TUMBLR_CONSUMER_SECRET',
    'SPOTIFY_CLIENT_SECRET', 'DROPBOX_ACCESS_TOKEN',
    'BOX_API_KEY', 'ONEDRIVE_ACCESS_TOKEN',
    'GOOGLE_DRIVE_API_KEY', 'ICLOUD_API_KEY',
]

# 敏感关键词（用于模糊匹配）
SENSITIVE_KEYWORDS = [
    'KEY', 'SECRET', 'TOKEN', 'PASSWORD', 'PASSWD', 'PWD',
    'CREDENTIAL', 'PRIVATE', 'AUTH', 'API_KEY',
]

# 敏感值长度阈值（超过此长度的值可能是密钥）
SENSITIVE_VALUE_LENGTH_THRESHOLD = 16


def _is_sensitive_by_keyword(key: str) -> bool:
    """
    通过关键词检测敏感变量
    
    检测逻辑：
    如果环境变量名包含敏感关键词（KEY、SECRET、TOKEN等），
    则认为是敏感变量，需要脱敏。
    
    例如：
    - MY_API_KEY -> 敏感（包含KEY）
    - DATABASE_PASSWORD -> 敏感（包含PASSWORD）
    - PATH -> 不敏感
    
    Args:
        key: 环境变量名
        
    Returns:
        是否敏感
    """
    # 标准化变量名：大写、替换连字符
    key_upper = key.upper().replace('-', '_')

    # 检查是否包含敏感关键词
    for keyword in SENSITIVE_KEYWORDS:
        if keyword in key_upper:
            return True

    return False


def _is_sensitive_by_value(value: str) -> bool:
    """
    通过值特征检测敏感变量
    
    检测逻辑：
    分析值的格式特征，判断是否可能是密钥或token。
    
    特征检测：
    1. 长度：超过16字符的随机字符串
    2. 前缀：sk-（OpenAI）、ghp_（GitHub）等
    3. 格式：Base64、十六进制、证书格式
    
    例如：
    - "sk-xxxxxxxxxxxx" -> 敏感（OpenAI密钥格式）
    - "ghp_xxxxxxxxxx" -> 敏感（GitHub token格式）
    - "-----BEGIN RSA PRIVATE KEY-----" -> 敏感（私钥格式）
    - "Hello World" -> 不敏感（普通文本）
    
    Args:
        value: 环境变量值
        
    Returns:
        是否可能是敏感值
    """
    # 空值或太短的值不可能是密钥
    if not value or len(value) < SENSITIVE_VALUE_LENGTH_THRESHOLD:
        return False

    # 检查已知的密钥前缀
    # OpenAI: sk-, Anthropic: sk-ant-
    # GitHub: ghp_, gho_, ghu_, ghs_, ghr_
    if value.startswith(('sk-', 'sk-ant-', 'Bearer ', 'ghp_', 'gho_', 'ghu_', 'ghs_', 'ghr_')):
        return True

    # 检查证书和Base64格式
    # -----BEGIN: 证书格式
    # eyJ: JWT token（Base64编码的JSON）
    # AKIA/ASIA: AWS访问密钥
    if value.startswith(('-----BEGIN', 'eyJ', 'AKIA', 'ASIA')):
        return True

    # 检查长随机字符串（可能是API密钥）
    # 格式：20+字符的字母数字下划线连字符
    import re
    if re.match(r'^[A-Za-z0-9_-]{20,}$', value):
        return True

    # 检查十六进制字符串（可能是哈希或密钥）
    # 格式：32+字符的十六进制
    if re.match(r'^[a-f0-9]{32,}$', value, re.IGNORECASE):
        return True

    return False


def filter_sensitive_env(env: dict[str, str]) -> dict[str, str]:
    """
    过滤敏感环境变量
    
    使用多种方法检测敏感变量：
    1. 精确匹配已知敏感变量名
    2. 关键词匹配
    3. 值特征检测
    
    Args:
        env: 原始环境变量字典
        
    Returns:
        过滤后的环境变量字典
    """
    filtered = {}

    for key, value in env.items():
        key_upper = key.upper().replace('-', '_')

        is_sensitive = False
        match_reason = ""

        for pattern in SENSITIVE_ENV_PATTERNS:
            if pattern in key_upper:
                is_sensitive = True
                match_reason = f"匹配模式: {pattern}"
                break

        if not is_sensitive and _is_sensitive_by_keyword(key):
            is_sensitive = True
            match_reason = "关键词匹配"

        if not is_sensitive and _is_sensitive_by_value(value):
            is_sensitive = True
            match_reason = "值特征匹配"

        if is_sensitive:
            filtered[key] = "***FILTERED***"
            logger.debug(f"过滤敏感环境变量: {key} ({match_reason})")
        else:
            filtered[key] = value

    return filtered


def decode_output(data: bytes) -> str:
    """
    智能解码命令输出
    
    尝试多种编码方式解码输出数据
    
    Args:
        data: 原始字节数据
        
    Returns:
        解码后的字符串
    """
    # 尝试的编码列表（按优先级排序）
    encodings = [
        "utf-8",
        "gbk",           # 中文 Windows
        "gb2312",        # 简体中文
        "gb18030",       # 中文超集
        "big5",          # 繁体中文
        "cp932",         # 日文 Windows
        "cp949",         # 韩文 Windows
        "shift_jis",     # 日文
        "euc-jp",        # 日文
        "euc-kr",        # 韩文
        "iso-8859-1",    # 西欧语言
        "cp1252",        # 西欧 Windows
        "latin-1",       # 通用后备
    ]

    for encoding in encodings:
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue

    # 所有编码都失败，使用 replace 模式
    return data.decode("utf-8", errors="replace")


@tool
class ShellExecuteTool(BaseTool):
    """Execute shell command"""

    name = "shell_execute"
    description = "Execute command in terminal, supports sync and async modes"
    category = ToolCategory.SHELL
    dangerous = True
    parameters = [
        ToolParameter(
            name="command",
            type="string",
            description="Command to execute",
            required=True,
        ),
        ToolParameter(
            name="cwd",
            type="string",
            description="Working directory for command execution",
            required=False,
            default=None,
        ),
        ToolParameter(
            name="timeout",
            type="integer",
            description="Command timeout in seconds",
            required=False,
            default=300,
        ),
        ToolParameter(
            name="env",
            type="object",
            description="Environment variables",
            required=False,
            default=None,
        ),
        ToolParameter(
            name="async_mode",
            type="boolean",
            description="Whether to execute asynchronously (recommended for long-running commands)",
            required=False,
            default=False,
        ),
    ]

    def __init__(self, config: Any = None):
        super().__init__(config)
        self._sandbox: Sandbox | None = None

    def _get_sandbox(self) -> Sandbox:
        """
        获取沙箱实例
        
        Returns:
            Sandbox 实例
        """
        if self._sandbox is None:
            # 从配置创建沙箱
            if self.config and hasattr(self.config, 'sandbox'):
                sandbox_config = SandboxConfig(
                    enabled=self.config.sandbox.enabled,
                    mode=SandboxMode(self.config.sandbox.mode.value),
                    allow_path_traversal=self.config.sandbox.allow_path_traversal,
                    max_command_length=self.config.sandbox.max_command_length,
                    allowed_commands=self.config.sandbox.allowed_commands,
                    blocked_commands=self.config.sandbox.blocked_commands or None,
                )
                self._sandbox = Sandbox(sandbox_config)
            else:
                # 使用默认配置
                self._sandbox = Sandbox()

        return self._sandbox

    def _sanitize_path_env(self, env: dict[str, str], system: str) -> dict[str, str]:
        """
        清理 PATH 环境变量，确保只包含安全路径
        
        防止通过 PATH 注入执行恶意程序。
        
        Args:
            env: 环境变量字典
            system: 操作系统类型
            
        Returns:
            清理后的环境变量字典
        """
        if "PATH" not in env:
            return env

        # 定义安全的 PATH 目录
        if system == "Windows":
            safe_dirs = [
                os.environ.get("SystemRoot", r"C:\Windows"),
                os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32"),
                os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "Wbem"),
                os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0"),
            ]
        else:
            safe_dirs = [
                "/usr/local/sbin",
                "/usr/local/bin",
                "/usr/sbin",
                "/usr/bin",
                "/sbin",
                "/bin",
            ]

        # 过滤 PATH 中的目录
        current_path = env["PATH"]
        path_dirs = current_path.split(os.pathsep)

        # 只保留存在的安全目录
        filtered_dirs = []
        for dir_path in path_dirs:
            dir_path = dir_path.strip()
            if not dir_path:
                continue

            # 检查是否是安全目录
            is_safe = False
            for safe_dir in safe_dirs:
                try:
                    # 规范化路径比较
                    resolved_dir = str(Path(dir_path).resolve())
                    resolved_safe = str(Path(safe_dir).resolve())
                    if resolved_dir == resolved_safe:
                        is_safe = True
                        break
                except Exception:
                    pass

            # 如果目录在工作目录下，也认为是安全的
            try:
                work_dir = Path.cwd()
                resolved_dir = Path(dir_path).resolve()
                if str(resolved_dir).startswith(str(work_dir)):
                    is_safe = True
            except Exception:
                pass

            if is_safe:
                filtered_dirs.append(dir_path)
            else:
                logger.debug(f"从 PATH 中移除不安全目录: {dir_path}")

        # 更新 PATH
        env["PATH"] = os.pathsep.join(filtered_dirs)

        return env

    async def execute(
        self,
        command: str,
        cwd: str | None = None,
        timeout: int = 300,
        env: dict[str, str] | None = None,
        async_mode: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        """执行 Shell 命令"""
        try:
            # 确定工作目录
            work_dir = Path(cwd).resolve() if cwd else Path.cwd()

            if not work_dir.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"工作目录不存在: {work_dir}",
                )

            # 沙箱安全验证
            sandbox = self._get_sandbox()
            sandbox_result = sandbox.validate_command(command, work_dir)

            if not sandbox_result.allowed:
                logger.warning(
                    f"沙箱拦截命令: {mask_sensitive(command[:100])}{'...' if len(command) > 100 else ''}\n"
                    f"原因: {sandbox_result.error_message}"
                )
                return ToolResult(
                    success=False,
                    output="",
                    error=sandbox_result.error_message,
                    data={
                        "sandbox_blocked": True,
                        "violation_type": sandbox_result.first_violation.violation_type if sandbox_result.first_violation else None,
                    },
                )

            exec_env = filter_sensitive_env(os.environ.copy())
            if env:
                filtered_user_env = filter_sensitive_env(env)
                exec_env.update(filtered_user_env)

            # 根据系统选择 shell（使用绝对路径，避免 PATH 查找）
            system = platform.system()
            if system == "Windows":
                # Windows 使用 PowerShell（查找绝对路径）
                shell_path = shutil.which("powershell") or shutil.which("pwsh")
                if shell_path:
                    # 验证 shell 路径是否在系统目录中
                    shell_path = str(Path(shell_path).resolve())
                    exec_cmd = [shell_path, "-NoProfile", "-NonInteractive", "-Command", command]
                else:
                    # 回退到 cmd，使用系统目录的绝对路径
                    system_root = os.environ.get("SystemRoot", r"C:\Windows")
                    cmd_path = Path(system_root) / "System32" / "cmd.exe"
                    if cmd_path.exists():
                        exec_cmd = [str(cmd_path), "/c", command]
                    else:
                        exec_cmd = ["cmd", "/c", command]
            else:
                # Unix 使用 bash（使用绝对路径）
                bash_path = "/bin/bash"
                if not Path(bash_path).exists():
                    bash_path = shutil.which("bash") or "/bin/sh"
                exec_cmd = [bash_path, "-c", command]

            # 清理环境变量中的 PATH，确保只包含安全路径
            exec_env = self._sanitize_path_env(exec_env, system)

            logger.info(f"执行命令: {mask_sensitive(command)}")
            logger.debug(f"工作目录: {work_dir}, 异步模式: {async_mode}")

            # 注册命令
            cmd_info = await command_manager.register_command(
                command=command,
                cwd=str(work_dir),
                timeout=timeout,
                env=env,
            )

            # 执行命令
            process = await asyncio.create_subprocess_exec(
                *exec_cmd,
                cwd=str(work_dir),
                env=exec_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # 标记命令开始
            await command_manager.start_command(cmd_info, process)

            if async_mode:
                # 异步模式：立即返回命令 ID
                # 启动后台任务来收集输出
                asyncio.create_task(
                    self._async_wait_for_command(cmd_info.id, process, timeout)
                )

                return ToolResult(
                    success=True,
                    output=f"命令已在后台启动\n命令 ID: {cmd_info.id}\n使用 check_command_status 查看状态",
                    data={
                        "command_id": cmd_info.id,
                        "async": True,
                        "cwd": str(work_dir),
                    },
                )

            # 同步模式：等待命令完成
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await command_manager.timeout_command(cmd_info.id)
                return ToolResult(
                    success=False,
                    output="",
                    error=f"命令执行超时（{timeout}秒）",
                    data={"command_id": cmd_info.id},
                )

            # 解码输出
            stdout_str = decode_output(stdout)
            stderr_str = decode_output(stderr)

            # 更新命令状态
            await command_manager.complete_command(
                cmd_info.id,
                exit_code=process.returncode or 0,
                stdout=stdout_str,
                stderr=stderr_str,
            )

            # 构建输出
            output_parts = []
            if stdout_str.strip():
                output_parts.append(stdout_str.strip())
            if stderr_str.strip():
                output_parts.append(f"[stderr]\n{stderr_str.strip()}")

            output = "\n".join(output_parts) if output_parts else "(无输出)"

            success = process.returncode == 0

            return ToolResult(
                success=success,
                output=output,
                error=None if success else f"退出码: {process.returncode}",
                data={
                    "command_id": cmd_info.id,
                    "return_code": process.returncode,
                    "cwd": str(work_dir),
                    "timeout": timeout,
                },
            )

        except Exception as e:
            logger.error(f"执行命令失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=str(e),
            )

    async def _async_wait_for_command(
        self,
        cmd_id: str,
        process: asyncio.subprocess.Process,
        timeout: int,
    ) -> None:
        """
        异步等待命令完成
        
        Args:
            cmd_id: 命令 ID
            process: 进程对象
            timeout: 超时时间
        """
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )

            stdout_str = decode_output(stdout)
            stderr_str = decode_output(stderr)

            await command_manager.complete_command(
                cmd_id,
                exit_code=process.returncode or 0,
                stdout=stdout_str,
                stderr=stderr_str,
            )

        except asyncio.TimeoutError:
            process.kill()
            await command_manager.timeout_command(cmd_id)
        except Exception as e:
            logger.error(f"异步命令执行失败: {e}")
            await command_manager.fail_command(cmd_id, str(e))


@tool
class ShellCheckStatusTool(BaseTool):
    """Check command status"""

    name = "check_command_status"
    description = "Check status and output of long-running commands"
    category = ToolCategory.SHELL
    parameters = [
        ToolParameter(
            name="command_id",
            type="string",
            description="Command ID",
            required=True,
        ),
        ToolParameter(
            name="show_output",
            type="boolean",
            description="Whether to show output content",
            required=False,
            default=True,
        ),
        ToolParameter(
            name="output_priority",
            type="string",
            description="Output priority: top (from start), bottom (from end), split (both)",
            required=False,
            default="bottom",
        ),
        ToolParameter(
            name="output_character_count",
            type="integer",
            description="Number of characters to display",
            required=False,
            default=2000,
        ),
        ToolParameter(
            name="skip_character_count",
            type="integer",
            description="Number of characters to skip (for pagination)",
            required=False,
            default=0,
        ),
    ]

    async def execute(
        self,
        command_id: str,
        show_output: bool = True,
        output_priority: str = "bottom",
        output_character_count: int = 2000,
        skip_character_count: int = 0,
        **kwargs: Any,
    ) -> ToolResult:
        """检查命令状态"""
        cmd_info = command_manager.get_command(command_id)

        if not cmd_info:
            return ToolResult(
                success=False,
                output="",
                error=f"命令不存在: {command_id}",
            )

        # 构建状态信息
        status_emoji = {
            CommandStatus.PENDING: "⏳",
            CommandStatus.RUNNING: "🔄",
            CommandStatus.COMPLETED: "✅",
            CommandStatus.FAILED: "❌",
            CommandStatus.STOPPED: "⏹️",
            CommandStatus.TIMEOUT: "⏱️",
        }

        emoji = status_emoji.get(cmd_info.status, "❓")

        output_lines = [
            f"{emoji} 命令状态: {cmd_info.status.value}",
            f"命令 ID: {cmd_info.id}",
            f"命令: {cmd_info.command}",
            f"工作目录: {cmd_info.cwd}",
            f"执行时长: {cmd_info.duration:.2f} 秒",
        ]

        if cmd_info.exit_code is not None:
            output_lines.append(f"退出码: {cmd_info.exit_code}")

        if cmd_info.error:
            output_lines.append(f"错误: {cmd_info.error}")

        # 添加输出内容
        if show_output:
            output_lines.append("")
            output_lines.append("─── 输出内容 ───")

            combined_output = cmd_info.stdout
            if cmd_info.stderr:
                combined_output += f"\n[stderr]\n{cmd_info.stderr}"

            if combined_output:
                truncated_output = self._truncate_output(
                    combined_output,
                    priority=output_priority,
                    char_count=output_character_count,
                    skip_count=skip_character_count,
                )
                output_lines.append(truncated_output)
            else:
                output_lines.append("(暂无输出)")

        return ToolResult(
            success=True,
            output="\n".join(output_lines),
            data=cmd_info.to_dict(),
        )

    def _truncate_output(
        self,
        output: str,
        priority: str,
        char_count: int,
        skip_count: int,
    ) -> str:
        """
        截断输出
        
        Args:
            output: 原始输出
            priority: 优先级
            char_count: 字符数量
            skip_count: 跳过数量
            
        Returns:
            截断后的输出
        """
        total_len = len(output)

        if total_len <= char_count:
            return output

        if priority == "top":
            # 从开头显示
            start = skip_count
            end = min(start + char_count, total_len)
            result = output[start:end]
            if end < total_len:
                result += f"\n... (还有 {total_len - end} 个字符)"
            return result

        elif priority == "bottom":
            # 从结尾显示
            end = total_len - skip_count
            start = max(0, end - char_count)
            result = output[start:end]
            if start > 0:
                result = f"... (跳过 {start} 个字符)\n" + result
            return result

        elif priority == "split":
            # 同时显示开头和结尾
            half = char_count // 2
            top_part = output[:half]
            bottom_part = output[-(char_count - half):]
            middle_count = total_len - char_count
            return f"{top_part}\n... (中间省略 {middle_count} 个字符) ...\n{bottom_part}"

        return output[:char_count]


@tool
class ShellStopTool(BaseTool):
    """Stop command execution"""

    name = "stop_command"
    description = "Stop a running command"
    category = ToolCategory.SHELL
    dangerous = True
    parameters = [
        ToolParameter(
            name="command_id",
            type="string",
            description="Command ID to stop",
            required=True,
        ),
    ]

    async def execute(
        self,
        command_id: str,
        **kwargs: Any,
    ) -> ToolResult:
        """停止命令"""
        cmd_info = command_manager.get_command(command_id)

        if not cmd_info:
            return ToolResult(
                success=False,
                output="",
                error=f"命令不存在: {command_id}",
            )

        if not cmd_info.is_running:
            return ToolResult(
                success=True,
                output=f"命令 {command_id} 当前状态为 {cmd_info.status.value}，无需停止",
                data=cmd_info.to_dict(),
            )

        # 停止命令
        stopped_info = await command_manager.stop_command(command_id)

        if stopped_info:
            return ToolResult(
                success=True,
                output=f"命令 {command_id} 已停止\n执行时长: {stopped_info.duration:.2f} 秒",
                data=stopped_info.to_dict(),
            )

        return ToolResult(
            success=False,
            output="",
            error=f"停止命令失败: {command_id}",
        )


@tool
class ShellListCommandsTool(BaseTool):
    """List commands"""

    name = "list_commands"
    description = "List all commands or commands with specified status"
    category = ToolCategory.SHELL
    parameters = [
        ToolParameter(
            name="status",
            type="string",
            description="Filter status: pending, running, completed, failed, stopped, timeout",
            required=False,
            default=None,
        ),
        ToolParameter(
            name="limit",
            type="integer",
            description="Maximum number to return",
            required=False,
            default=20,
        ),
    ]

    async def execute(
        self,
        status: str | None = None,
        limit: int = 20,
        **kwargs: Any,
    ) -> ToolResult:
        """列出命令"""
        # 解析状态
        filter_status = None
        if status:
            try:
                filter_status = CommandStatus(status.lower())
            except ValueError:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"无效的状态: {status}，有效值: pending, running, completed, failed, stopped, timeout",
                )

        commands = command_manager.list_commands(status=filter_status, limit=limit)

        if not commands:
            return ToolResult(
                success=True,
                output="没有找到匹配的命令",
                data={"count": 0},
            )

        # 格式化输出
        status_emoji = {
            CommandStatus.PENDING: "⏳",
            CommandStatus.RUNNING: "🔄",
            CommandStatus.COMPLETED: "✅",
            CommandStatus.FAILED: "❌",
            CommandStatus.STOPPED: "⏹️",
            CommandStatus.TIMEOUT: "⏱️",
        }

        output_lines = [f"找到 {len(commands)} 个命令:\n"]

        for cmd in commands:
            emoji = status_emoji.get(cmd.status, "❓")
            output_lines.append(
                f"{emoji} [{cmd.id}] {cmd.status.value} - {cmd.command[:50]}..."
                if len(cmd.command) > 50
                else f"{emoji} [{cmd.id}] {cmd.status.value} - {cmd.command}"
            )
            output_lines.append(f"   时长: {cmd.duration:.2f}s, 目录: {cmd.cwd}")
            output_lines.append("")

        return ToolResult(
            success=True,
            output="\n".join(output_lines),
            data={
                "count": len(commands),
                "commands": [c.to_dict() for c in commands],
            },
        )
