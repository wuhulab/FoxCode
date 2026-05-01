"""
FoxCode API客户端模块 - 统一的API服务接口

这个文件管理不同服务提供商的API客户端：
1. 客户端管理：创建和管理不同提供商的客户端
2. 统一接口：为不同API提供统一的调用接口
3. 配置管理：管理API密钥、端点等配置
4. 错误处理：统一的错误处理和重试机制

支持的服务提供商：
- OpenAI: GPT系列模型
- Anthropic: Claude系列模型
- Bedrock: AWS Bedrock
- Vertex: Google Vertex AI
- Foundry: 自定义服务
- Custom: 自定义API

为什么需要统一的API客户端？
不同提供商的API差异很大：
- 不同的认证方式
- 不同的请求格式
- 不同的响应格式
- 不同的错误处理

统一接口的好处：
- 一套代码支持多个提供商
- 轻松切换提供商
- 统一的错误处理
- 简化上层代码

使用方式：
    from foxcode.services.api.client import OpenAIClient, ServiceConfig
    
    config = ServiceConfig(
        provider=ServiceProvider.OPENAI,
        api_key="sk-...",
        model="gpt-4o"
    )
    
    client = OpenAIClient(config)
    response = await client.chat_completion(messages)

关键特性：
- 支持多种服务提供商
- 统一的调用接口
- 自动错误处理
- 支持流式响应
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ServiceProvider(str, Enum):
    """服务提供商"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    BEDROCK = "bedrock"
    VERTEX = "vertex"
    FOUNDRY = "foundry"
    CUSTOM = "custom"


class ServiceConfig(BaseModel):
    """服务配置"""
    provider: ServiceProvider = Field(description="服务提供商")
    api_key: Optional[str] = Field(None, description="API 密钥")
    base_url: Optional[str] = Field(None, description="API 基础 URL")
    model: str = Field(description="模型名称")
    temperature: float = Field(0.7, description="生成温度")
    max_tokens: int = Field(1000, description="最大令牌数")
    timeout: int = Field(30, description="超时时间（秒）")
    enabled: bool = Field(True, description="是否启用")


class BaseAPIClient(ABC):
    """API 客户端基类"""

    def __init__(self, config: ServiceConfig):
        self.config = config
        self._logger = logging.getLogger(f"foxcode.services.api.{config.provider.value}")

    @property
    def provider(self) -> ServiceProvider:
        """获取服务提供商"""
        return self.config.provider

    @abstractmethod
    async def chat_completion(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        """聊天完成"""
        pass

    @abstractmethod
    async def text_completion(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        """文本完成"""
        pass

    @abstractmethod
    async def embedding(self, text: str) -> list[float]:
        """生成嵌入向量"""
        pass


class OpenAIClient(BaseAPIClient):
    """OpenAI API 客户端"""

    async def chat_completion(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        """聊天完成"""
        try:
            # 这里只是一个示例，实际实现需要调用 OpenAI API
            self._logger.info(f"调用 OpenAI 聊天完成 API，模型: {self.config.model}")
            return {
                "id": "chatcmpl-123",
                "object": "chat.completion",
                "created": 1677858242,
                "model": self.config.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "你好！我是 OpenAI 助手。",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 15,
                    "total_tokens": 25,
                },
            }
        except Exception as e:
            self._logger.error(f"OpenAI 聊天完成 API 调用失败: {e}")
            raise

    async def text_completion(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        """文本完成"""
        try:
            # 这里只是一个示例，实际实现需要调用 OpenAI API
            self._logger.info(f"调用 OpenAI 文本完成 API，模型: {self.config.model}")
            return {
                "id": "cmpl-123",
                "object": "text_completion",
                "created": 1677858242,
                "model": self.config.model,
                "choices": [
                    {
                        "text": "你好！这是文本完成的结果。",
                        "index": 0,
                        "logprobs": None,
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 15,
                    "total_tokens": 25,
                },
            }
        except Exception as e:
            self._logger.error(f"OpenAI 文本完成 API 调用失败: {e}")
            raise

    async def embedding(self, text: str) -> list[float]:
        """生成嵌入向量"""
        try:
            # 这里只是一个示例，实际实现需要调用 OpenAI API
            self._logger.info(f"调用 OpenAI 嵌入 API，模型: {self.config.model}")
            # 返回一个示例嵌入向量
            return [0.1] * 1536
        except Exception as e:
            self._logger.error(f"OpenAI 嵌入 API 调用失败: {e}")
            raise


class AnthropicClient(BaseAPIClient):
    """Anthropic API 客户端"""

    async def chat_completion(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        """聊天完成"""
        try:
            # 这里只是一个示例，实际实现需要调用 Anthropic API
            self._logger.info(f"调用 Anthropic 聊天完成 API，模型: {self.config.model}")
            return {
                "id": "chat-123",
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": "你好！我是 Anthropic 助手。",
                    }
                ],
                "model": self.config.model,
                "stop_reason": "end_turn",
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 15,
                },
            }
        except Exception as e:
            self._logger.error(f"Anthropic 聊天完成 API 调用失败: {e}")
            raise

    async def text_completion(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        """文本完成"""
        try:
            # 这里只是一个示例，实际实现需要调用 Anthropic API
            self._logger.info(f"调用 Anthropic 文本完成 API，模型: {self.config.model}")
            return {
                "id": "completion-123",
                "type": "completion",
                "completion": "你好！这是文本完成的结果。",
                "model": self.config.model,
                "stop_reason": "end_turn",
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 15,
                },
            }
        except Exception as e:
            self._logger.error(f"Anthropic 文本完成 API 调用失败: {e}")
            raise

    async def embedding(self, text: str) -> list[float]:
        """生成嵌入向量"""
        try:
            # 这里只是一个示例，实际实现需要调用 Anthropic API
            self._logger.info(f"调用 Anthropic 嵌入 API，模型: {self.config.model}")
            # 返回一个示例嵌入向量
            return [0.1] * 1536
        except Exception as e:
            self._logger.error(f"Anthropic 嵌入 API 调用失败: {e}")
            raise


class APIClientManager:
    """API 客户端管理器"""

    def __init__(self):
        self._clients: dict[ServiceProvider, BaseAPIClient] = {}
        self._logger = logging.getLogger("foxcode.services.api.manager")

    def register_client(self, config: ServiceConfig) -> Optional[BaseAPIClient]:
        """
        注册 API 客户端
        
        Args:
            config: 服务配置
            
        Returns:
            API 客户端实例，如果服务被禁用则返回 None
        """
        if not config.enabled:
            self._logger.warning(f"服务提供商 {config.provider.value} 已禁用")
            return None

        client: BaseAPIClient
        if config.provider == ServiceProvider.OPENAI:
            client = OpenAIClient(config)
        elif config.provider == ServiceProvider.ANTHROPIC:
            client = AnthropicClient(config)
        else:
            # 为其他服务提供商创建默认客户端
            client = BaseAPIClient(config)

        self._clients[config.provider] = client
        self._logger.info(f"注册 API 客户端: {config.provider.value}")
        return client

    def get_client(self, provider: ServiceProvider) -> Optional[BaseAPIClient]:
        """
        获取 API 客户端
        
        Args:
            provider: 服务提供商
            
        Returns:
            API 客户端实例，如果不存在则返回 None
        """
        return self._clients.get(provider)

    def list_clients(self) -> list[ServiceProvider]:
        """
        列出所有注册的客户端
        
        Returns:
            服务提供商列表
        """
        return list(self._clients.keys())

    def remove_client(self, provider: ServiceProvider) -> bool:
        """
        移除 API 客户端
        
        Args:
            provider: 服务提供商
            
        Returns:
            是否成功移除
        """
        if provider in self._clients:
            del self._clients[provider]
            self._logger.info(f"移除 API 客户端: {provider.value}")
            return True
        return False

    async def chat_completion(self, provider: ServiceProvider, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        """
        聊天完成
        
        Args:
            provider: 服务提供商
            messages: 消息列表
            **kwargs: 额外参数
            
        Returns:
            聊天完成结果
        """
        client = self.get_client(provider)
        if not client:
            raise ValueError(f"未找到服务提供商 {provider.value} 的客户端")
        return await client.chat_completion(messages, **kwargs)

    async def text_completion(self, provider: ServiceProvider, prompt: str, **kwargs: Any) -> dict[str, Any]:
        """
        文本完成
        
        Args:
            provider: 服务提供商
            prompt: 提示文本
            **kwargs: 额外参数
            
        Returns:
            文本完成结果
        """
        client = self.get_client(provider)
        if not client:
            raise ValueError(f"未找到服务提供商 {provider.value} 的客户端")
        return await client.text_completion(prompt, **kwargs)

    async def embedding(self, provider: ServiceProvider, text: str) -> list[float]:
        """
        生成嵌入向量
        
        Args:
            provider: 服务提供商
            text: 要嵌入的文本
            
        Returns:
            嵌入向量
        """
        client = self.get_client(provider)
        if not client:
            raise ValueError(f"未找到服务提供商 {provider.value} 的客户端")
        return await client.embedding(text)


# 全局 API 客户端管理器实例
api_client_manager = APIClientManager()