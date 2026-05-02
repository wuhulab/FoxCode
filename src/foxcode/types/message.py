"""
FoxCode 消息模块 - 定义消息类型和对话历史管理

这个文件定义了 FoxCode 的消息系统:
1. MessageRole: 消息角色枚举（system/user/assistant/tool）
2. ContentType: 内容类型枚举（text/image/code/tool_use/tool_result）
3. TextContent / ImageContent / CodeContent: 各种内容类型
4. ToolUseContent / ToolResultContent: 工具调用和结果
5. Message: 单条消息
6. Conversation: 对话历史管理

消息角色:
- SYSTEM: 系统提示词
- USER: 用户输入
- ASSISTANT: AI 回复
- TOOL: 工具执行结果

使用方式:
    from foxcode.types.message import Message, Conversation, MessageRole

    conversation = Conversation()
    conversation.add_message(MessageRole.USER, "你好")
    conversation.add_message(MessageRole.ASSISTANT, "你好！")
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """消息角色"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ContentType(str, Enum):
    """内容类型"""
    TEXT = "text"
    IMAGE = "image"
    CODE = "code"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"


class TextContent(BaseModel):
    """文本内容"""
    type: ContentType = ContentType.TEXT
    text: str


class ImageContent(BaseModel):
    """图片内容"""
    type: ContentType = ContentType.IMAGE
    url: str | None = None
    base64_data: str | None = None
    media_type: str = "image/png"


class CodeContent(BaseModel):
    """代码内容"""
    type: ContentType = ContentType.CODE
    code: str
    language: str = "python"


class ToolUseContent(BaseModel):
    """工具调用内容"""
    type: ContentType = ContentType.TOOL_USE
    tool_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool_name: str
    tool_input: dict[str, Any] = Field(default_factory=dict)


class ToolResultContent(BaseModel):
    """工具结果内容"""
    type: ContentType = ContentType.TOOL_RESULT
    tool_id: str
    tool_name: str
    result: str
    is_error: bool = False


ContentBlock = TextContent | ImageContent | CodeContent | ToolUseContent | ToolResultContent


class Message(BaseModel):
    """
    消息类
    
    表示对话中的一条消息，支持多种内容类型
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: MessageRole
    content: str | list[ContentBlock]
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Token 统计
    input_tokens: int = 0
    output_tokens: int = 0

    def get_text_content(self) -> str:
        """获取文本内容"""
        if isinstance(self.content, str):
            return self.content

        texts = []
        for block in self.content:
            if isinstance(block, TextContent):
                texts.append(block.text)
            elif isinstance(block, CodeContent):
                texts.append(f"```{block.language}\n{block.code}\n```")

        return "\n".join(texts)

    def to_api_format(self) -> dict[str, Any]:
        """
        转换为 API 调用格式
        
        Returns:
            API 格式的消息字典
        """
        if isinstance(self.content, str):
            return {
                "role": self.role.value,
                "content": self.content,
            }

        # 处理多内容块
        content_parts = []
        for block in self.content:
            if isinstance(block, TextContent):
                content_parts.append({"type": "text", "text": block.text})
            elif isinstance(block, ImageContent):
                if block.base64_data:
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{block.media_type};base64,{block.base64_data}"
                        }
                    })
                elif block.url:
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": block.url}
                    })
            elif isinstance(block, ToolUseContent):
                content_parts.append({
                    "type": "tool_use",
                    "id": block.tool_id,
                    "name": block.tool_name,
                    "input": block.tool_input,
                })
            elif isinstance(block, ToolResultContent):
                content_parts.append({
                    "type": "tool_result",
                    "tool_use_id": block.tool_id,
                    "content": block.result,
                    "is_error": block.is_error,
                })

        return {
            "role": self.role.value,
            "content": content_parts,
        }

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "role": self.role.value,
            "content": self.content if isinstance(self.content, str)
                      else [block.model_dump() for block in self.content],
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Message:
        """从字典创建消息"""
        content = data["content"]
        if isinstance(content, list):
            parsed_content = []
            for block in content:
                block_type = ContentType(block.get("type", "text"))
                if block_type == ContentType.TEXT:
                    parsed_content.append(TextContent(**block))
                elif block_type == ContentType.IMAGE:
                    parsed_content.append(ImageContent(**block))
                elif block_type == ContentType.CODE:
                    parsed_content.append(CodeContent(**block))
                elif block_type == ContentType.TOOL_USE:
                    parsed_content.append(ToolUseContent(**block))
                elif block_type == ContentType.TOOL_RESULT:
                    parsed_content.append(ToolResultContent(**block))
            content = parsed_content

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            role=MessageRole(data["role"]),
            content=content,
            created_at=datetime.fromisoformat(data["created_at"]),
            metadata=data.get("metadata", {}),
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
        )


class Conversation(BaseModel):
    """
    对话类
    
    管理完整的对话历史
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    messages: list[Message] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Token 统计
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    def add_message(self, message: Message) -> None:
        """添加消息"""
        self.messages.append(message)
        self.total_input_tokens += message.input_tokens
        self.total_output_tokens += message.output_tokens
        self.updated_at = datetime.now()

    def get_last_message(self) -> Message | None:
        """获取最后一条消息"""
        return self.messages[-1] if self.messages else None

    def get_messages_for_api(self, include_system: bool = True) -> list[dict[str, Any]]:
        """
        获取用于 API 调用的消息列表
        
        Args:
            include_system: 是否包含系统消息
            
        Returns:
            API 格式的消息列表
        """
        messages = []
        for msg in self.messages:
            if not include_system and msg.role == MessageRole.SYSTEM:
                continue
            messages.append(msg.to_api_format())
        return messages

    def clear(self) -> None:
        """清空对话"""
        self.messages.clear()
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.updated_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "messages": [msg.to_dict() for msg in self.messages],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Conversation:
        """从字典创建对话"""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            messages=[Message.from_dict(msg) for msg in data.get("messages", [])],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            metadata=data.get("metadata", {}),
            total_input_tokens=data.get("total_input_tokens", 0),
            total_output_tokens=data.get("total_output_tokens", 0),
        )

    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> Conversation:
        """从 JSON 字符串创建对话"""
        return cls.from_dict(json.loads(json_str))
