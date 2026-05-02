"""
FoxCode - AI 终端编码助手

FoxCode 是一个类似 Claude Code 的终端 AI 编码助手，支持多种 AI 模型，
提供智能代码生成、文件操作、任务规划等功能。

支持 MCP (Model Context Protocol) 和 Skill 技能系统。

核心模块:
- FoxCodeAgent: AI 代理，负责对话和代码生成
- Config: 配置管理，支持多种运行模式
- Session: 会话管理，记录对话历史

Hook 系统:
- HookManager: 钩子管理器，支持事件驱动
- AppHooks / CommandHooks / ToolHooks: 各类钩子

MCP 协议:
- MCPManager: MCP 服务器管理
- MCPTool / MCPResource / MCPPrompt: MCP 工具/资源/提示

Skill 技能:
- SkillManager: 技能管理器
- BaseSkill: 技能基类，自定义技能需继承此类

使用方式:
    from foxcode import FoxCodeAgent, Config

    config = Config.create()
    agent = FoxCodeAgent(config)
    result = await agent.run("帮我写一个排序函数")
"""

__version__ = "0.1.5"
__author__ = "FoxCode"

from foxcode.core.agent import FoxCodeAgent
from foxcode.core.config import Config, MCPConfig, SkillsConfig
from foxcode.services.mcp import (
    MCPManager,
    MCPPrompt,
    MCPResource,
    MCPServerConfig,
    MCPTool,
    MCPToolResult,
    mcp_manager,
)
from foxcode.core.session import Session
from foxcode.core.skill import (
    BaseSkill,
    SkillConfig,
    SkillContext,
    SkillManager,
    SkillPriority,
    SkillResult,
    SkillState,
    SkillTrigger,
    register_builtin_skills,
    skill_manager,
)

from foxcode.core.hooks import (
    HookType,
    HookContext,
    HookManager,
    hook_manager,
    register_hook,
    AppHooks,
    CommandHooks,
    ToolHooks,
    SessionHooks,
    SkillHooks,
    WorkModeHooks,
    ConfigHooks,
    ServiceHooks,
)

__all__ = [
    # Core
    "FoxCodeAgent",
    "Config",
    "Session",
    # Hooks
    "HookType",
    "HookContext",
    "HookManager",
    "hook_manager",
    "register_hook",
    "AppHooks",
    "CommandHooks",
    "ToolHooks",
    "SessionHooks",
    "SkillHooks",
    "WorkModeHooks",
    "ConfigHooks",
    "ServiceHooks",
    # MCP
    "MCPConfig",
    "MCPManager",
    "MCPServerConfig",
    "MCPTool",
    "MCPResource",
    "MCPPrompt",
    "MCPToolResult",
    "mcp_manager",
    # Skill
    "SkillsConfig",
    "BaseSkill",
    "SkillContext",
    "SkillResult",
    "SkillConfig",
    "SkillState",
    "SkillPriority",
    "SkillTrigger",
    "SkillManager",
    "skill_manager",
    "register_builtin_skills",
    # Version
    "__version__",
]
