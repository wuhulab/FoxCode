"""
FoxCode AI模型提供者模块 - 统一的AI模型接口

这个文件是FoxCode与各种AI模型通信的桥梁，负责：
1. 统一接口：为不同AI模型提供统一的调用方式
2. 模型适配：适配OpenAI、Anthropic、DeepSeek等不同API
3. 流式输出：支持实时流式响应
4. Token计算：计算token消耗用于统计成本

支持的模型提供者：
- OpenAI: GPT-4、GPT-4o、GPT-3.5等
- Anthropic: Claude系列
- DeepSeek: DeepSeek Chat、DeepSeek Coder
- StepFun: Step系列

使用方式：
    from foxcode.core.providers import create_model_provider
    from foxcode.core.config import ModelConfig
    
    # 创建模型提供者
    config = ModelConfig(model_name="gpt-4o")
    provider = create_model_provider(config)
    await provider.initialize()
    
    # 同步调用
    response = await provider.chat(conversation, system_prompt="...")
    
    # 流式调用
    async for chunk in provider.stream_chat(conversation):
        print(chunk, end="")

关键特性：
- 统一的API接口，无需关心底层差异
- 自动重试和错误处理
- 支持流式输出，实时响应
- 自动计算token消耗
"""

from __future__ import annotations

import abc
import asyncio
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from foxcode.core.config import ModelConfig, ModelProvider
from foxcode.types.message import Conversation

logger = logging.getLogger(__name__)


class ModelResponse:
    """
    模型响应封装 - 统一的响应格式
    
    封装AI模型的响应数据，包括：
    - content: 生成的文本内容
    - input_tokens: 输入token数
    - output_tokens: 输出token数
    - finish_reason: 结束原因（stop、length等）
    - tool_calls: 工具调用列表
    
    使用示例：
        response = await provider.chat(conversation)
        print(f"生成内容: {response.content}")
        print(f"消耗token: {response.total_tokens}")
    """

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
        """总token数 = 输入 + 输出"""
        return self.input_tokens + self.output_tokens


class BaseModelProvider(abc.ABC):
    """
    模型提供者基类 - 所有AI模型接口的父类
    
    这是模型提供者的抽象基类，定义了统一的接口：
    - initialize(): 初始化客户端
    - chat(): 同步对话
    - stream_chat(): 流式对话
    - count_tokens(): 计算token数
    
    为什么需要统一接口？
    1. 不同AI公司的API差异很大
    2. 统一接口让上层代码不用关心底层差异
    3. 方便添加新的模型提供者
    
    开发新的模型提供者：
    1. 继承BaseModelProvider
    2. 实现所有抽象方法
    3. 在create_model_provider中注册
    
    使用示例：
        class MyProvider(BaseModelProvider):
            async def initialize(self):
                self._client = MyClient(self.config.api_key)
            
            async def chat(self, conversation, system_prompt=None):
                # 调用API
                response = await self._client.chat(...)
                return ModelResponse(content=response.text)
    """

    def __init__(self, config: ModelConfig):
        """
        初始化模型提供者
        
        Args:
            config: 模型配置，包含API密钥、模型名称等
        """
        self.config = config
        self._client: Any = None  # 具体的API客户端

    @abc.abstractmethod
    async def initialize(self) -> None:
        """
        初始化模型客户端 - 子类必须实现
        
        初始化流程：
        1. 获取API密钥
        2. 创建API客户端
        3. 验证连接
        
        异常：
        - ImportError: 未安装对应的SDK
        - AuthenticationError: API密钥无效
        """
        pass

    @abc.abstractmethod
    async def chat(
        self,
        conversation: Conversation,
        system_prompt: str | None = None,
    ) -> ModelResponse:
        """
        发送聊天请求（同步模式） - 子类必须实现
        
        同步模式：等待AI完全生成响应后返回
        适用场景：需要完整响应的场景
        
        Args:
            conversation: 对话历史，包含所有消息
            system_prompt: 系统提示词，定义AI的角色和行为
            
        Returns:
            ModelResponse: 包含生成内容和token统计
        """
        pass

    @abc.abstractmethod
    async def stream_chat(
        self,
        conversation: Conversation,
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        """
        流式聊天请求 - 子类必须实现
        
        流式模式：实时返回生成的内容片段
        适用场景：需要实时反馈的场景（推荐）
        
        为什么推荐流式？
        1. 用户体验好，不用等待
        2. 可以提前显示内容
        3. 减少超时风险
        
        Args:
            conversation: 对话历史
            system_prompt: 系统提示词
            
        Yields:
            响应文本片段（逐字返回）
        """
        pass

    @abc.abstractmethod
    def count_tokens(self, text: str) -> int:
        """
        计算token数量 - 子类必须实现
        
        不同模型的token计算方式不同：
        - OpenAI: 使用tiktoken库
        - Anthropic: 使用官方tokenizer
        - 其他: 使用近似估算
        
        Args:
            text: 要计算的文本
            
        Returns:
            token数量
        """
        pass


class OpenAIProvider(BaseModelProvider):
    """
    OpenAI模型提供者 - 支持GPT系列模型
    
    支持的模型：
    - GPT-4o: 最新旗舰模型，性价比高
    - GPT-4 Turbo: 性能强劲
    - GPT-3.5 Turbo: 快速且便宜
    
    特性：
    - 支持流式输出
    - 支持自定义base_url（兼容第三方API）
    - 自动token计算（使用tiktoken）
    
    使用示例：
        config = ModelConfig(model_name="gpt-4o", api_key="sk-...")
        provider = OpenAIProvider(config)
        await provider.initialize()
        
        async for chunk in provider.stream_chat(conversation):
            print(chunk, end="")
    """

    async def initialize(self) -> None:
        """
        初始化OpenAI客户端
        
        初始化流程：
        1. 检查openai库是否安装
        2. 获取API密钥
        3. 创建AsyncOpenAI客户端
        
        异常：
        - ImportError: 未安装openai库
        """
        try:
            from openai import AsyncOpenAI

            # 获取有效的API密钥
            api_key = self.config.get_effective_api_key()
            
            # 创建异步客户端
            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=self.config.base_url,  # 支持自定义API地址
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
