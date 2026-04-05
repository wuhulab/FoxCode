"""
FoxCode Agent 模块

核心 AI 代理实现
支持初始化代理和编码代理双模式
支持 MCP (Model Context Protocol) 和 Skill 技能系统
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import xml.etree.ElementTree as ET
from typing import Any, AsyncIterator

from foxcode.core.config import AgentRole, Config, RunMode
from foxcode.core.handoff import HandoffArtifact, TaskItem
from foxcode.core.context_reset import ContextResetManager, ResetTrigger
from foxcode.core.evaluator import EvaluatorAgent
from foxcode.core.message import Conversation, Message, MessageRole
from foxcode.core.providers import BaseModelProvider, ModelResponse, create_model_provider
from foxcode.core.session import Session
from foxcode.core.statistics import stats_manager
from foxcode.tools.base import ToolResult, registry

logger = logging.getLogger(__name__)

# 重试配置
MAX_RETRIES = 5  # 最大重试次数
INITIAL_RETRY_DELAY = 2.0  # 初始重试延迟（秒）
MAX_RETRY_DELAY = 60.0  # 最大重试延迟（秒）
RETRY_BACKOFF_FACTOR = 2.0  # 退避因子


def _is_retryable_error(error: Exception) -> bool:
    """
    检查错误是否可重试
    
    Args:
        error: 异常对象
        
    Returns:
        是否可重试
    """
    error_str = str(error).lower()
    
    # 403 错误 - RPM 限制
    if "403" in error_str:
        return True
    if "rpm limit" in error_str:
        return True
    if "rate limit" in error_str:
        return True
    if "too many requests" in error_str:
        return True
    
    # 429 错误 - 请求过多
    if "429" in error_str:
        return True
    
    # 超时错误
    if "timeout" in error_str:
        return True
    
    # 连接错误
    if "connection" in error_str:
        return True
    
    return False


def _calculate_retry_delay(retry_count: int) -> float:
    """
    计算重试延迟时间（指数退避）
    
    Args:
        retry_count: 当前重试次数（从 0 开始）
        
    Returns:
        延迟时间（秒）
    """
    delay = INITIAL_RETRY_DELAY * (RETRY_BACKOFF_FACTOR ** retry_count)
    return min(delay, MAX_RETRY_DELAY)


# Default System Prompt
SYSTEM_PROMPT = """You are FoxCode, an AI coding assistant.

================================================================================
## STOP! READ THIS FIRST!
================================================================================

You have tools to read files, execute commands, and search code.

**RULE 1: NEVER ask the user for information! You have tools, get it yourself!**

**RULE 2: When you receive a request, IMMEDIATELY output a tool call, do NOT talk first!**

**RULE 3: NEVER say "please provide", "please share", "please tell me"!**

================================================================================
## EXAMPLES
================================================================================

User: "analyze project structure"
Your response (output immediately, do NOT talk):
```xml
<function=list_directory>
<parameter=path>{working_dir}</parameter>
</function>
```

User: "check main.py"
Your response (output immediately, do NOT talk):
```xml
<function=read_file>
<parameter=file_path>{working_dir}\\main.py</parameter>
</function>
```

User: "search TODO"
Your response (output immediately, do NOT talk):
```xml
<function=grep>
<parameter=pattern>TODO</parameter>
<parameter=path>{working_dir}</parameter>
<parameter=output_mode>content</parameter>
<parameter=-n>true</parameter>
</function>
```

================================================================================
## TOOLS
================================================================================

| Tool | Purpose | Required Params |
|------|---------|-----------------|
| list_directory | List directory | path |
| read_file | Read file | file_path |
| write_file | Write file | file_path, content |
| edit_file | Edit file | file_path, old_text, new_text |
| grep | Search content | pattern |
| glob | Find files | pattern |
| search_codebase | Semantic search | query |
| shell_execute | Run command | command |

================================================================================
## TOOL CALL FORMAT
================================================================================

```xml
<function=tool_name>
<parameter=param_name>value</parameter>
</function>
```

**IMPORTANT**:
- Call ONE tool at a time
- Wait for result before next action
- Use absolute file paths

================================================================================
## WORK PRINCIPLES
================================================================================

1. **Be Proactive**: Call tools immediately, don't ask user
2. **Be Safe**: Be careful with file deletion
3. **Be Clear**: Explain your actions

## Current Environment

Working directory: {working_dir}
Run mode: {run_mode}
"""

# Initializer Agent System Prompt
INITIALIZER_PROMPT = """You are FoxCode Initializer Agent.

================================================================================
## STOP! READ THIS FIRST!
================================================================================

You have tools to read files, execute commands, and search code.

**RULE 1: NEVER ask the user for information! You have tools, get it yourself!**

**RULE 2: When you receive a request, IMMEDIATELY output a tool call, do NOT talk first!**

**RULE 3: NEVER say "please provide", "please share", "please tell me"!**

================================================================================
## YOUR TASK
================================================================================

Set up the initial environment for the project, create feature list and progress files.

**IMPORTANT: All FoxCode internal files MUST be created in the `.foxcode/` directory:**
- Feature list: `{working_dir}/.foxcode/features.md`
- Progress file: `{working_dir}/.foxcode/progress.md`
- Summary file: `{working_dir}/.foxcode/summary.md`

First, create the `.foxcode/` directory if it does not exist, then create the files inside it.

================================================================================
## TOOLS
================================================================================

| Tool | Purpose | Required Params |
|------|---------|-----------------|
| list_directory | List directory | path |
| read_file | Read file | file_path |
| write_file | Write file | file_path, content |
| glob | Find files | pattern |
| shell_execute | Run command | command |

================================================================================
## TOOL CALL FORMAT
================================================================================

```xml
<function=tool_name>
<parameter=param_name>value</parameter>
</function>
```

**IMPORTANT**:
- Call ONE tool at a time
- Wait for result before next action
- Use absolute file paths

## Current Environment

Working directory: {working_dir}
Run mode: {run_mode}

{context_info}
"""

# Coder Agent System Prompt
CODER_PROMPT = """You are FoxCode Coder Agent.

## Current Project Status

{context_info}

================================================================================
## STOP! READ THIS FIRST!
================================================================================

You have tools to read files, execute commands, and search code.

**RULE 1: NEVER ask the user for information! You have tools, get it yourself!**

**RULE 2: When you receive a request, IMMEDIATELY output a tool call, do NOT talk first!**

**RULE 3: NEVER say "please provide", "please share", "please tell me"!**

================================================================================
## TOOLS
================================================================================

| Tool | Purpose | Required Params |
|------|---------|-----------------|
| read_file | Read file | file_path |
| edit_file | Edit file | file_path, old_text, new_text |
| write_file | Write file | file_path, content |
| grep | Search content | pattern |
| glob | Find files | pattern |
| shell_execute | Run command | command |

================================================================================
## TOOL CALL FORMAT
================================================================================

```xml
<function=tool_name>
<parameter=param_name>value</parameter>
</function>
```

**IMPORTANT**:
- Call ONE tool at a time
- Wait for result before next action
- Use absolute file paths

================================================================================
## WORK PRINCIPLES
================================================================================

1. **Incremental Work**: Handle one feature at a time
2. **Quality Code**: Follow project code style
3. **Update Progress**: Update status after completion

## Current Environment

Working directory: {working_dir}
Run mode: {run_mode}
"""


class FoxCodeAgent:
    """
    FoxCode AI 代理
    
    核心代理类，负责处理用户请求、调用模型、执行工具
    支持初始化代理和编码代理双模式
    支持 MCP (Model Context Protocol) 和 Skill 技能系统
    """
    
    def __init__(self, config: Config, force_mode: str | None = None):
        """
        初始化代理
        
        Args:
            config: 配置实例
            force_mode: 强制模式 ("initializer" 或 "coder")，None 则自动检测
        """
        self.config = config
        self.session = Session(config)
        self.model_provider: BaseModelProvider | None = None
        self._initialized = False
        
        # 已执行的工具调用记录（用于防重复）
        # 格式: {(tool_name, frozenset(sorted_params)): execution_count}
        self._executed_tools: dict[tuple[str, frozenset], int] = {}
        
        # 会话模式
        self._force_mode = force_mode
        self._session_type = None  # 延迟检测
        
        # 设置工具配置
        registry.set_config(config.tools)
        
        # MCP 管理器
        self._mcp_manager = None
        self._mcp_initialized = False
        
        # Skill 管理器
        self._skill_manager = None
        self._skills_initialized = False
        
        # 多代理模式相关
        self._agent_role: AgentRole = AgentRole.GENERATOR
        self._orchestrator: "MultiAgentOrchestrator | None" = None
        self._context_reset_manager: "ContextResetManager | None" = None
    
    @property
    def session_type(self):
        """获取会话类型（延迟检测）"""
        if self._session_type is None:
            if self._force_mode == "initializer":
                from foxcode.core.context_bridge import SessionType
                self._session_type = SessionType.INITIALIZER
            elif self._force_mode == "coder":
                from foxcode.core.context_bridge import SessionType
                self._session_type = SessionType.CODER
            else:
                # 自动检测
                self._session_type = self.session.get_session_type()
        return self._session_type
    
    @property
    def is_initializer(self) -> bool:
        """是否为初始化代理模式"""
        from foxcode.core.context_bridge import SessionType
        return self.session_type == SessionType.INITIALIZER
    
    @property
    def is_coder(self) -> bool:
        """是否为编码代理模式"""
        from foxcode.core.context_bridge import SessionType
        return self.session_type == SessionType.CODER
    
    @property
    def agent_role(self) -> AgentRole:
        """
        获取当前代理角色
        
        返回当前代理在多代理系统中承担的角色类型。
        代理角色决定了代理在任务处理中的职责和行为模式。
        
        Returns:
            AgentRole: 当前代理角色（PLANNER、GENERATOR 或 EVALUATOR）
        """
        return self._agent_role
    
    def switch_role(self, role: AgentRole) -> None:
        """
        切换代理角色（带权限控制）
        
        将当前代理的角色切换为指定的角色类型。切换角色后，
        会同步更新会话中的代理角色状态，后续的任务处理将按照新角色的职责进行。
        
        权限控制：
        - 记录角色切换审计日志
        - 检查角色切换频率限制
        - 验证角色切换权限
        
        Args:
            role: 新的代理角色，可选值为：
                - AgentRole.PLANNER: 规划器代理
                - AgentRole.GENERATOR: 生成器代理
                - AgentRole.EVALUATOR: 评估器代理
                
        Raises:
            PermissionError: 角色切换权限不足
            
        Example:
            >>> agent.switch_role(AgentRole.EVALUATOR)
            >>> print(agent.agent_role)  # AgentRole.EVALUATOR
        """
        if not self._check_role_switch_permission(role):
            raise PermissionError(f"无权限切换到角色: {role.value}")
        
        old_role = self._agent_role
        self._agent_role = role
        self.session.switch_agent_role(role)
        
        self._record_role_switch_audit(old_role, role)
        
        logger.info(f"代理角色已切换: {old_role.value} -> {role.value}")
    
    def _check_role_switch_permission(self, target_role: AgentRole) -> bool:
        """
        检查角色切换权限
        
        Args:
            target_role: 目标角色
            
        Returns:
            是否有权限切换
        """
        if not hasattr(self, '_role_switch_history'):
            self._role_switch_history = []
        
        import time
        current_time = time.time()
        
        self._role_switch_history = [
            t for t in self._role_switch_history
            if current_time - t < 60
        ]
        
        if len(self._role_switch_history) >= 10:
            logger.warning(f"角色切换频率过高，已拒绝切换请求")
            return False
        
        self._role_switch_history.append(current_time)
        
        if hasattr(self.config, 'allowed_roles'):
            allowed_roles = getattr(self.config, 'allowed_roles', None)
            if allowed_roles and target_role not in allowed_roles:
                logger.warning(f"角色 {target_role.value} 不在允许列表中")
                return False
        
        return True
    
    def _record_role_switch_audit(self, old_role: AgentRole, new_role: AgentRole) -> None:
        """
        记录角色切换审计日志
        
        Args:
            old_role: 原角色
            new_role: 新角色
        """
        import time
        from datetime import datetime
        
        audit_record = {
            "timestamp": datetime.now().isoformat(),
            "unix_time": time.time(),
            "old_role": old_role.value,
            "new_role": new_role.value,
            "session_id": self.session.session_id,
        }
        
        if not hasattr(self, '_role_audit_log'):
            self._role_audit_log = []
        self._role_audit_log.append(audit_record)
        
        if len(self._role_audit_log) > 100:
            self._role_audit_log = self._role_audit_log[-100:]
        
        logger.debug(f"角色切换审计: {audit_record}")
    
    def get_context_reset_manager(self) -> ContextResetManager:
        """
        获取上下文重置管理器
        
        返回当前代理的上下文重置管理器实例。如果实例不存在，则创建一个新的实例。
        上下文重置管理器用于监控上下文窗口使用情况，并在必要时触发重置操作。
        
        Returns:
            ContextResetManager: 上下文重置管理器实例
            
        Example:
            >>> manager = agent.get_context_reset_manager()
            >>> usage = manager.get_context_usage(session)
        """
        if self._context_reset_manager is None:
            self._context_reset_manager = ContextResetManager(config=self.config)
        return self._context_reset_manager
    
    def get_orchestrator(self) -> "MultiAgentOrchestrator":
        """
        获取多代理协调器
        
        返回当前代理的多代理协调器实例。如果实例不存在，则创建一个新的实例。
        多代理协调器用于管理多个代理之间的协作和任务分配。
        
        Returns:
            MultiAgentOrchestrator: 多代理协调器实例
            
        Example:
            >>> orchestrator = agent.get_orchestrator()
            >>> orchestrator.assign_task(task)
        """
        if self._orchestrator is None:
            from foxcode.core.orchestrator import MultiAgentOrchestrator
            self._orchestrator = MultiAgentOrchestrator(
                config=self.config,
                session=self.session,
            )
        return self._orchestrator
    
    async def initialize(self) -> None:
        """初始化代理"""
        if self._initialized:
            return
        
        try:
            # 初始化模型提供者
            self.model_provider = create_model_provider(self.config.model)
            await self.model_provider.initialize()
            
            # 如果启用长时间运行模式，加载进度信息
            if self.config.long_running.enable_long_running_mode:
                await self._load_progress_context()
            
            # 初始化 MCP 系统
            await self._initialize_mcp()
            
            # 初始化 Skill 系统
            await self._initialize_skills()
            
            self._initialized = True
            logger.info(f"FoxCode Agent initialized (mode: {self.session_type.value})")
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            raise
    
    async def _initialize_mcp(self) -> None:
        """初始化 MCP 系统"""
        if not self.config.mcp.enabled:
            logger.debug("MCP is disabled")
            return
        
        try:
            from foxcode.core.mcp import mcp_manager, MCPServerConfig
            
            self._mcp_manager = mcp_manager
            
            # 加载配置中的 MCP 服务器
            for server_config in self.config.mcp.servers:
                if server_config.enabled:
                    config = MCPServerConfig(
                        name=server_config.name,
                        command=server_config.command,
                        args=server_config.args,
                        env=server_config.env,
                        cwd=server_config.cwd,
                        enabled=server_config.enabled,
                        auto_start=server_config.auto_start,
                    )
                    await mcp_manager.add_server(config)
            
            self._mcp_initialized = True
            logger.info(f"MCP initialized with {len(mcp_manager.list_servers())} servers")
            
        except Exception as e:
            logger.warning(f"Failed to initialize MCP: {e}")
    
    async def _initialize_skills(self) -> None:
        """初始化 Skill 系统"""
        if not self.config.skills.enabled:
            logger.debug("Skills system is disabled")
            return
        
        try:
            from foxcode.core.skill import skill_manager, register_builtin_skills
            
            self._skill_manager = skill_manager
            
            # 注册内置技能
            if self.config.skills.enable_builtin:
                register_builtin_skills()
            
            # 加载配置中的技能
            for skill_config in self.config.skills.skills:
                if not skill_config.enabled:
                    skill_manager.disable_skill(skill_config.name)
            
            # 自动发现技能
            if self.config.skills.auto_discover:
                skills_dir = self.config.working_dir / self.config.skills.skills_dir
                if skills_dir.exists():
                    await skill_manager.load_from_directory(skills_dir)
            
            # 初始化所有技能
            await skill_manager.initialize_all()
            
            self._skills_initialized = True
            logger.info(f"Skills initialized: {len(skill_manager.list_skills())} skills")
            
        except Exception as e:
            logger.warning(f"Failed to initialize skills: {e}")
    
    async def _load_progress_context(self) -> None:
        """加载进度上下文"""
        try:
            progress_info = self.session.load_progress_info()
            logger.info(f"Loaded progress context: {len(progress_info)} items")
        except Exception as e:
            logger.warning(f"Failed to load progress context: {e}")
    
    def _get_system_prompt(self) -> str:
        """
        获取系统提示词
        
        根据会话类型选择不同的提示词模板
        并注入 MCP 工具和 Skill 技能描述
        
        支持Claude兼容模式：当模型名称包含"claude"时，
        将提示词中的"FoxCode"替换为"Claude"
        """
        # 检测是否为Claude模型（Claude模型对名称比较敏感）
        model_name = self.config.model.model_name.lower()
        is_claude_model = "claude" in model_name
        
        # 基础参数
        base_params = {
            "working_dir": str(self.config.working_dir),
            "run_mode": self.config.run_mode.value,
        }
        
        # 如果未启用长时间运行模式，使用默认提示词
        if not self.config.long_running.enable_long_running_mode:
            base_prompt = SYSTEM_PROMPT.format(**base_params)
        else:
            # 构建上下文信息
            context_info = self._build_context_info()
            
            if self.is_initializer:
                # 初始化代理模式
                base_prompt = INITIALIZER_PROMPT.format(
                    **base_params,
                    context_info=context_info,
                )
            else:
                # 编码代理模式
                base_prompt = CODER_PROMPT.format(
                    **base_params,
                    context_info=context_info,
                )
        
        # Claude兼容模式：将FoxCode替换为Claude
        if is_claude_model:
            base_prompt = base_prompt.replace("FoxCode", "Claude")
            logger.debug("Claude compatibility mode enabled: replaced 'FoxCode' with 'Claude' in system prompt")
        
        # 注入 MCP 工具描述
        mcp_prompt = self._get_mcp_prompt_injection()
        if mcp_prompt:
            base_prompt += "\n\n" + mcp_prompt
        
        # 注入 Skill 技能描述
        skill_prompt = self._get_skill_prompt_injection()
        if skill_prompt:
            base_prompt += "\n\n" + skill_prompt
        
        # 注入 OpenSpace 经验知识
        open_space_prompt = self._get_open_space_prompt_injection()
        if open_space_prompt:
            base_prompt += "\n\n" + open_space_prompt
        
        # 检查是否有恢复上下文
        handoff_context = self._get_handoff_context()
        if handoff_context:
            base_prompt += "\n\n" + handoff_context
        
        return base_prompt
    
    def _get_mcp_prompt_injection(self) -> str:
        """获取 MCP 工具提示注入"""
        if not self._mcp_initialized or not self._mcp_manager:
            return ""
        
        try:
            return self._mcp_manager.get_tools_for_prompt()
        except Exception as e:
            logger.warning(f"Failed to get MCP prompt injection: {e}")
            return ""
    
    def _get_skill_prompt_injection(self) -> str:
        """获取 Skill 技能提示注入"""
        if not self._skills_initialized or not self._skill_manager:
            return ""
        
        try:
            return self._skill_manager.get_prompt_injections()
        except Exception as e:
            logger.warning(f"Failed to get skill prompt injection: {e}")
            return ""
    
    def _get_open_space_prompt_injection(self) -> str:
        """
        获取 OpenSpace 经验知识提示注入
        
        从全局 OpenSpace 管理器加载 AI 经验知识并注入到系统提示中。
        这些经验知识帮助 AI 避免重复踩坑。
        
        Returns:
            格式化的经验知识提示内容
        """
        # 检查是否启用 OpenSpace
        if not self.config.open_space.enabled:
            return ""
        
        try:
            from foxcode.core.open_space import get_open_space_manager
            
            # 使用工作目录获取管理器（优先加载项目级经验）
            manager = get_open_space_manager(working_dir=self.config.working_dir)
            
            # 检查管理器是否启用
            if not manager.enabled:
                return ""
            
            return manager.get_prompt_injection()
            
        except Exception as e:
            logger.warning(f"Failed to get OpenSpace prompt injection: {e}")
            return ""
    
    def _get_handoff_context(self) -> str:
        """
        获取 HandoffArtifact 恢复上下文
        
        从最近的 HandoffArtifact 文件中加载状态信息，并生成可注入系统提示词的上下文。
        此方法用于在会话恢复时注入之前的工作状态，使代理能够无缝继续工作。
        
        Returns:
            str: 恢复上下文文本，如果没有找到 HandoffArtifact 则返回空字符串
            
        Example:
            >>> context = agent._get_handoff_context()
            >>> if context:
            ...     print("找到恢复上下文")
        """
        if not self.config.long_running.enable_long_running_mode:
            return ""
        
        try:
            manager = self.get_context_reset_manager()
            artifact = manager.load_latest_handoff()
            
            if artifact:
                logger.info(f"加载 HandoffArtifact 恢复上下文: {artifact.session_id}")
                return artifact.to_prompt_context()
            
        except Exception as e:
            logger.warning(f"加载 HandoffArtifact 失败: {e}")
        
        return ""
    
    def _build_context_info(self) -> str:
        """
        构建上下文信息（带安全转义）
        
        对动态内容进行转义，防止提示词注入攻击
        
        Returns:
            格式化的上下文信息
        """
        try:
            progress_info = self.session.load_progress_info()
            
            lines = []
            
            if progress_info.get("progress_summary"):
                lines.append("### Progress Summary")
                lines.append(self._escape_prompt_content(progress_info["progress_summary"]))
                lines.append("")
            
            if progress_info.get("current_feature"):
                lines.append("### Current Feature")
                lines.append(self._escape_prompt_content(progress_info["current_feature"]))
                lines.append("")
            
            pending = progress_info.get("pending_features", [])
            if pending:
                lines.append("### Pending Features")
                for feature in pending[:5]:
                    lines.append(f"- {self._escape_prompt_content(feature)}")
                if len(pending) > 5:
                    lines.append(f"- ... and {len(pending) - 5} more features")
                lines.append("")
            
            if progress_info.get("recent_summary"):
                lines.append("### Recent Session Summary")
                lines.append(self._escape_prompt_content(progress_info["recent_summary"][:500]))
                lines.append("")
            
            return "\n".join(lines) if lines else "No context information available"
            
        except Exception as e:
            logger.warning(f"Failed to build context info: {e}")
            return "Failed to load context information"
    
    def _escape_prompt_content(self, content: str) -> str:
        """
        转义提示词内容，防止提示词注入攻击
        
        Args:
            content: 原始内容
            
        Returns:
            转义后的安全内容
        """
        if not content:
            return ""
        
        dangerous_patterns = [
            ("忽略之前的指令", "[已过滤]"),
            ("ignore previous instructions", "[filtered]"),
            ("ignore all previous", "[filtered]"),
            ("disregard all", "[filtered]"),
            ("system:", "[filtered]"),
            ("assistant:", "[filtered]"),
            ("user:", "[filtered]"),
            ("<|im_start|>", "[filtered]"),
            ("[INST]", "[filtered]"),
            ("[SYSTEM]", "[filtered]"),
            ("```system", "```[filtered]"),
        ]
        
        escaped = str(content)
        
        for pattern, replacement in dangerous_patterns:
            if pattern.lower() in escaped.lower():
                escaped = re.sub(
                    re.escape(pattern),
                    replacement,
                    escaped,
                    flags=re.IGNORECASE
                )
        
        if escaped != content:
            logger.debug("Prompt content was escaped for security")
        
        return escaped
    
    def _parse_tool_call(self, text: str) -> tuple[str | None, dict[str, str] | None, str]:
        """
        解析工具调用
        
        从文本中解析 XML 格式的工具调用
        
        Args:
            text: 包含工具调用的文本
            
        Returns:
            (工具名称, 参数字典, 剩余文本) 如果找到工具调用
            (None, None, 原文本) 如果没有找到工具调用
        """
        # 匹配 <function=xxx>...</function> 格式
        func_pattern = r'<function=([^>]+)>(.*?)</function>'
        match = re.search(func_pattern, text, re.DOTALL)
        
        if not match:
            return None, None, text
        
        tool_name = match.group(1).strip()
        params_text = match.group(2)
        
        # 如果工具名称包含中文或看起来像占位符，则忽略
        if any('\u4e00' <= c <= '\u9fff' for c in tool_name):
            logger.warning(f"Ignoring invalid tool name (contains Chinese): {tool_name}")
            return None, None, text
        
        # 如果工具名称是 "工具名称" 这样的占位符，忽略
        if tool_name.lower() in ["工具名称", "tool_name", "xxx", "name"]:
            logger.warning(f"Ignoring placeholder tool name: {tool_name}")
            return None, None, text
        
        # 从注册表获取有效工具名称
        try:
            registered_tools = registry.list_tools()
            valid_tool_names = [t["name"] for t in registered_tools]
        except Exception:
            # 如果无法获取注册表，使用默认列表
            valid_tool_names = [
                "read_file", "write_file", "edit_file", "list_directory",
                "glob", "grep", "search_codebase", "shell_execute",
                "delete_file", "search_in_file", "shell_check_status", "shell_stop"
            ]
        
        # 检查是否是已知工具
        if tool_name not in valid_tool_names:
            # 尝试模糊匹配
            from difflib import get_close_matches
            matches = get_close_matches(tool_name, valid_tool_names, n=1, cutoff=0.6)
            if matches:
                logger.info(f"Tool name '{tool_name}' might be a typo for '{matches[0]}'")
                tool_name = matches[0]
            else:
                logger.warning(f"Unknown tool name: {tool_name}, available tools: {valid_tool_names}")
                return None, None, text
        
        # 解析参数
        params = {}
        param_pattern = r'<parameter=([^>]+)>(.*?)</parameter>'
        for param_match in re.finditer(param_pattern, params_text, re.DOTALL):
            param_name = param_match.group(1).strip()
            param_value = param_match.group(2).strip()
            params[param_name] = param_value
        
        # 获取工具调用前后的文本
        pre_text = text[:match.start()]
        post_text = text[match.end():]
        remaining = pre_text + post_text
        
        logger.info(f"Parsed tool call: {tool_name}, params: {params}")
        return tool_name, params, remaining
    
    def _make_tool_key(self, tool_name: str, params: dict[str, str]) -> tuple[str, frozenset]:
        """
        生成工具调用的唯一键（用于防重复检测）
        
        Args:
            tool_name: 工具名称
            params: 工具参数
            
        Returns:
            可哈希的键元组
        """
        # 将参数排序后转为 frozenset，确保相同参数生成相同的键
        sorted_params = tuple(sorted(params.items()))
        return (tool_name, sorted_params)
    
    async def chat(self, user_input: str) -> AsyncIterator[str]:
        """
        处理用户输入并生成响应
        
        实现工具调用循环：当模型输出工具调用时，执行工具并将结果返回给模型
        支持 Skill 技能触发和 MCP 工具调用
        
        Args:
            user_input: 用户输入
            
        Yields:
            响应文本片段
        """
        if not self._initialized:
            await self.initialize()
        
        # 检查并执行触发的技能
        if self._skills_initialized and self._skill_manager:
            skill_results = await self._process_skills(user_input)
            for skill_name, result in skill_results:
                if result.output:
                    yield f"\n🎯 Skill '{skill_name}' activated:\n{result.output}\n\n"
                if not result.should_continue:
                    return
                if result.modified_input:
                    user_input = result.modified_input
        
        # 添加用户消息
        self.session.add_user_message(user_input)
        
        # 清空本次对话的工具执行记录
        self._executed_tools.clear()
        
        # 工具调用循环（无次数限制，通过防重复机制控制）
        total_response = ""
        
        while True:
            # 获取模型响应
            full_response = ""
            retry_count = 0
            
            while retry_count < MAX_RETRIES:
                try:
                    # 流式获取响应
                    async for chunk in self.model_provider.stream_chat(
                        self.session.conversation,
                        system_prompt=self._get_system_prompt(),
                    ):
                        full_response += chunk
                        yield chunk
                    
                    total_response += full_response
                    break  # 成功获取响应，退出重试循环
                    
                except Exception as e:
                    # 检查是否可重试
                    if _is_retryable_error(e) and retry_count < MAX_RETRIES - 1:
                        retry_count += 1
                        delay = _calculate_retry_delay(retry_count - 1)
                        
                        logger.warning(
                            f"Request failed (retry {retry_count}/{MAX_RETRIES}): {e}"
                        )
                        logger.info(f"Waiting {delay:.1f} seconds before retry...")
                        
                        yield f"\n\n⏳ Request rate limited, retrying in {delay:.1f}s ({retry_count}/{MAX_RETRIES})...\n"
                        
                        await asyncio.sleep(delay)
                        full_response = ""  # 重置响应
                        continue
                    else:
                        # 不可重试或达到最大重试次数
                        logger.error(f"Failed to generate response: {e}")
                        yield f"\n\n❌ Error: {str(e)}"
                        return
            
            # 检查上下文重置
            if await self.check_context_reset():
                yield "\n\n⚠️ 上下文已重置，继续工作...\n\n"
            
            # 检测上下文焦虑
            if self.config.long_running.enable_long_running_mode:
                is_anxious, anxiety_reason = self.detect_anxiety_in_output(full_response)
                if is_anxious:
                    logger.warning(f"检测到上下文焦虑: {anxiety_reason}")
                    yield f"\n\n⚠️ 检测到可能的上下文焦虑: {anxiety_reason}\n"
                    yield "请继续完成任务，不要过早结束。\n\n"
            
            # 检查是否有工具调用
            tool_name, tool_params, remaining_text = self._parse_tool_call(full_response)
            
            if tool_name is None:
                # 没有工具调用，结束循环
                logger.debug("No tool call detected, ending conversation")
                break
            
            # 检查是否重复调用
            tool_key = self._make_tool_key(tool_name, tool_params or {})
            execution_count = self._executed_tools.get(tool_key, 0)
            
            if execution_count > 0:
                # 重复调用，提示模型并跳过执行
                logger.warning(f"Duplicate tool call detected: {tool_name}, params: {tool_params}, executed {execution_count} times")
                yield f"\n\n⚠️ Duplicate call detected: {tool_name} (executed {execution_count} times), skipping.\n\n"
                
                # 添加提示消息，引导模型继续
                repeat_msg = (
                    f"<tool_result>\n"
                    f"<tool_name>{tool_name}</tool_name>\n"
                    f"<success>false</success>\n"
                    f"<error>Duplicate call detected: This tool call has been executed {execution_count} times. Do not call the same tool with the same parameters. Continue with existing results or try a different approach.</error>\n"
                    f"</tool_result>\n\n"
                    f"Please continue with the information you already have, do not repeat the same tool call."
                )
                self.session.add_user_message(repeat_msg)
                continue
            
            # 有工具调用，执行工具
            logger.info(f"Executing tool: {tool_name}, params: {tool_params}")
            
            # 记录工具调用
            self._executed_tools[tool_key] = execution_count + 1
            
            # 输出工具执行提示
            yield f"\n\n🔧 Executing tool: {tool_name}\n"
            yield f"   Params: {tool_params}\n\n"
            
            # 执行工具
            try:
                result = await self.execute_tool(tool_name, **(tool_params or {}))
                
                if result.success:
                    yield f"✅ Tool executed successfully:\n```\n{result.output}\n```\n\n"
                else:
                    yield f"❌ Tool execution failed: {result.error}\n\n"
                
                # 将工具结果添加到对话，使用更清晰的格式
                tool_result_message = (
                    f"<tool_result>\n"
                    f"<tool_name>{tool_name}</tool_name>\n"
                    f"<success>{result.success}</success>\n"
                    f"<output>\n{result.output}\n</output>\n"
                )
                if result.error:
                    tool_result_message += f"<error>{result.error}</error>\n"
                    # 添加恢复指导
                    if "missing required parameter" in result.error.lower():
                        tool_result_message += "\n<hint>Check tool call format, ensure all required parameters are provided. Correct format:</hint>\n"
                        tool_result_message += "<function=tool_name>\n<parameter=param_name>value</parameter>\n</function>\n"
                    elif "not found" in result.error.lower() or "does not exist" in result.error.lower():
                        tool_result_message += "\n<hint>Check if the path is correct, or use list_directory tool to see directory contents.</hint>\n"
                tool_result_message += "</tool_result>\n\nPlease continue based on the tool execution result. Call more tools if needed."
                
                self.session.add_user_message(tool_result_message)
                
            except Exception as e:
                logger.error(f"Tool execution exception: {e}")
                error_msg = (
                    f"<tool_result>\n"
                    f"<tool_name>{tool_name}</tool_name>\n"
                    f"<success>false</success>\n"
                    f"<error>{str(e)}</error>\n"
                    f"</tool_result>\n\n"
                    f"Tool execution failed with exception. Please analyze the error and try a different approach."
                )
                yield f"❌ Tool execution exception: {str(e)}\n\n"
                self.session.add_user_message(error_msg)
        
        # 计算 token 并保存助手消息
        input_tokens = self.model_provider.count_tokens(
            self._get_system_prompt() + user_input
        )
        output_tokens = self.model_provider.count_tokens(total_response)
        
        self.session.add_assistant_message(
            total_response,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        
        # 记录 API 使用统计
        stats_manager.record_api_usage(
            model=self.config.model.model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
    
    async def execute_tool(self, tool_name: str, **kwargs: Any) -> ToolResult:
        """
        执行工具
        
        支持内置工具和 MCP 工具调用
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数
            
        Returns:
            执行结果
        """
        # 首先尝试内置工具
        try:
            tool = registry.get_tool(tool_name)
        except KeyError:
            tool = None
        
        if tool:
            # 检查运行模式
            if self.config.run_mode == RunMode.PLAN:
                # 规划模式下：只读工具正常执行，危险操作返回计划信息
                if tool.dangerous:
                    return ToolResult(
                        success=True,
                        output=f"[Plan Mode] Will execute dangerous operation: {tool_name}, params: {kwargs}\n(This operation was not actually executed)",
                        data={"planned": True, "tool": tool_name, "params": kwargs},
                    )
                # 只读工具在规划模式下正常执行
            
            # 检查危险操作确认
            if tool.dangerous and self.config.run_mode == RunMode.DEFAULT:
                logger.warning(f"Dangerous operation requires confirmation: {tool_name}")
            
            return await registry.execute(tool_name, **kwargs)
        
        # 尝试 MCP 工具
        if self._mcp_initialized and self._mcp_manager:
            mcp_tool = self._mcp_manager.get_tool(tool_name)
            if mcp_tool:
                try:
                    result = await self._mcp_manager.call_tool(tool_name, kwargs)
                    return ToolResult(
                        success=not result.is_error,
                        output=result.get_text_content(),
                        error=result.get_text_content() if result.is_error else None,
                        data={"mcp_tool": True, "server": mcp_tool.server_name},
                    )
                except Exception as e:
                    logger.error(f"MCP tool execution failed: {e}")
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"MCP tool error: {str(e)}",
                    )
        
        return ToolResult(
            success=False,
            output="",
            error=f"Tool not found: {tool_name}",
        )
    
    async def check_context_reset(self) -> bool:
        """
        检查并执行上下文重置
        
        检查当前上下文使用率是否超过配置的阈值，如果超过则执行上下文重置。
        重置操作会保存当前状态到 HandoffArtifact，清空对话历史，并恢复关键上下文。
        
        Returns:
            bool: 是否执行了重置操作
            
        Example:
            >>> if await agent.check_context_reset():
            ...     print("上下文已重置")
        """
        if not self.config.long_running.enable_long_running_mode:
            return False
        
        try:
            manager = self.get_context_reset_manager()
            usage = self.session.get_context_usage()
            
            needs_reset, reason = manager.check_reset_needed(
                usage.used_tokens,
                usage.max_tokens,
            )
            
            if needs_reset:
                logger.warning(f"触发上下文重置: {reason}")
                
                # 执行重置
                result = self.session.reset_context(
                    trigger=ResetTrigger.AUTO_THRESHOLD,
                    context_summary=f"Token 使用: {usage.used_tokens}/{usage.max_tokens}",
                )
                
                return result.success
            
            return False
            
        except Exception as e:
            logger.error(f"检查上下文重置失败: {e}")
            return False
    
    def detect_anxiety_in_output(self, output: str) -> tuple[bool, str]:
        """
        检测输出中的上下文焦虑行为
        
        分析模型输出文本，检测是否存在"上下文焦虑"行为。
        上下文焦虑是指模型因为上下文过长而试图过早结束任务的行为。
        
        Args:
            output: 模型输出文本
            
        Returns:
            tuple[bool, str]: 元组 (是否检测到焦虑, 原因说明)
            
        Example:
            >>> is_anxious, reason = agent.detect_anxiety_in_output("让我总结一下")
            >>> if is_anxious:
            ...     print(f"检测到焦虑: {reason}")
        """
        if not self.config.long_running.enable_long_running_mode:
            return False, ""
        
        try:
            manager = self.get_context_reset_manager()
            
            # 获取待处理任务
            pending_tasks = []
            if self._orchestrator:
                pending_tasks = [t for t in self._orchestrator._tasks if t.status == "pending"]
            
            return manager.detect_anxiety(output, pending_tasks)
            
        except Exception as e:
            logger.error(f"检测上下文焦虑失败: {e}")
            return False, ""
    
    async def _process_skills(self, user_input: str) -> list[tuple[str, "SkillResult"]]:
        """
        处理触发的技能
        
        Args:
            user_input: 用户输入
            
        Returns:
            (技能名称, 执行结果) 列表
        """
        if not self._skill_manager:
            return []
        
        try:
            from foxcode.core.skill import SkillContext
            
            context = SkillContext(
                user_input=user_input,
                conversation_history=[
                    {"role": msg.role.value, "content": msg.content}
                    for msg in self.session.conversation.messages
                ],
                working_dir=self.config.working_dir,
                config=self.config.skills.model_dump(),
            )
            
            return await self._skill_manager.execute_triggered_skills(context)
            
        except Exception as e:
            logger.error(f"Failed to process skills: {e}")
            return []
    
    def get_conversation(self) -> Conversation:
        """获取当前对话"""
        return self.session.conversation
    
    def clear_conversation(self) -> None:
        """清空对话"""
        self.session.clear()
    
    def get_token_usage(self) -> dict[str, int]:
        """获取 token 使用统计"""
        return {
            "input_tokens": self.session.conversation.total_input_tokens,
            "output_tokens": self.session.conversation.total_output_tokens,
            "total_tokens": (
                self.session.conversation.total_input_tokens +
                self.session.conversation.total_output_tokens
            ),
        }
    
    def get_stats(self) -> dict[str, Any]:
        """
        获取会话统计信息
        
        Returns:
            统计信息字典
        """
        return stats_manager.get_session_stats()
    
    def get_stats_report(self) -> str:
        """
        获取统计报告
        
        Returns:
            格式化的统计报告
        """
        return stats_manager.get_full_report()
    
    def reset_stats(self) -> None:
        """重置统计信息"""
        stats_manager.reset()
    
    def save_session(self) -> None:
        """保存会话"""
        self.session.save()
    
    def load_session(self, session_id: str) -> None:
        """
        加载会话
        
        Args:
            session_id: 会话 ID
        """
        self.session = Session.load(self.config, session_id)
    
    def end_session(
        self,
        completed_work: list[str] | None = None,
        incomplete_work: list[str] | None = None,
        issues: list[str] | None = None,
        next_steps: list[str] | None = None,
    ) -> None:
        """
        结束会话并保存摘要
        
        Args:
            completed_work: 完成的工作列表
            incomplete_work: 未完成的工作列表
            issues: 遇到的问题列表
            next_steps: 下一步建议列表
        """
        if not self.config.long_running.enable_long_running_mode:
            return
        
        if not self.config.long_running.auto_generate_summary:
            return
        
        try:
            # 保存会话摘要
            self.session.save_session_summary(
                completed_work=completed_work,
                incomplete_work=incomplete_work,
                issues=issues,
                next_steps=next_steps,
            )
            
            logger.info("Session summary saved")
            
        except Exception as e:
            logger.error(f"Failed to save session summary: {e}")
    
    def get_progress_summary(self) -> str:
        """
        获取进度摘要
        
        Returns:
            进度摘要文本
        """
        if not self.config.long_running.enable_long_running_mode:
            return "Long running mode not enabled"
        
        try:
            return self.session.get_progress_manager().get_summary()
        except Exception as e:
            logger.error(f"Failed to get progress summary: {e}")
            return f"Failed to get progress summary: {e}"
    
    def get_feature_list_summary(self) -> str:
        """
        获取功能列表摘要
        
        Returns:
            功能列表摘要文本
        """
        if not self.config.long_running.enable_long_running_mode:
            return "Long running mode not enabled"
        
        try:
            feature_list = self.session.get_feature_list()
            stats = feature_list.get_statistics()
            
            lines = [
                f"Total features: {stats['total']}",
                f"Pending: {stats['pending']}",
                f"In progress: {stats['in_progress']}",
                f"Completed: {stats['completed']}",
                f"Completion rate: {stats['completion_rate']}%",
            ]
            
            next_feature = feature_list.get_next_feature()
            if next_feature:
                lines.append(f"\nNext suggested feature: {next_feature.id} - {next_feature.title}")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Failed to get feature list summary: {e}")
            return f"Failed to get feature list summary: {e}"
    
    def mark_feature_completed(self, feature_id: str, verification: str = "") -> bool:
        """
        标记功能为已完成
        
        Args:
            feature_id: 功能 ID
            verification: 验证结果
            
        Returns:
            是否成功
        """
        try:
            feature_list = self.session.get_feature_list()
            feature_list.mark_completed(feature_id, verification)
            feature_list.save()
            
            logger.info(f"Feature {feature_id} marked as completed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to mark feature as completed: {e}")
            return False
    
    def add_feature(
        self,
        title: str,
        description: str = "",
        priority: str = "medium",
        category: str = "Core Feature",
    ) -> str | None:
        """
        添加新功能
        
        Args:
            title: 功能标题
            description: 功能描述
            priority: 优先级
            category: 分类
            
        Returns:
            功能 ID，失败返回 None
        """
        try:
            from foxcode.core.feature_list import FeaturePriority
            
            feature_list = self.session.get_feature_list()
            
            # 生成功能 ID
            feature_id = f"FEATURE-{len(feature_list.features) + 1:03d}"
            
            priority_enum = FeaturePriority(priority.lower())
            
            feature_list.add_feature(
                feature_id=feature_id,
                title=title,
                description=description,
                priority=priority_enum,
                category=category,
            )
            feature_list.save()
            
            logger.info(f"Added feature: {feature_id} - {title}")
            return feature_id
            
        except Exception as e:
            logger.error(f"Failed to add feature: {e}")
            return None
