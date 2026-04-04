"""
FoxCode QQbot 服务模块

集成官方 QQbot API，提供：
- WebSocket 连接管理
- 消息收发处理
- 事件处理
- API 调用封装
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

import aiohttp

from foxcode.core.company_mode_config import QQbotConfig

logger = logging.getLogger(__name__)


class QQbotStatus(str, Enum):
    """QQbot 状态枚举"""
    DISCONNECTED = "disconnected"   # 已断开
    CONNECTING = "connecting"       # 连接中
    CONNECTED = "connected"         # 已连接
    AUTHENTICATING = "authenticating"  # 认证中
    READY = "ready"                 # 就绪
    ERROR = "error"                 # 错误
    RECONNECTING = "reconnecting"   # 重连中


class MessageType(str, Enum):
    """消息类型枚举"""
    TEXT = 0            # 文本消息
    IMAGE = 1           # 图片消息
    AUDIO = 2           # 语音消息
    VIDEO = 3           # 视频消息
    EMBED = 4           # 嵌入消息
    ARK = 4             # Ark 消息
    MARKDOWN = 9        # Markdown 消息


@dataclass
class QQbotMessage:
    """QQbot 消息"""
    id: str                             # 消息 ID
    channel_id: str                     # 频道 ID
    guild_id: str                       # 子频道 ID
    author_id: str                      # 作者 ID
    content: str                        # 消息内容
    message_type: MessageType = MessageType.TEXT
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    mentions: list[str] = field(default_factory=list)  # @用户列表
    attachments: list[dict[str, Any]] = field(default_factory=list)  # 附件列表
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "channel_id": self.channel_id,
            "guild_id": self.guild_id,
            "author_id": self.author_id,
            "content": self.content,
            "message_type": self.message_type.value,
            "timestamp": self.timestamp,
            "mentions": self.mentions,
            "attachments": self.attachments,
            "metadata": self.metadata,
        }


@dataclass
class QQbotEvent:
    """QQbot 事件"""
    event_type: str                     # 事件类型
    data: dict[str, Any]                # 事件数据
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # 常见事件类型
    EVENT_READY = "READY"
    EVENT_MESSAGE_CREATE = "MESSAGE_CREATE"
    EVENT_MESSAGE_UPDATE = "MESSAGE_UPDATE"
    EVENT_MESSAGE_DELETE = "MESSAGE_DELETE"
    EVENT_CHANNEL_CREATE = "CHANNEL_CREATE"
    EVENT_CHANNEL_UPDATE = "CHANNEL_UPDATE"
    EVENT_CHANNEL_DELETE = "CHANNEL_DELETE"
    EVENT_GUILD_CREATE = "GUILD_CREATE"
    EVENT_GUILD_UPDATE = "GUILD_UPDATE"
    EVENT_GUILD_DELETE = "GUILD_DELETE"
    EVENT_GUILD_MEMBER_ADD = "GUILD_MEMBER_ADD"
    EVENT_GUILD_MEMBER_UPDATE = "GUILD_MEMBER_UPDATE"
    EVENT_GUILD_MEMBER_REMOVE = "GUILD_MEMBER_REMOVE"


@dataclass
class QQbotApiResponse:
    """QQbot API 响应"""
    success: bool                       # 是否成功
    status_code: int                    # HTTP 状态码
    data: dict[str, Any] | None = None  # 响应数据
    error: str | None = None            # 错误信息
    rate_limit_remaining: int = 0       # 剩余请求次数
    rate_limit_reset: int = 0           # 重置时间戳


class QQbotService:
    """
    QQbot 服务
    
    管理 QQbot 的连接、消息处理和 API 调用
    """
    
    def __init__(self, config: QQbotConfig):
        """
        初始化 QQbot 服务
        
        Args:
            config: QQbot 配置
        """
        self.config = config
        self.status = QQbotStatus.DISCONNECTED
        
        # 连接相关
        self._session: aiohttp.ClientSession | None = None
        self._websocket: aiohttp.ClientWebSocketResponse | None = None
        self._heartbeat_task: asyncio.Task | None = None
        
        # 认证信息
        self._access_token: str | None = None
        self._token_expires_at: float = 0
        
        # 事件处理器
        self._event_handlers: dict[str, list[Callable]] = {}
        
        # 消息处理器
        self._message_handler: Callable | None = None
        
        # 重连计数
        self._reconnect_count = 0
        
        # 序列号（用于消息确认）
        self._sequence: int = 0
        
        # 统计信息
        self._stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "events_processed": 0,
            "errors": 0,
            "reconnects": 0,
        }
        
        logger.info("QQbot 服务初始化完成")
    
    async def start(self) -> bool:
        """
        启动 QQbot 服务
        
        Returns:
            是否成功启动
        """
        if self.status in [QQbotStatus.CONNECTED, QQbotStatus.READY]:
            logger.warning("QQbot 服务已在运行")
            return True
        
        try:
            self.status = QQbotStatus.CONNECTING
            
            # 创建 HTTP 会话
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession()
            
            # 获取访问令牌
            if not await self._authenticate():
                self.status = QQbotStatus.ERROR
                return False
            
            # 连接 WebSocket
            if not await self._connect_websocket():
                self.status = QQbotStatus.ERROR
                return False
            
            self.status = QQbotStatus.READY
            logger.info("QQbot 服务启动成功")
            return True
            
        except Exception as e:
            logger.error(f"QQbot 服务启动失败: {e}")
            self.status = QQbotStatus.ERROR
            return False
    
    async def stop(self) -> None:
        """停止 QQbot 服务"""
        logger.info("正在停止 QQbot 服务...")
        
        # 停止心跳任务
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
        
        # 关闭 WebSocket
        if self._websocket and not self._websocket.closed:
            await self._websocket.close()
            self._websocket = None
        
        # 关闭 HTTP 会话
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
        
        self.status = QQbotStatus.DISCONNECTED
        logger.info("QQbot 服务已停止")
    
    async def _authenticate(self) -> bool:
        """
        认证并获取访问令牌
        
        Returns:
            是否认证成功
        """
        if not self.config.app_id or not self.config.app_secret:
            logger.error("缺少 App ID 或 App Secret")
            return False
        
        self.status = QQbotStatus.AUTHENTICATING
        
        try:
            url = f"{self.config.get_effective_api_url()}/api/v1/auth"
            
            async with self._session.post(
                url,
                json={
                    "app_id": self.config.app_id,
                    "app_secret": self.config.app_secret,
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self._access_token = data.get("access_token")
                    self._token_expires_at = time.time() + data.get("expires_in", 7200)
                    
                    logger.info("QQbot 认证成功")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"QQbot 认证失败: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"QQbot 认证异常: {e}")
            return False
    
    async def _connect_websocket(self) -> bool:
        """
        连接 WebSocket
        
        Returns:
            是否连接成功
        """
        if not self._access_token:
            logger.error("未获取访问令牌")
            return False
        
        try:
            headers = {
                "Authorization": f"Bearer {self._access_token}",
            }
            
            self._websocket = await self._session.ws_connect(
                self.config.websocket_url,
                headers=headers,
                heartbeat=self.config.heartbeat_interval,
            )
            
            logger.info("WebSocket 连接成功")
            
            # 启动消息接收循环
            asyncio.create_task(self._message_loop())
            
            # 启动心跳
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            return True
            
        except Exception as e:
            logger.error(f"WebSocket 连接失败: {e}")
            return False
    
    async def _message_loop(self) -> None:
        """WebSocket 消息接收循环"""
        if not self._websocket:
            return
        
        try:
            async for msg in self._websocket:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._handle_websocket_message(msg.data)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WebSocket 错误: {self._websocket.exception()}")
                    break
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    logger.warning("WebSocket 连接已关闭")
                    break
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"消息循环异常: {e}")
        
        # 尝试重连
        if self.status == QQbotStatus.READY:
            await self._reconnect()
    
    async def _handle_websocket_message(self, data: str) -> None:
        """
        处理 WebSocket 消息
        
        Args:
            data: 消息数据
        """
        try:
            message = json.loads(data)
            event_type = message.get("t")
            event_data = message.get("d", {})
            
            # 更新序列号
            if "s" in message:
                self._sequence = message["s"]
            
            # 处理不同类型的事件
            if event_type == QQbotEvent.EVENT_READY:
                await self._handle_ready_event(event_data)
            elif event_type == QQbotEvent.EVENT_MESSAGE_CREATE:
                await self._handle_message_event(event_data)
            else:
                await self._handle_generic_event(event_type, event_data)
            
            self._stats["events_processed"] += 1
            
        except json.JSONDecodeError as e:
            logger.error(f"消息解析失败: {e}")
        except Exception as e:
            logger.error(f"消息处理异常: {e}")
    
    async def _handle_ready_event(self, data: dict[str, Any]) -> None:
        """
        处理 Ready 事件
        
        Args:
            data: 事件数据
        """
        logger.info(f"QQbot 已就绪: {data.get('user', {}).get('username', 'unknown')}")
        
        # 触发事件处理器
        await self._trigger_event_handlers(QQbotEvent.EVENT_READY, data)
    
    async def _handle_message_event(self, data: dict[str, Any]) -> None:
        """
        处理消息事件
        
        Args:
            data: 事件数据
        """
        try:
            # 解析消息
            message = QQbotMessage(
                id=data.get("id", ""),
                channel_id=data.get("channel_id", ""),
                guild_id=data.get("guild_id", ""),
                author_id=data.get("author", {}).get("id", ""),
                content=data.get("content", ""),
                message_type=MessageType(data.get("type", 0)),
                timestamp=data.get("timestamp", datetime.now().isoformat()),
                mentions=[m.get("id", "") for m in data.get("mentions", [])],
                attachments=data.get("attachments", []),
                metadata=data,
            )
            
            self._stats["messages_received"] += 1
            
            # 检查权限
            if not self.config.is_guild_allowed(message.guild_id):
                logger.debug(f"忽略不允许的频道消息: {message.guild_id}")
                return
            
            if not self.config.is_channel_allowed(message.channel_id):
                logger.debug(f"忽略不允许的子频道消息: {message.channel_id}")
                return
            
            # 调用消息处理器
            if self._message_handler:
                await self._message_handler(message)
            
            # 触发事件处理器
            await self._trigger_event_handlers(QQbotEvent.EVENT_MESSAGE_CREATE, message.to_dict())
            
        except Exception as e:
            logger.error(f"消息事件处理失败: {e}")
    
    async def _handle_generic_event(self, event_type: str, data: dict[str, Any]) -> None:
        """
        处理通用事件
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
        await self._trigger_event_handlers(event_type, data)
    
    async def _trigger_event_handlers(self, event_type: str, data: Any) -> None:
        """
        触发事件处理器
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"事件处理器执行失败: {e}")
    
    async def _heartbeat_loop(self) -> None:
        """心跳循环"""
        while self.status in [QQbotStatus.CONNECTED, QQbotStatus.READY]:
            try:
                await asyncio.sleep(self.config.heartbeat_interval)
                
                if self._websocket and not self._websocket.closed:
                    await self._websocket.send_json({
                        "op": 1,  # Heartbeat
                        "d": self._sequence,
                    })
                    logger.debug("心跳已发送")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"心跳发送失败: {e}")
                break
    
    async def _reconnect(self) -> bool:
        """
        重连
        
        Returns:
            是否重连成功
        """
        if self._reconnect_count >= self.config.reconnect_attempts:
            logger.error(f"重连次数超过限制 ({self.config.reconnect_attempts})")
            self.status = QQbotStatus.ERROR
            return False
        
        self._reconnect_count += 1
        self.status = QQbotStatus.RECONNECTING
        self._stats["reconnects"] += 1
        
        logger.info(f"尝试重连 ({self._reconnect_count}/{self.config.reconnect_attempts})...")
        
        await asyncio.sleep(self.config.reconnect_delay)
        
        # 重新认证
        if not await self._authenticate():
            return await self._reconnect()
        
        # 重新连接 WebSocket
        if not await self._connect_websocket():
            return await self._reconnect()
        
        self._reconnect_count = 0
        self.status = QQbotStatus.READY
        logger.info("重连成功")
        return True
    
    def on_event(self, event_type: str) -> Callable:
        """
        注册事件处理器装饰器
        
        Args:
            event_type: 事件类型
            
        Returns:
            装饰器函数
        """
        def decorator(func: Callable) -> Callable:
            if event_type not in self._event_handlers:
                self._event_handlers[event_type] = []
            self._event_handlers[event_type].append(func)
            logger.debug(f"注册事件处理器: {event_type} -> {func.__name__}")
            return func
        return decorator
    
    def on_message(self, handler: Callable) -> None:
        """
        注册消息处理器
        
        Args:
            handler: 处理函数
        """
        self._message_handler = handler
        logger.debug(f"注册消息处理器: {handler.__name__ if hasattr(handler, '__name__') else 'anonymous'}")
    
    async def send_message(
        self,
        channel_id: str,
        content: str,
        message_type: MessageType = MessageType.TEXT,
        embed: dict[str, Any] | None = None,
        markdown: dict[str, Any] | None = None,
    ) -> QQbotApiResponse:
        """
        发送消息
        
        Args:
            channel_id: 频道 ID
            content: 消息内容
            message_type: 消息类型
            embed: 嵌入内容
            markdown: Markdown 内容
            
        Returns:
            API 响应
        """
        if self.status != QQbotStatus.READY:
            return QQbotApiResponse(
                success=False,
                status_code=0,
                error="QQbot 服务未就绪",
            )
        
        # 检查消息长度
        if len(content) > self.config.max_message_length:
            content = content[:self.config.max_message_length] + "..."
        
        try:
            url = f"{self.config.get_effective_api_url()}/api/v1/channels/{channel_id}/messages"
            
            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
            }
            
            payload: dict[str, Any] = {
                "content": content,
                "type": message_type.value,
            }
            
            if embed:
                payload["embed"] = embed
            if markdown:
                payload["markdown"] = markdown
            
            async with self._session.post(
                url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.config.message_timeout),
            ) as response:
                rate_limit_remaining = int(response.headers.get("X-RateLimit-Remaining", 0))
                rate_limit_reset = int(response.headers.get("X-RateLimit-Reset", 0))
                
                if response.status == 200:
                    data = await response.json()
                    self._stats["messages_sent"] += 1
                    logger.debug(f"消息发送成功: {channel_id}")
                    return QQbotApiResponse(
                        success=True,
                        status_code=response.status,
                        data=data,
                        rate_limit_remaining=rate_limit_remaining,
                        rate_limit_reset=rate_limit_reset,
                    )
                else:
                    error_text = await response.text()
                    self._stats["errors"] += 1
                    logger.error(f"消息发送失败: {response.status} - {error_text}")
                    return QQbotApiResponse(
                        success=False,
                        status_code=response.status,
                        error=error_text,
                        rate_limit_remaining=rate_limit_remaining,
                        rate_limit_reset=rate_limit_reset,
                    )
                    
        except asyncio.TimeoutError:
            self._stats["errors"] += 1
            return QQbotApiResponse(
                success=False,
                status_code=0,
                error="请求超时",
            )
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"消息发送异常: {e}")
            return QQbotApiResponse(
                success=False,
                status_code=0,
                error=str(e),
            )
    
    async def reply_message(
        self,
        message: QQbotMessage,
        content: str,
        mention_author: bool = False,
    ) -> QQbotApiResponse:
        """
        回复消息
        
        Args:
            message: 原消息
            content: 回复内容
            mention_author: 是否 @原作者
            
        Returns:
            API 响应
        """
        if mention_author:
            content = f"<@{message.author_id}> {content}"
        
        return await self.send_message(
            channel_id=message.channel_id,
            content=content,
        )
    
    async def get_guild_info(self, guild_id: str) -> QQbotApiResponse:
        """
        获取频道信息
        
        Args:
            guild_id: 频道 ID
            
        Returns:
            API 响应
        """
        if self.status != QQbotStatus.READY:
            return QQbotApiResponse(
                success=False,
                status_code=0,
                error="QQbot 服务未就绪",
            )
        
        try:
            url = f"{self.config.get_effective_api_url()}/api/v1/guilds/{guild_id}"
            
            headers = {
                "Authorization": f"Bearer {self._access_token}",
            }
            
            async with self._session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return QQbotApiResponse(
                        success=True,
                        status_code=response.status,
                        data=data,
                    )
                else:
                    error_text = await response.text()
                    return QQbotApiResponse(
                        success=False,
                        status_code=response.status,
                        error=error_text,
                    )
                    
        except Exception as e:
            logger.error(f"获取频道信息异常: {e}")
            return QQbotApiResponse(
                success=False,
                status_code=0,
                error=str(e),
            )
    
    async def get_channel_info(self, channel_id: str) -> QQbotApiResponse:
        """
        获取子频道信息
        
        Args:
            channel_id: 子频道 ID
            
        Returns:
            API 响应
        """
        if self.status != QQbotStatus.READY:
            return QQbotApiResponse(
                success=False,
                status_code=0,
                error="QQbot 服务未就绪",
            )
        
        try:
            url = f"{self.config.get_effective_api_url()}/api/v1/channels/{channel_id}"
            
            headers = {
                "Authorization": f"Bearer {self._access_token}",
            }
            
            async with self._session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return QQbotApiResponse(
                        success=True,
                        status_code=response.status,
                        data=data,
                    )
                else:
                    error_text = await response.text()
                    return QQbotApiResponse(
                        success=False,
                        status_code=response.status,
                        error=error_text,
                    )
                    
        except Exception as e:
            logger.error(f"获取子频道信息异常: {e}")
            return QQbotApiResponse(
                success=False,
                status_code=0,
                error=str(e),
            )
    
    def verify_webhook_signature(
        self,
        body: bytes,
        signature: str,
        timestamp: str,
    ) -> bool:
        """
        验证 Webhook 签名
        
        Args:
            body: 请求体
            signature: 签名
            timestamp: 时间戳
            
        Returns:
            是否验证通过
        """
        if not self.config.app_secret:
            logger.warning("未配置 App Secret，跳过签名验证")
            return True
        
        try:
            # 构建待签名字符串
            sign_str = timestamp + body.decode()
            
            # 计算签名
            expected_signature = hmac.new(
                self.config.app_secret.encode(),
                sign_str.encode(),
                hashlib.sha256,
            ).hexdigest()
            
            # 比较签名
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"签名验证异常: {e}")
            return False
    
    def get_stats(self) -> dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        return {
            "status": self.status.value,
            "messages_sent": self._stats["messages_sent"],
            "messages_received": self._stats["messages_received"],
            "events_processed": self._stats["events_processed"],
            "errors": self._stats["errors"],
            "reconnects": self._stats["reconnects"],
            "reconnect_count": self._reconnect_count,
        }
    
    def is_ready(self) -> bool:
        """检查服务是否就绪"""
        return self.status == QQbotStatus.READY
