"""
FoxCode 核心模块 - 导出所有核心组件

这个文件统一导出 FoxCode 的核心组件，方便外部模块导入使用。

核心组件分类:
1. Agent（代理）:
   - FoxCodeAgent: AI 代理核心类

2. Config（配置）:
   - Config: 主配置类
   - ModelConfig: 模型配置
   - RunMode: 运行模式枚举
   - ToolConfig / UIConfig / MCPConfig: 工具/UI/MCP 配置

3. Message（消息）:
   - Message / Conversation: 消息和对话
   - TextContent / ImageContent / CodeContent: 内容类型
   - ToolUseContent / ToolResultContent: 工具调用和结果

4. Providers（模型提供者）:
   - BaseModelProvider: 模型提供者基类
   - OpenAIProvider / AnthropicProvider / DeepSeekProvider: 具体实现
   - create_model_provider: 工厂函数

5. Session（会话）:
   - Session: 会话管理类

使用方式:
    from foxcode.core import FoxCodeAgent, Config, Session
"""

from foxcode.core.agent import FoxCodeAgent
from foxcode.core.config import (
    Config,
    MCPConfig,
    MCPServerConfigModel,
    ModelConfig,
    ModelProvider,
    RunMode,
    SkillConfigModel,
    SkillsConfig,
    ToolConfig,
    UIConfig,
)
from foxcode.types.message import (
    CodeContent,
    ContentBlock,
    Conversation,
    ImageContent,
    Message,
    MessageRole,
    TextContent,
    ToolResultContent,
    ToolUseContent,
)
from foxcode.core.providers import (
    AnthropicProvider,
    BaseModelProvider,
    DeepSeekProvider,
    LocalModelProvider,
    ModelResponse,
    OpenAIProvider,
    create_model_provider,
)
from foxcode.core.session import Session

__all__ = [
    # Agent
    "FoxCodeAgent",
    # Config
    "Config",
    "ModelConfig",
    "ModelProvider",
    "RunMode",
    "ToolConfig",
    "UIConfig",
    "MCPConfig",
    "MCPServerConfigModel",
    "SkillsConfig",
    "SkillConfigModel",
    # Message
    "Message",
    "MessageRole",
    "Conversation",
    "TextContent",
    "ImageContent",
    "CodeContent",
    "ToolUseContent",
    "ToolResultContent",
    "ContentBlock",
    # Providers
    "BaseModelProvider",
    "ModelResponse",
    "OpenAIProvider",
    "AnthropicProvider",
    "DeepSeekProvider",
    "LocalModelProvider",
    "create_model_provider",
    # Session
    "Session",
]
