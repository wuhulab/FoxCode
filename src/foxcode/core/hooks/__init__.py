"""
FoxCode 钩子系统模块

提供钩子定义、注册和执行机制，支持在不同生命周期执行自定义逻辑
"""

from foxcode.core.hooks.base import (
    HookType,
    HookContext,
    HookHandler,
    HookManager,
    hook_manager,
    register_hook,
)
from foxcode.core.hooks.app_hooks import AppHooks
from foxcode.core.hooks.command_hooks import CommandHooks
from foxcode.core.hooks.tool_hooks import ToolHooks
from foxcode.core.hooks.session_hooks import SessionHooks
from foxcode.core.hooks.skill_hooks import SkillHooks
from foxcode.core.hooks.work_mode_hooks import WorkModeHooks
from foxcode.core.hooks.config_hooks import ConfigHooks
from foxcode.core.hooks.service_hooks import ServiceHooks

__all__ = [
    # 基础组件
    "HookType",
    "HookContext",
    "HookHandler",
    "HookManager",
    "hook_manager",
    "register_hook",
    # 钩子集合
    "AppHooks",
    "CommandHooks",
    "ToolHooks",
    "SessionHooks",
    "SkillHooks",
    "WorkModeHooks",
    "ConfigHooks",
    "ServiceHooks",
]