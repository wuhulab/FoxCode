"""
FoxCode 钩子系统模块 - 统一导出所有钩子组件

这个文件统一导出钩子系统的所有组件，方便外部模块使用。

基础组件:
- HookType: 钩子类型枚举
- HookContext: 钩子上下文
- HookHandler: 钩子处理器
- HookManager: 钩子管理器
- hook_manager: 全局钩子管理器实例
- register_hook: 钩子注册装饰器

钩子集合:
- AppHooks: 应用生命周期钩子
- CommandHooks: 命令执行钩子
- ToolHooks: 工具执行钩子
- SessionHooks: 会话管理钩子
- SkillHooks: 技能执行钩子
- WorkModeHooks: 工作模式钩子
- ConfigHooks: 配置变更钩子
- ServiceHooks: 服务管理钩子

使用方式:
    from foxcode.core.hooks import register_hook, HookType

    @register_hook(HookType.APP_STARTUP)
    async def on_startup(context):
        print("应用启动")
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