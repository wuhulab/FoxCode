"""
FoxCode 统一 API 客户端接口 - 跨提供商的统一 API 调用

这个文件提供统一的 API 客户端接口:
1. 统一接口：一个客户端支持多个服务提供商
2. 服务注册：动态注册不同提供商的配置
3. 默认提供商：设置和切换默认提供商
4. 请求代理：自动路由到正确的提供商客户端

支持的提供商:
- OpenAI / Anthropic / Bedrock / Vertex / Foundry / Custom

使用方式:
    from foxcode.services.api.unified_client import UnifiedAPIClient

    client = UnifiedAPIClient(default_provider=ServiceProvider.OPENAI)
    client.register_service(config)
    response = await client.chat(messages)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from foxcode.services.api.client import ServiceProvider, ServiceConfig, APIClientManager, api_client_manager

logger = logging.getLogger(__name__)


class UnifiedAPIClient:
    """
    统一 API 客户端
    
    提供统一的接口，支持不同服务提供商
    """

    def __init__(self, default_provider: ServiceProvider = ServiceProvider.OPENAI):
        """
        初始化统一 API 客户端
        
        Args:
            default_provider: 默认服务提供商
        """
        self.default_provider = default_provider
        self.api_manager = api_client_manager
        self._logger = logging.getLogger("foxcode.services.api.unified")

    def register_service(self, config: ServiceConfig) -> None:
        """
        注册服务
        
        Args:
            config: 服务配置
        """
        self.api_manager.register_client(config)

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        provider: Optional[ServiceProvider] = None,
        **kwargs: Any
    ) -> dict[str, Any]:
        """
        聊天完成
        
        Args:
            messages: 消息列表
            provider: 服务提供商，如果为 None 则使用默认提供商
            **kwargs: 额外参数
            
        Returns:
            聊天完成结果
        """
        provider = provider or self.default_provider
        self._logger.info(f"调用聊天完成 API，服务提供商: {provider.value}")
        return await self.api_manager.chat_completion(provider, messages, **kwargs)

    async def text_completion(
        self,
        prompt: str,
        provider: Optional[ServiceProvider] = None,
        **kwargs: Any
    ) -> dict[str, Any]:
        """
        文本完成
        
        Args:
            prompt: 提示文本
            provider: 服务提供商，如果为 None 则使用默认提供商
            **kwargs: 额外参数
            
        Returns:
            文本完成结果
        """
        provider = provider or self.default_provider
        self._logger.info(f"调用文本完成 API，服务提供商: {provider.value}")
        return await self.api_manager.text_completion(provider, prompt, **kwargs)

    async def embedding(
        self,
        text: str,
        provider: Optional[ServiceProvider] = None
    ) -> list[float]:
        """
        生成嵌入向量
        
        Args:
            text: 要嵌入的文本
            provider: 服务提供商，如果为 None 则使用默认提供商
            
        Returns:
            嵌入向量
        """
        provider = provider or self.default_provider
        self._logger.info(f"调用嵌入 API，服务提供商: {provider.value}")
        return await self.api_manager.embedding(provider, text)

    def list_providers(self) -> list[ServiceProvider]:
        """
        列出所有可用的服务提供商
        
        Returns:
            服务提供商列表
        """
        return self.api_manager.list_clients()

    def set_default_provider(self, provider: ServiceProvider) -> None:
        """
        设置默认服务提供商
        
        Args:
            provider: 服务提供商
        """
        self.default_provider = provider
        self._logger.info(f"设置默认服务提供商: {provider.value}")


# 全局统一 API 客户端实例
unified_api_client = UnifiedAPIClient()