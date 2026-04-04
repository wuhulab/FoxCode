"""
FoxCode AI 模型提供者模块

支持多种 AI 模型提供者的统一接口
"""

from __future__ import annotations

import abc
import asyncio
import logging
import time
from typing import Any, AsyncIterator

from foxcode.core.config import ModelConfig, ModelProvider
from foxcode.core.message import Conversation, Message

logger = logging.getLogger(__name__)


class ModelResponse:
    """模型响应封装"""
    
    def __init__(
        self,
        content: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        finish_reason: str = "stop",
        tool_calls: list[dict[str, Any]] | None = None,
    ):
        self.content = content
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.finish_reason = finish_reason
        self.tool_calls = tool_calls or []
    
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class BaseModelProvider(abc.ABC):
    """
    模型提供者基类
    
    定义所有模型提供者必须实现的接口
    """
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self._client: Any = None
    
    @abc.abstractmethod
    async def initialize(self) -> None:
        """初始化模型客户端"""
        pass
    
    @abc.abstractmethod
    async def chat(
        self,
        conversation: Conversation,
        system_prompt: str | None = None,
    ) -> ModelResponse:
        """
        发送聊天请求
        
        Args:
            conversation: 对话历史
            system_prompt: 系统提示词
            
        Returns:
            模型响应
        """
        pass
    
    @abc.abstractmethod
    async def stream_chat(
        self,
        conversation: Conversation,
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        """
        流式聊天请求
        
        Args:
            conversation: 对话历史
            system_prompt: 系统提示词
            
        Yields:
            响应文本片段
        """
        pass
    
    @abc.abstractmethod
    def count_tokens(self, text: str) -> int:
        """
        计算 token 数量
        
        Args:
            text: 要计算的文本
            
        Returns:
            token 数量
        """
        pass


class OpenAIProvider(BaseModelProvider):
    """OpenAI 模型提供者"""
    
    async def initialize(self) -> None:
        """初始化 OpenAI 客户端"""
        try:
            from openai import AsyncOpenAI
            
            api_key = self.config.get_effective_api_key()
            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
            )
            logger.info("OpenAI 客户端初始化成功")
        except ImportError:
            raise ImportError("请安装 openai: pip install openai")
    
    async def chat(
        self,
        conversation: Conversation,
        system_prompt: str | None = None,
    ) -> ModelResponse:
        """发送聊天请求"""
        if not self._client:
            await self.initialize()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(conversation.get_messages_for_api(include_system=False))
        
        start_time = time.time()
        logger.debug(f"发送请求到 OpenAI: {self.config.model_name}")
        
        response = await self._client.chat.completions.create(
            model=self.config.model_name,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        
        elapsed = time.time() - start_time
        logger.debug(f"OpenAI 响应时间: {elapsed:.2f}s")
        
        choice = response.choices[0]
        return ModelResponse(
            content=choice.message.content or "",
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
            finish_reason=choice.finish_reason or "stop",
        )
    
    async def stream_chat(
        self,
        conversation: Conversation,
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        """流式聊天请求"""
        if not self._client:
            await self.initialize()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(conversation.get_messages_for_api(include_system=False))
        
        stream = await self._client.chat.completions.create(
            model=self.config.model_name,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            stream=True,
        )
        
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    def count_tokens(self, text: str) -> int:
        """计算 token 数量"""
        try:
            import tiktoken
            
            encoding = tiktoken.encoding_for_model(self.config.model_name)
            return len(encoding.encode(text))
        except Exception:
            # 简单估算：平均每 4 个字符约 1 个 token
            return len(text) // 4


class AnthropicProvider(BaseModelProvider):
    """Anthropic 模型提供者"""
    
    async def initialize(self) -> None:
        """初始化 Anthropic 客户端"""
        try:
            from anthropic import AsyncAnthropic
            
            api_key = self.config.get_effective_api_key()
            self._client = AsyncAnthropic(
                api_key=api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
            )
            logger.info("Anthropic 客户端初始化成功")
        except ImportError:
            raise ImportError("请安装 anthropic: pip install anthropic")
    
    async def chat(
        self,
        conversation: Conversation,
        system_prompt: str | None = None,
    ) -> ModelResponse:
        """发送聊天请求"""
        if not self._client:
            await self.initialize()
        
        messages = conversation.get_messages_for_api(include_system=False)
        
        start_time = time.time()
        logger.debug(f"发送请求到 Anthropic: {self.config.model_name}")
        
        response = await self._client.messages.create(
            model=self.config.model_name,
            max_tokens=self.config.max_tokens,
            system=system_prompt or "",
            messages=messages,
        )
        
        elapsed = time.time() - start_time
        logger.debug(f"Anthropic 响应时间: {elapsed:.2f}s")
        
        # 提取文本内容
        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text
        
        return ModelResponse(
            content=content,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            finish_reason=response.stop_reason or "stop",
        )
    
    async def stream_chat(
        self,
        conversation: Conversation,
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        """流式聊天请求"""
        if not self._client:
            await self.initialize()
        
        messages = conversation.get_messages_for_api(include_system=False)
        
        async with self._client.messages.stream(
            model=self.config.model_name,
            max_tokens=self.config.max_tokens,
            system=system_prompt or "",
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text
    
    def count_tokens(self, text: str) -> int:
        """计算 token 数量"""
        try:
            import tiktoken
            
            # Claude 使用类似的 token 计算
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception:
            return len(text) // 4


class DeepSeekProvider(BaseModelProvider):
    """DeepSeek 模型提供者 (OpenAI 兼容)"""
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        # DeepSeek 使用 OpenAI 兼容接口
        if not config.base_url:
            config.base_url = "https://api.deepseek.com/v1"
    
    async def initialize(self) -> None:
        """初始化 DeepSeek 客户端"""
        try:
            from openai import AsyncOpenAI
            
            api_key = self.config.get_effective_api_key()
            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
            )
            logger.info("DeepSeek 客户端初始化成功")
        except ImportError:
            raise ImportError("请安装 openai: pip install openai")
    
    async def chat(
        self,
        conversation: Conversation,
        system_prompt: str | None = None,
    ) -> ModelResponse:
        """发送聊天请求"""
        if not self._client:
            await self.initialize()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(conversation.get_messages_for_api(include_system=False))
        
        start_time = time.time()
        
        response = await self._client.chat.completions.create(
            model=self.config.model_name,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        
        elapsed = time.time() - start_time
        logger.debug(f"DeepSeek 响应时间: {elapsed:.2f}s")
        
        choice = response.choices[0]
        return ModelResponse(
            content=choice.message.content or "",
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
            finish_reason=choice.finish_reason or "stop",
        )
    
    async def stream_chat(
        self,
        conversation: Conversation,
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        """流式聊天请求"""
        if not self._client:
            await self.initialize()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(conversation.get_messages_for_api(include_system=False))
        
        stream = await self._client.chat.completions.create(
            model=self.config.model_name,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            stream=True,
        )
        
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    def count_tokens(self, text: str) -> int:
        """计算 token 数量"""
        return len(text) // 4


class StepProvider(BaseModelProvider):
    """StepFun (阶跃星辰) 模型提供者 (OpenAI 兼容)"""
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        # StepFun 使用 OpenAI 兼容接口
        if not config.base_url:
            config.base_url = "https://api.stepfun.com/v1"
    
    async def initialize(self) -> None:
        """初始化 StepFun 客户端"""
        try:
            from openai import AsyncOpenAI
            
            api_key = self.config.get_effective_api_key()
            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
            )
            logger.info("StepFun 客户端初始化成功")
        except ImportError:
            raise ImportError("请安装 openai: pip install openai")
    
    async def chat(
        self,
        conversation: Conversation,
        system_prompt: str | None = None,
    ) -> ModelResponse:
        """发送聊天请求"""
        if not self._client:
            await self.initialize()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(conversation.get_messages_for_api(include_system=False))
        
        start_time = time.time()
        
        response = await self._client.chat.completions.create(
            model=self.config.model_name,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        
        elapsed = time.time() - start_time
        logger.debug(f"StepFun 响应时间: {elapsed:.2f}s")
        
        choice = response.choices[0]
        return ModelResponse(
            content=choice.message.content or "",
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
            finish_reason=choice.finish_reason or "stop",
        )
    
    async def stream_chat(
        self,
        conversation: Conversation,
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        """流式聊天请求"""
        if not self._client:
            await self.initialize()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(conversation.get_messages_for_api(include_system=False))
        
        stream = await self._client.chat.completions.create(
            model=self.config.model_name,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            stream=True,
        )
        
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    def count_tokens(self, text: str) -> int:
        """计算 token 数量"""
        return len(text) // 4


class LocalModelProvider(BaseModelProvider):
    """本地模型提供者"""
    
    async def initialize(self) -> None:
        """初始化本地模型"""
        try:
            # 尝试加载 llama-cpp-python
            import llama_cpp
            
            model_path = self.config.base_url or "model.gguf"
            self._client = llama_cpp.Llama(
                model_path=model_path,
                n_ctx=4096,
                verbose=False,
            )
            logger.info(f"本地模型加载成功: {model_path}")
        except ImportError:
            raise ImportError("请安装 llama-cpp-python: pip install llama-cpp-python")
    
    async def chat(
        self,
        conversation: Conversation,
        system_prompt: str | None = None,
    ) -> ModelResponse:
        """发送聊天请求"""
        if not self._client:
            await self.initialize()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(conversation.get_messages_for_api(include_system=False))
        
        # 在线程池中运行同步调用
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.create_chat_completion(
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )
        )
        
        choice = response["choices"][0]
        return ModelResponse(
            content=choice["message"]["content"],
            input_tokens=response["usage"]["prompt_tokens"],
            output_tokens=response["usage"]["completion_tokens"],
            finish_reason=choice.get("finish_reason", "stop"),
        )
    
    async def stream_chat(
        self,
        conversation: Conversation,
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        """流式聊天请求"""
        if not self._client:
            await self.initialize()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(conversation.get_messages_for_api(include_system=False))
        
        for chunk in self._client.create_chat_completion(
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            stream=True,
        ):
            if "content" in chunk["choices"][0]["delta"]:
                yield chunk["choices"][0]["delta"]["content"]
    
    def count_tokens(self, text: str) -> int:
        """计算 token 数量"""
        return len(text) // 4


def create_model_provider(config: ModelConfig) -> BaseModelProvider:
    """
    创建模型提供者
    
    Args:
        config: 模型配置
        
    Returns:
        模型提供者实例
    """
    providers = {
        ModelProvider.OPENAI: OpenAIProvider,
        ModelProvider.ANTHROPIC: AnthropicProvider,
        ModelProvider.DEEPSEEK: DeepSeekProvider,
        ModelProvider.STEP: StepProvider,
        ModelProvider.LOCAL: LocalModelProvider,
    }
    
    provider_class = providers.get(config.provider)
    if not provider_class:
        raise ValueError(f"不支持的模型提供者: {config.provider}")
    
    return provider_class(config)
