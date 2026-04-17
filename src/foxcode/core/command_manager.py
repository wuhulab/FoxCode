"""
FoxCode 命令管理器模块

管理长时间运行的命令进程，支持状态检查和停止操作
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CommandStatus(str, Enum):
    """命令状态枚举"""
    PENDING = "pending"        # 等待执行
    RUNNING = "running"        # 正在运行
    COMPLETED = "completed"    # 已完成
    FAILED = "failed"          # 执行失败
    STOPPED = "stopped"        # 被停止
    TIMEOUT = "timeout"        # 超时


@dataclass
class CommandInfo:
    """命令信息"""
    id: str                          # 命令唯一标识
    command: str                     # 命令内容
    cwd: str                         # 工作目录
    status: CommandStatus = CommandStatus.PENDING
    process: asyncio.subprocess.Process | None = None
    start_time: float = 0.0
    end_time: float = 0.0
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    timeout: int = 300
    env: dict[str, str] = field(default_factory=dict)
    error: str | None = None

    @property
    def duration(self) -> float:
        """获取命令执行时长（秒）"""
        if self.start_time == 0:
            return 0.0
        if self.end_time > 0:
            return self.end_time - self.start_time
        return time.time() - self.start_time

    @property
    def is_running(self) -> bool:
        """检查命令是否正在运行"""
        return self.status == CommandStatus.RUNNING and self.process is not None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "command": self.command,
            "cwd": self.cwd,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": round(self.duration, 2),
            "exit_code": self.exit_code,
            "timeout": self.timeout,
            "error": self.error,
            "stdout_length": len(self.stdout),
            "stderr_length": len(self.stderr),
        }


class CommandManager:
    """
    命令管理器
    
    管理所有长时间运行的命令进程
    """

    def __init__(self, max_commands: int = 100):
        """
        初始化命令管理器
        
        Args:
            max_commands: 最大保存的命令数量
        """
        self._commands: dict[str, CommandInfo] = {}
        self._max_commands = max_commands
        self._lock = asyncio.Lock()

    def generate_id(self) -> str:
        """生成唯一的命令 ID"""
        return str(uuid.uuid4())[:8]

    async def register_command(
        self,
        command: str,
        cwd: str,
        timeout: int = 300,
        env: dict[str, str] | None = None,
    ) -> CommandInfo:
        """
        注册新命令
        
        Args:
            command: 命令内容
            cwd: 工作目录
            timeout: 超时时间
            env: 环境变量
            
        Returns:
            命令信息
        """
        cmd_id = self.generate_id()
        cmd_info = CommandInfo(
            id=cmd_id,
            command=command,
            cwd=cwd,
            timeout=timeout,
            env=env or {},
        )

        async with self._lock:
            # 清理旧命令
            if len(self._commands) >= self._max_commands:
                await self._cleanup_old_commands()

            self._commands[cmd_id] = cmd_info

        logger.debug(f"注册命令: {cmd_id} - {command}")
        return cmd_info

    async def start_command(
        self,
        cmd_info: CommandInfo,
        process: asyncio.subprocess.Process,
    ) -> None:
        """
        标记命令开始执行
        
        Args:
            cmd_info: 命令信息
            process: 进程对象
        """
        cmd_info.process = process
        cmd_info.status = CommandStatus.RUNNING
        cmd_info.start_time = time.time()

        logger.info(f"命令开始执行: {cmd_info.id}")

    async def complete_command(
        self,
        cmd_id: str,
        exit_code: int,
        stdout: str = "",
        stderr: str = "",
    ) -> CommandInfo | None:
        """
        标记命令完成
        
        Args:
            cmd_id: 命令 ID
            exit_code: 退出码
            stdout: 标准输出
            stderr: 标准错误
            
        Returns:
            命令信息
        """
        async with self._lock:
            cmd_info = self._commands.get(cmd_id)
            if not cmd_info:
                return None

            cmd_info.end_time = time.time()
            cmd_info.exit_code = exit_code
            cmd_info.stdout = stdout
            cmd_info.stderr = stderr
            cmd_info.process = None

            if exit_code == 0:
                cmd_info.status = CommandStatus.COMPLETED
            else:
                cmd_info.status = CommandStatus.FAILED

            logger.info(f"命令完成: {cmd_id}, 退出码: {exit_code}, 耗时: {cmd_info.duration:.2f}s")
            return cmd_info

    async def fail_command(
        self,
        cmd_id: str,
        error: str,
    ) -> CommandInfo | None:
        """
        标记命令失败
        
        Args:
            cmd_id: 命令 ID
            error: 错误信息
            
        Returns:
            命令信息
        """
        async with self._lock:
            cmd_info = self._commands.get(cmd_id)
            if not cmd_info:
                return None

            cmd_info.end_time = time.time()
            cmd_info.status = CommandStatus.FAILED
            cmd_info.error = error
            cmd_info.process = None

            logger.error(f"命令失败: {cmd_id}, 错误: {error}")
            return cmd_info

    async def timeout_command(self, cmd_id: str) -> CommandInfo | None:
        """
        标记命令超时
        
        Args:
            cmd_id: 命令 ID
            
        Returns:
            命令信息
        """
        async with self._lock:
            cmd_info = self._commands.get(cmd_id)
            if not cmd_info:
                return None

            cmd_info.end_time = time.time()
            cmd_info.status = CommandStatus.TIMEOUT
            cmd_info.error = f"命令执行超时（{cmd_info.timeout}秒）"
            cmd_info.process = None

            logger.warning(f"命令超时: {cmd_id}")
            return cmd_info

    async def stop_command(self, cmd_id: str) -> CommandInfo | None:
        """
        停止命令
        
        Args:
            cmd_id: 命令 ID
            
        Returns:
            命令信息
        """
        async with self._lock:
            cmd_info = self._commands.get(cmd_id)
            if not cmd_info:
                return None

            if not cmd_info.is_running:
                return cmd_info

            # 终止进程
            if cmd_info.process:
                try:
                    cmd_info.process.kill()
                    await cmd_info.process.wait()
                except ProcessLookupError:
                    pass  # 进程已经结束
                except Exception as e:
                    logger.error(f"停止命令时出错: {e}")

            cmd_info.end_time = time.time()
            cmd_info.status = CommandStatus.STOPPED
            cmd_info.error = "命令被用户停止"
            cmd_info.process = None

            logger.info(f"命令已停止: {cmd_id}")
            return cmd_info

    def get_command(self, cmd_id: str) -> CommandInfo | None:
        """
        获取命令信息
        
        Args:
            cmd_id: 命令 ID
            
        Returns:
            命令信息
        """
        return self._commands.get(cmd_id)

    def list_commands(
        self,
        status: CommandStatus | None = None,
        limit: int = 20,
    ) -> list[CommandInfo]:
        """
        列出命令
        
        Args:
            status: 过滤状态
            limit: 最大返回数量
            
        Returns:
            命令列表
        """
        commands = list(self._commands.values())

        # 按开始时间倒序排序
        commands.sort(key=lambda x: x.start_time, reverse=True)

        # 过滤状态
        if status:
            commands = [c for c in commands if c.status == status]

        return commands[:limit]

    async def _cleanup_old_commands(self) -> None:
        """清理旧命令"""
        # 保留正在运行的命令和最近完成的命令
        running = [c for c in self._commands.values() if c.is_running]
        completed = [
            c for c in self._commands.values()
            if not c.is_running
        ]

        # 按结束时间排序，保留最近的
        completed.sort(key=lambda x: x.end_time, reverse=True)
        keep_count = self._max_commands - len(running)

        # 重建命令字典
        self._commands.clear()
        for cmd in running:
            self._commands[cmd.id] = cmd
        for cmd in completed[:keep_count]:
            self._commands[cmd.id] = cmd

        logger.debug(f"清理旧命令，当前保留 {len(self._commands)} 个")


# 全局命令管理器实例
command_manager = CommandManager()
