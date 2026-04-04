"""
FoxCode - 一个强大的 AI 终端编码助手

FoxCode 是一个类似 Claude Code 的终端 AI 编码助手，支持多种 AI 模型，
提供智能代码生成、文件操作、任务规划等功能。

支持 MCP (Model Context Protocol) 和 Skill 技能系统。
"""

__version__ = "0.1.0"
__author__ = "FoxCode"

from foxcode.core.agent import FoxCodeAgent
from foxcode.core.config import Config, MCPConfig, SkillsConfig
from foxcode.core.session import Session
from foxcode.core.mcp import (
    MCPManager,
    MCPServerConfig,
    MCPTool,
    MCPResource,
    MCPPrompt,
    MCPToolResult,
    mcp_manager,
)
from foxcode.core.skill import (
    BaseSkill,
    SkillContext,
    SkillResult,
    SkillConfig,
    SkillState,
    SkillPriority,
    SkillTrigger,
    SkillManager,
    skill_manager,
    register_builtin_skills,
)

__all__ = [
    # Core
    "FoxCodeAgent",
    "Config",
    "Session",
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
