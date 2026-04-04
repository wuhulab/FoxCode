"""
FoxCode Playwright 浏览器自动化工具

提供浏览器自动化、页面操作和测试功能
"""

from __future__ import annotations

import asyncio
import base64
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from foxcode.tools.base import (
    BaseTool,
    ToolCategory,
    ToolParameter,
    ToolResult,
    tool,
)

logger = logging.getLogger(__name__)


class BrowserSession:
    """
    浏览器会话类
    
    管理单个浏览器实例的生命周期
    """
    
    def __init__(
        self,
        session_id: str,
        browser_type: str = "chromium",
        headless: bool = True,
        viewport_width: int = 1280,
        viewport_height: int = 720,
        default_timeout: int = 30000,
        navigation_timeout: int = 30000,
    ):
        """
        初始化浏览器会话
        
        Args:
            session_id: 会话唯一标识
            browser_type: 浏览器类型 (chromium/firefox/webkit)
            headless: 是否使用无头模式
            viewport_width: 视口宽度
            viewport_height: 视口高度
            default_timeout: 默认超时时间（毫秒）
            navigation_timeout: 导航超时时间（毫秒）
        """
        self.session_id = session_id
        self.browser_type = browser_type
        self.headless = headless
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.default_timeout = default_timeout
        self.navigation_timeout = navigation_timeout
        
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._console_logs: list[dict[str, Any]] = []
        self._created_at = datetime.now()
        self._is_closed = False
    
    @property
    def page(self):
        """获取当前页面"""
        return self._page
    
    @property
    def context(self):
        """获取浏览器上下文"""
        return self._context
    
    @property
    def browser(self):
        """获取浏览器实例"""
        return self._browser
    
    @property
    def is_active(self) -> bool:
        """检查会话是否活跃"""
        return self._browser is not None and not self._is_closed
    
    async def start(self) -> dict[str, Any]:
        """
        启动浏览器会话
        
        Returns:
            会话信息字典
        """
        try:
            # 延迟导入 Playwright
            from playwright.async_api import async_playwright
            
            # 启动 Playwright
            self._playwright = await async_playwright().start()
            
            # 选择浏览器类型
            browser_launcher = getattr(self._playwright, self.browser_type, None)
            if browser_launcher is None:
                raise ValueError(f"不支持的浏览器类型: {self.browser_type}")
            
            # 启动浏览器
            self._browser = await browser_launcher.launch(headless=self.headless)
            
            # 创建浏览器上下文
            self._context = await self._browser.new_context(
                viewport={
                    "width": self.viewport_width,
                    "height": self.viewport_height,
                },
            )
            
            # 设置默认超时
            self._context.set_default_timeout(self.default_timeout)
            self._context.set_default_navigation_timeout(self.navigation_timeout)
            
            # 创建新页面
            self._page = await self._context.new_page()
            
            # 监听控制台日志
            self._page.on("console", self._on_console_message)
            
            logger.info(f"浏览器会话已启动: {self.session_id} ({self.browser_type})")
            
            return {
                "session_id": self.session_id,
                "browser_type": self.browser_type,
                "headless": self.headless,
                "viewport": {
                    "width": self.viewport_width,
                    "height": self.viewport_height,
                },
                "created_at": self._created_at.isoformat(),
            }
            
        except Exception as e:
            logger.error(f"启动浏览器失败: {e}")
            await self.close()
            raise
    
    def _on_console_message(self, msg) -> None:
        """处理控制台消息"""
        self._console_logs.append({
            "type": msg.type,
            "text": msg.text,
            "timestamp": datetime.now().isoformat(),
        })
    
    def get_console_logs(self, clear: bool = False) -> list[dict[str, Any]]:
        """
        获取控制台日志
        
        Args:
            clear: 是否清空日志
            
        Returns:
            控制台日志列表
        """
        logs = self._console_logs.copy()
        if clear:
            self._console_logs.clear()
        return logs
    
    async def close(self) -> None:
        """关闭浏览器会话"""
        if self._is_closed:
            return
        
        self._is_closed = True
        
        try:
            if self._page:
                await self._page.close()
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
            
            logger.info(f"浏览器会话已关闭: {self.session_id}")
            
        except Exception as e:
            logger.warning(f"关闭浏览器时出错: {e}")
        finally:
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None


class PlaywrightSessionManager:
    """
    Playwright 会话管理器
    
    管理多个浏览器会话的生命周期
    """
    
    _instance: Optional["PlaywrightSessionManager"] = None
    _sessions: dict[str, BrowserSession] = {}
    _default_session_id: Optional[str] = None
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_instance(cls) -> "PlaywrightSessionManager":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def create_session(
        self,
        browser_type: str = "chromium",
        headless: bool = True,
        viewport_width: int = 1280,
        viewport_height: int = 720,
        default_timeout: int = 30000,
        navigation_timeout: int = 30000,
    ) -> BrowserSession:
        """
        创建新的浏览器会话
        
        Args:
            browser_type: 浏览器类型
            headless: 是否无头模式
            viewport_width: 视口宽度
            viewport_height: 视口高度
            default_timeout: 默认超时
            navigation_timeout: 导航超时
            
        Returns:
            浏览器会话实例
        """
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        
        session = BrowserSession(
            session_id=session_id,
            browser_type=browser_type,
            headless=headless,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            default_timeout=default_timeout,
            navigation_timeout=navigation_timeout,
        )
        
        self._sessions[session_id] = session
        
        # 如果是第一个会话，设为默认
        if self._default_session_id is None:
            self._default_session_id = session_id
        
        logger.info(f"创建浏览器会话: {session_id}")
        return session
    
    def get_session(self, session_id: Optional[str] = None) -> Optional[BrowserSession]:
        """
        获取浏览器会话
        
        Args:
            session_id: 会话ID，如果为None则返回默认会话
            
        Returns:
            浏览器会话实例
        """
        if session_id is None:
            session_id = self._default_session_id
        
        if session_id is None:
            return None
        
        return self._sessions.get(session_id)
    
    def get_active_session(self, session_id: Optional[str] = None) -> BrowserSession:
        """
        获取活跃的浏览器会话，如果不存在则抛出异常
        
        Args:
            session_id: 会话ID
            
        Returns:
            浏览器会话实例
            
        Raises:
            ValueError: 如果没有活跃的会话
        """
        session = self.get_session(session_id)
        
        if session is None or not session.is_active:
            raise ValueError("没有活跃的浏览器会话，请先启动浏览器")
        
        return session
    
    async def close_session(self, session_id: Optional[str] = None) -> bool:
        """
        关闭浏览器会话
        
        Args:
            session_id: 会话ID，如果为None则关闭默认会话
            
        Returns:
            是否成功关闭
        """
        if session_id is None:
            session_id = self._default_session_id
        
        if session_id is None:
            return False
        
        session = self._sessions.get(session_id)
        if session:
            await session.close()
            del self._sessions[session_id]
            
            # 如果关闭的是默认会话，更新默认会话
            if self._default_session_id == session_id:
                self._default_session_id = next(iter(self._sessions), None)
            
            return True
        
        return False
    
    async def close_all_sessions(self) -> int:
        """
        关闭所有浏览器会话
        
        Returns:
            关闭的会话数量
        """
        count = 0
        for session_id in list(self._sessions.keys()):
            if await self.close_session(session_id):
                count += 1
        
        self._default_session_id = None
        return count
    
    def list_sessions(self) -> list[dict[str, Any]]:
        """
        列出所有会话
        
        Returns:
            会话信息列表
        """
        return [
            {
                "session_id": session.session_id,
                "browser_type": session.browser_type,
                "is_active": session.is_active,
                "created_at": session._created_at.isoformat(),
                "is_default": session.session_id == self._default_session_id,
            }
            for session in self._sessions.values()
        ]
    
    def set_default_session(self, session_id: str) -> bool:
        """
        设置默认会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            是否成功设置
        """
        if session_id in self._sessions:
            self._default_session_id = session_id
            return True
        return False


# 全局会话管理器实例
session_manager = PlaywrightSessionManager()


# ==================== 浏览器生命周期工具 ====================

@tool
class PlaywrightStartTool(BaseTool):
    """启动 Playwright 浏览器"""
    
    name = "playwright_start"
    description = "Start a new browser instance, returns session ID for subsequent operations"
    category = ToolCategory.WEB
    parameters = [
        ToolParameter(
            name="browser_type",
            type="string",
            description="浏览器类型: chromium, firefox 或 webkit",
            required=False,
            default="chromium",
            enum=["chromium", "firefox", "webkit"],
        ),
        ToolParameter(
            name="headless",
            type="boolean",
            description="是否使用无头模式（不显示浏览器窗口）",
            required=False,
            default=True,
        ),
        ToolParameter(
            name="viewport_width",
            type="integer",
            description="浏览器视口宽度（像素）",
            required=False,
            default=1280,
        ),
        ToolParameter(
            name="viewport_height",
            type="integer",
            description="浏览器视口高度（像素）",
            required=False,
            default=720,
        ),
    ]
    
    async def execute(
        self,
        browser_type: str = "chromium",
        headless: bool = True,
        viewport_width: int = 1280,
        viewport_height: int = 720,
        **kwargs: Any,
    ) -> ToolResult:
        """执行启动浏览器"""
        try:
            # 从配置获取默认值
            if self.config and hasattr(self.config, "playwright"):
                pw_config = self.config.playwright
                browser_type = browser_type or pw_config.browser_type
                headless = headless if headless is not None else pw_config.headless
                viewport_width = viewport_width or pw_config.viewport_width
                viewport_height = viewport_height or pw_config.viewport_height
            
            # 创建会话
            session = session_manager.create_session(
                browser_type=browser_type,
                headless=headless,
                viewport_width=viewport_width,
                viewport_height=viewport_height,
            )
            
            # 启动浏览器
            session_info = await session.start()
            
            output = f"✅ 浏览器已启动\n"
            output += f"会话ID: {session.session_id}\n"
            output += f"浏览器类型: {browser_type}\n"
            output += f"无头模式: {headless}\n"
            output += f"视口大小: {viewport_width}x{viewport_height}\n"
            
            return ToolResult(
                success=True,
                output=output,
                data=session_info,
            )
            
        except ImportError:
            return ToolResult(
                success=False,
                output="",
                error="Playwright 未安装。请运行: pip install playwright && playwright install",
            )
        except Exception as e:
            logger.error(f"启动浏览器失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"启动浏览器失败: {str(e)}",
            )


@tool
class PlaywrightCloseTool(BaseTool):
    """关闭 Playwright 浏览器"""
    
    name = "playwright_close"
    description = "Close specified browser session or all sessions"
    category = ToolCategory.WEB
    parameters = [
        ToolParameter(
            name="session_id",
            type="string",
            description="要关闭的会话ID，不指定则关闭默认会话",
            required=False,
        ),
        ToolParameter(
            name="close_all",
            type="boolean",
            description="是否关闭所有会话",
            required=False,
            default=False,
        ),
    ]
    
    async def execute(
        self,
        session_id: Optional[str] = None,
        close_all: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        """执行关闭浏览器"""
        try:
            if close_all:
                count = await session_manager.close_all_sessions()
                return ToolResult(
                    success=True,
                    output=f"✅ 已关闭 {count} 个浏览器会话",
                    data={"closed_count": count},
                )
            
            success = await session_manager.close_session(session_id)
            
            if success:
                return ToolResult(
                    success=True,
                    output=f"✅ 浏览器会话已关闭: {session_id or '默认会话'}",
                )
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"未找到会话: {session_id or '默认会话'}",
                )
                
        except Exception as e:
            logger.error(f"关闭浏览器失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"关闭浏览器失败: {str(e)}",
            )


@tool
class PlaywrightListSessionsTool(BaseTool):
    """列出所有浏览器会话"""
    
    name = "playwright_list_sessions"
    description = "List all active browser sessions"
    category = ToolCategory.WEB
    parameters = []
    
    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行列出会话"""
        try:
            sessions = session_manager.list_sessions()
            
            if not sessions:
                return ToolResult(
                    success=True,
                    output="当前没有活跃的浏览器会话",
                    data={"sessions": []},
                )
            
            output = f"当前有 {len(sessions)} 个浏览器会话:\n\n"
            for session in sessions:
                default_mark = " (默认)" if session["is_default"] else ""
                output += f"- 会话ID: {session['session_id']}{default_mark}\n"
                output += f"  浏览器: {session['browser_type']}\n"
                output += f"  状态: {'活跃' if session['is_active'] else '已关闭'}\n"
                output += f"  创建时间: {session['created_at']}\n\n"
            
            return ToolResult(
                success=True,
                output=output,
                data={"sessions": sessions},
            )
            
        except Exception as e:
            logger.error(f"列出会话失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"列出会话失败: {str(e)}",
            )


# ==================== 页面导航工具 ====================

@tool
class PlaywrightNavigateTool(BaseTool):
    """导航到指定URL"""
    
    name = "playwright_navigate"
    description = "Navigate browser to specified URL"
    category = ToolCategory.WEB
    parameters = [
        ToolParameter(
            name="url",
            type="string",
            description="要导航到的URL地址",
            required=True,
        ),
        ToolParameter(
            name="session_id",
            type="string",
            description="浏览器会话ID，不指定则使用默认会话",
            required=False,
        ),
        ToolParameter(
            name="wait_until",
            type="string",
            description="等待页面加载完成的状态",
            required=False,
            default="load",
            enum=["load", "domcontentloaded", "networkidle"],
        ),
    ]
    
    async def execute(
        self,
        url: str,
        session_id: Optional[str] = None,
        wait_until: str = "load",
        **kwargs: Any,
    ) -> ToolResult:
        """执行页面导航"""
        try:
            session = session_manager.get_active_session(session_id)
            page = session.page
            
            # 导航到URL
            response = await page.goto(url, wait_until=wait_until)
            
            output = f"✅ 已导航到: {url}\n"
            output += f"状态码: {response.status if response else 'N/A'}\n"
            output += f"页面标题: {await page.title()}\n"
            output += f"当前URL: {page.url}\n"
            
            return ToolResult(
                success=True,
                output=output,
                data={
                    "url": url,
                    "final_url": page.url,
                    "status": response.status if response else None,
                    "title": await page.title(),
                },
            )
            
        except ValueError as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e),
            )
        except Exception as e:
            logger.error(f"导航失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"导航失败: {str(e)}",
            )


@tool
class PlaywrightGoBackTool(BaseTool):
    """浏览器后退"""
    
    name = "playwright_go_back"
    description = "Go back to previous page in browser history"
    category = ToolCategory.WEB
    parameters = [
        ToolParameter(
            name="session_id",
            type="string",
            description="浏览器会话ID",
            required=False,
        ),
    ]
    
    async def execute(
        self,
        session_id: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        """执行后退操作"""
        try:
            session = session_manager.get_active_session(session_id)
            page = session.page
            
            await page.go_back()
            
            return ToolResult(
                success=True,
                output=f"✅ 已后退\n当前URL: {page.url}",
                data={"url": page.url},
            )
            
        except Exception as e:
            logger.error(f"后退失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"后退失败: {str(e)}",
            )


@tool
class PlaywrightGoForwardTool(BaseTool):
    """浏览器前进"""
    
    name = "playwright_go_forward"
    description = "Go forward to next page in browser history"
    category = ToolCategory.WEB
    parameters = [
        ToolParameter(
            name="session_id",
            type="string",
            description="浏览器会话ID",
            required=False,
        ),
    ]
    
    async def execute(
        self,
        session_id: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        """执行前进操作"""
        try:
            session = session_manager.get_active_session(session_id)
            page = session.page
            
            await page.go_forward()
            
            return ToolResult(
                success=True,
                output=f"✅ 已前进\n当前URL: {page.url}",
                data={"url": page.url},
            )
            
        except Exception as e:
            logger.error(f"前进失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"前进失败: {str(e)}",
            )


# ==================== 页面交互工具 ====================

@tool
class PlaywrightClickTool(BaseTool):
    """点击页面元素"""
    
    name = "playwright_click"
    description = "Click a specified element on the page"
    category = ToolCategory.WEB
    parameters = [
        ToolParameter(
            name="selector",
            type="string",
            description="CSS选择器或XPath表达式",
            required=True,
        ),
        ToolParameter(
            name="session_id",
            type="string",
            description="浏览器会话ID",
            required=False,
        ),
        ToolParameter(
            name="timeout",
            type="integer",
            description="等待元素出现的超时时间（毫秒）",
            required=False,
            default=30000,
        ),
        ToolParameter(
            name="force",
            type="boolean",
            description="是否强制点击（跳过可操作性检查）",
            required=False,
            default=False,
        ),
    ]
    
    async def execute(
        self,
        selector: str,
        session_id: Optional[str] = None,
        timeout: int = 30000,
        force: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        """执行点击操作"""
        try:
            session = session_manager.get_active_session(session_id)
            page = session.page
            
            # 等待元素出现
            await page.wait_for_selector(selector, timeout=timeout)
            
            # 执行点击
            await page.click(selector, force=force)
            
            return ToolResult(
                success=True,
                output=f"✅ 已点击元素: {selector}",
                data={"selector": selector},
            )
            
        except Exception as e:
            logger.error(f"点击失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"点击元素失败: {str(e)}",
            )


@tool
class PlaywrightFillTool(BaseTool):
    """在输入框中填写文本"""
    
    name = "playwright_fill"
    description = "Fill text content in specified input field"
    category = ToolCategory.WEB
    parameters = [
        ToolParameter(
            name="selector",
            type="string",
            description="输入框的CSS选择器",
            required=True,
        ),
        ToolParameter(
            name="text",
            type="string",
            description="要填写的文本内容",
            required=True,
        ),
        ToolParameter(
            name="session_id",
            type="string",
            description="浏览器会话ID",
            required=False,
        ),
        ToolParameter(
            name="clear_first",
            type="boolean",
            description="是否先清空输入框",
            required=False,
            default=True,
        ),
    ]
    
    async def execute(
        self,
        selector: str,
        text: str,
        session_id: Optional[str] = None,
        clear_first: bool = True,
        **kwargs: Any,
    ) -> ToolResult:
        """执行填写操作"""
        try:
            session = session_manager.get_active_session(session_id)
            page = session.page
            
            if clear_first:
                await page.fill(selector, text)
            else:
                await page.type(selector, text)
            
            return ToolResult(
                success=True,
                output=f"✅ 已填写文本到: {selector}\n内容: {text[:50]}{'...' if len(text) > 50 else ''}",
                data={"selector": selector, "text": text},
            )
            
        except Exception as e:
            logger.error(f"填写失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"填写文本失败: {str(e)}",
            )


@tool
class PlaywrightSelectTool(BaseTool):
    """选择下拉框选项"""
    
    name = "playwright_select"
    description = "Select specified option in dropdown select box"
    category = ToolCategory.WEB
    parameters = [
        ToolParameter(
            name="selector",
            type="string",
            description="下拉框的CSS选择器",
            required=True,
        ),
        ToolParameter(
            name="value",
            type="string",
            description="要选择的选项值或文本",
            required=True,
        ),
        ToolParameter(
            name="session_id",
            type="string",
            description="浏览器会话ID",
            required=False,
        ),
    ]
    
    async def execute(
        self,
        selector: str,
        value: str,
        session_id: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        """执行选择操作"""
        try:
            session = session_manager.get_active_session(session_id)
            page = session.page
            
            await page.select_option(selector, value)
            
            return ToolResult(
                success=True,
                output=f"✅ 已选择选项: {value}",
                data={"selector": selector, "value": value},
            )
            
        except Exception as e:
            logger.error(f"选择失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"选择选项失败: {str(e)}",
            )


@tool
class PlaywrightHoverTool(BaseTool):
    """悬停在元素上"""
    
    name = "playwright_hover"
    description = "Hover mouse over specified element"
    category = ToolCategory.WEB
    parameters = [
        ToolParameter(
            name="selector",
            type="string",
            description="元素的CSS选择器",
            required=True,
        ),
        ToolParameter(
            name="session_id",
            type="string",
            description="浏览器会话ID",
            required=False,
        ),
    ]
    
    async def execute(
        self,
        selector: str,
        session_id: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        """执行悬停操作"""
        try:
            session = session_manager.get_active_session(session_id)
            page = session.page
            
            await page.hover(selector)
            
            return ToolResult(
                success=True,
                output=f"✅ 已悬停在元素上: {selector}",
                data={"selector": selector},
            )
            
        except Exception as e:
            logger.error(f"悬停失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"悬停失败: {str(e)}",
            )


@tool
class PlaywrightPressKeyTool(BaseTool):
    """按下键盘按键"""
    
    name = "playwright_press_key"
    description = "Simulate keyboard key press on page"
    category = ToolCategory.WEB
    parameters = [
        ToolParameter(
            name="key",
            type="string",
            description="要按下的键（如 Enter, Tab, Escape, ArrowDown 等）",
            required=True,
        ),
        ToolParameter(
            name="session_id",
            type="string",
            description="浏览器会话ID",
            required=False,
        ),
        ToolParameter(
            name="selector",
            type="string",
            description="目标元素选择器，不指定则在当前焦点元素上操作",
            required=False,
        ),
    ]
    
    async def execute(
        self,
        key: str,
        session_id: Optional[str] = None,
        selector: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        """执行按键操作"""
        try:
            session = session_manager.get_active_session(session_id)
            page = session.page
            
            if selector:
                await page.press(selector, key)
            else:
                await page.keyboard.press(key)
            
            return ToolResult(
                success=True,
                output=f"✅ 已按下按键: {key}",
                data={"key": key, "selector": selector},
            )
            
        except Exception as e:
            logger.error(f"按键失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"按键操作失败: {str(e)}",
            )


# ==================== 页面信息获取工具 ====================

@tool
class PlaywrightScreenshotTool(BaseTool):
    """页面截图"""
    
    name = "playwright_screenshot"
    description = "Take screenshot of current page or specified element"
    category = ToolCategory.WEB
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="截图保存路径（相对于工作目录）",
            required=False,
        ),
        ToolParameter(
            name="selector",
            type="string",
            description="要截图的元素选择器，不指定则截取整个页面",
            required=False,
        ),
        ToolParameter(
            name="session_id",
            type="string",
            description="浏览器会话ID",
            required=False,
        ),
        ToolParameter(
            name="full_page",
            type="boolean",
            description="是否截取完整页面（包括滚动区域）",
            required=False,
            default=False,
        ),
    ]
    
    async def execute(
        self,
        path: Optional[str] = None,
        selector: Optional[str] = None,
        session_id: Optional[str] = None,
        full_page: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        """执行截图操作"""
        try:
            session = session_manager.get_active_session(session_id)
            page = session.page
            
            # 确定保存路径
            if path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_dir = Path(".foxcode/screenshots")
                screenshot_dir.mkdir(parents=True, exist_ok=True)
                path = str(screenshot_dir / f"screenshot_{timestamp}.png")
            
            # 执行截图
            if selector:
                element = await page.query_selector(selector)
                if element:
                    screenshot_bytes = await element.screenshot()
                else:
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"未找到元素: {selector}",
                    )
            else:
                screenshot_bytes = await page.screenshot(
                    path=path,
                    full_page=full_page,
                )
            
            # 如果指定了路径且不是整页截图，需要手动保存
            if selector and path:
                with open(path, "wb") as f:
                    f.write(screenshot_bytes)
            
            # 转换为 base64
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode()
            
            output = f"✅ 截图已保存: {path}\n"
            output += f"文件大小: {len(screenshot_bytes)} 字节\n"
            
            return ToolResult(
                success=True,
                output=output,
                data={
                    "path": path,
                    "size": len(screenshot_bytes),
                    "base64": screenshot_base64[:100] + "...",  # 只返回前100字符
                },
            )
            
        except Exception as e:
            logger.error(f"截图失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"截图失败: {str(e)}",
            )


@tool
class PlaywrightGetVisibleTextTool(BaseTool):
    """获取页面可见文本"""
    
    name = "playwright_get_visible_text"
    description = "Get visible text content from current page or specified element"
    category = ToolCategory.WEB
    parameters = [
        ToolParameter(
            name="selector",
            type="string",
            description="元素的CSS选择器，不指定则获取整个页面",
            required=False,
        ),
        ToolParameter(
            name="session_id",
            type="string",
            description="浏览器会话ID",
            required=False,
        ),
    ]
    
    async def execute(
        self,
        selector: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        """执行获取文本操作"""
        try:
            session = session_manager.get_active_session(session_id)
            page = session.page
            
            if selector:
                element = await page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                else:
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"未找到元素: {selector}",
                    )
            else:
                text = await page.inner_text("body")
            
            # 限制输出长度
            max_length = 5000
            truncated = len(text) > max_length
            display_text = text[:max_length] + "..." if truncated else text
            
            return ToolResult(
                success=True,
                output=f"页面文本内容:\n\n{display_text}",
                data={
                    "text": text,
                    "length": len(text),
                    "truncated": truncated,
                },
            )
            
        except Exception as e:
            logger.error(f"获取文本失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"获取文本失败: {str(e)}",
            )


@tool
class PlaywrightGetVisibleHtmlTool(BaseTool):
    """获取页面HTML"""
    
    name = "playwright_get_visible_html"
    description = "获取当前页面或指定元素的HTML内容"
    category = ToolCategory.WEB
    parameters = [
        ToolParameter(
            name="selector",
            type="string",
            description="元素的CSS选择器，不指定则获取整个页面",
            required=False,
        ),
        ToolParameter(
            name="session_id",
            type="string",
            description="浏览器会话ID",
            required=False,
        ),
    ]
    
    async def execute(
        self,
        selector: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        """执行获取HTML操作"""
        try:
            session = session_manager.get_active_session(session_id)
            page = session.page
            
            if selector:
                element = await page.query_selector(selector)
                if element:
                    html = await element.inner_html()
                else:
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"未找到元素: {selector}",
                    )
            else:
                html = await page.content()
            
            # 限制输出长度
            max_length = 10000
            truncated = len(html) > max_length
            display_html = html[:max_length] + "..." if truncated else html
            
            return ToolResult(
                success=True,
                output=f"页面HTML内容:\n\n```html\n{display_html}\n```",
                data={
                    "html": html,
                    "length": len(html),
                    "truncated": truncated,
                },
            )
            
        except Exception as e:
            logger.error(f"获取HTML失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"获取HTML失败: {str(e)}",
            )


@tool
class PlaywrightGetTool(BaseTool):
    """获取元素属性或内容"""
    
    name = "playwright_get"
    description = "Get specified element's attribute value or content"
    category = ToolCategory.WEB
    parameters = [
        ToolParameter(
            name="selector",
            type="string",
            description="元素的CSS选择器",
            required=True,
        ),
        ToolParameter(
            name="attribute",
            type="string",
            description="要获取的属性名，如 href, src, value 等",
            required=False,
        ),
        ToolParameter(
            name="session_id",
            type="string",
            description="浏览器会话ID",
            required=False,
        ),
    ]
    
    async def execute(
        self,
        selector: str,
        attribute: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        """执行获取属性操作"""
        try:
            session = session_manager.get_active_session(session_id)
            page = session.page
            
            element = await page.query_selector(selector)
            if not element:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"未找到元素: {selector}",
                )
            
            if attribute:
                value = await element.get_attribute(attribute)
                return ToolResult(
                    success=True,
                    output=f"属性 '{attribute}' 的值: {value}",
                    data={"attribute": attribute, "value": value},
                )
            else:
                # 获取所有属性
                text = await element.inner_text()
                tag = await element.evaluate("el => el.tagName")
                
                return ToolResult(
                    success=True,
                    output=f"元素信息:\n标签: {tag}\n文本: {text}",
                    data={
                        "tag": tag,
                        "text": text,
                    },
                )
            
        except Exception as e:
            logger.error(f"获取属性失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"获取属性失败: {str(e)}",
            )


# ==================== 测试辅助工具 ====================

@tool
class PlaywrightExpectResponseTool(BaseTool):
    """等待响应"""
    
    name = "playwright_expect_response"
    description = "Wait for specific HTTP response"
    category = ToolCategory.WEB
    parameters = [
        ToolParameter(
            name="url_pattern",
            type="string",
            description="要匹配的URL模式（支持通配符）",
            required=True,
        ),
        ToolParameter(
            name="session_id",
            type="string",
            description="浏览器会话ID",
            required=False,
        ),
        ToolParameter(
            name="timeout",
            type="integer",
            description="超时时间（毫秒）",
            required=False,
            default=30000,
        ),
    ]
    
    async def execute(
        self,
        url_pattern: str,
        session_id: Optional[str] = None,
        timeout: int = 30000,
        **kwargs: Any,
    ) -> ToolResult:
        """执行等待响应操作"""
        try:
            session = session_manager.get_active_session(session_id)
            page = session.page
            
            response = await page.wait_for_response(url_pattern, timeout=timeout)
            
            output = f"✅ 收到响应\n"
            output += f"URL: {response.url}\n"
            output += f"状态码: {response.status}\n"
            
            return ToolResult(
                success=True,
                output=output,
                data={
                    "url": response.url,
                    "status": response.status,
                },
            )
            
        except Exception as e:
            logger.error(f"等待响应失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"等待响应失败: {str(e)}",
            )


@tool
class PlaywrightAssertResponseTool(BaseTool):
    """断言响应状态"""
    
    name = "playwright_assert_response"
    description = "Assert HTTP response status code or content"
    category = ToolCategory.WEB
    parameters = [
        ToolParameter(
            name="url_pattern",
            type="string",
            description="要匹配的URL模式",
            required=True,
        ),
        ToolParameter(
            name="expected_status",
            type="integer",
            description="期望的状态码",
            required=False,
        ),
        ToolParameter(
            name="session_id",
            type="string",
            description="浏览器会话ID",
            required=False,
        ),
    ]
    
    async def execute(
        self,
        url_pattern: str,
        expected_status: Optional[int] = None,
        session_id: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        """执行断言操作"""
        try:
            session = session_manager.get_active_session(session_id)
            page = session.page
            
            response = await page.wait_for_response(url_pattern)
            
            assertions_passed = []
            assertions_failed = []
            
            if expected_status:
                if response.status == expected_status:
                    assertions_passed.append(f"状态码等于 {expected_status}")
                else:
                    assertions_failed.append(
                        f"状态码不匹配: 期望 {expected_status}, 实际 {response.status}"
                    )
            
            if assertions_failed:
                return ToolResult(
                    success=False,
                    output=f"❌ 断言失败:\n" + "\n".join(assertions_failed),
                    data={
                        "passed": assertions_passed,
                        "failed": assertions_failed,
                        "actual_status": response.status,
                    },
                )
            
            return ToolResult(
                success=True,
                output=f"✅ 断言通过:\n" + "\n".join(assertions_passed) if assertions_passed else "✅ 响应已收到",
                data={
                    "passed": assertions_passed,
                    "url": response.url,
                    "status": response.status,
                },
            )
            
        except Exception as e:
            logger.error(f"断言失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"断言失败: {str(e)}",
            )


@tool
class PlaywrightEvaluateTool(BaseTool):
    """执行JavaScript"""
    
    name = "playwright_evaluate"
    description = "Execute JavaScript code in the page"
    category = ToolCategory.WEB
    parameters = [
        ToolParameter(
            name="script",
            type="string",
            description="要执行的JavaScript代码",
            required=True,
        ),
        ToolParameter(
            name="session_id",
            type="string",
            description="浏览器会话ID",
            required=False,
        ),
    ]
    
    async def execute(
        self,
        script: str,
        session_id: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        """执行JavaScript代码"""
        try:
            session = session_manager.get_active_session(session_id)
            page = session.page
            
            result = await page.evaluate(script)
            
            return ToolResult(
                success=True,
                output=f"✅ JavaScript 执行成功\n返回值: {result}",
                data={"result": result},
            )
            
        except Exception as e:
            logger.error(f"执行JavaScript失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"执行JavaScript失败: {str(e)}",
            )


# ==================== 高级功能工具 ====================

@tool
class PlaywrightResizeTool(BaseTool):
    """调整视口大小"""
    
    name = "playwright_resize"
    description = "Resize browser viewport dimensions"
    category = ToolCategory.WEB
    parameters = [
        ToolParameter(
            name="width",
            type="integer",
            description="视口宽度（像素）",
            required=True,
        ),
        ToolParameter(
            name="height",
            type="integer",
            description="视口高度（像素）",
            required=True,
        ),
        ToolParameter(
            name="session_id",
            type="string",
            description="浏览器会话ID",
            required=False,
        ),
    ]
    
    async def execute(
        self,
        width: int,
        height: int,
        session_id: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        """执行调整视口操作"""
        try:
            session = session_manager.get_active_session(session_id)
            page = session.page
            
            await page.set_viewport_size({"width": width, "height": height})
            
            return ToolResult(
                success=True,
                output=f"✅ 视口已调整为: {width}x{height}",
                data={"width": width, "height": height},
            )
            
        except Exception as e:
            logger.error(f"调整视口失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"调整视口失败: {str(e)}",
            )


@tool
class PlaywrightUploadFileTool(BaseTool):
    """上传文件"""
    
    name = "playwright_upload_file"
    description = "Upload file to file input element"
    category = ToolCategory.WEB
    parameters = [
        ToolParameter(
            name="selector",
            type="string",
            description="文件输入框的CSS选择器",
            required=True,
        ),
        ToolParameter(
            name="file_path",
            type="string",
            description="要上传的文件路径",
            required=True,
        ),
        ToolParameter(
            name="session_id",
            type="string",
            description="浏览器会话ID",
            required=False,
        ),
    ]
    
    async def execute(
        self,
        selector: str,
        file_path: str,
        session_id: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        """执行文件上传操作"""
        try:
            session = session_manager.get_active_session(session_id)
            page = session.page
            
            # 检查文件是否存在
            file = Path(file_path)
            if not file.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"文件不存在: {file_path}",
                )
            
            await page.set_input_files(selector, str(file.absolute()))
            
            return ToolResult(
                success=True,
                output=f"✅ 文件已上传: {file_path}",
                data={"selector": selector, "file_path": file_path},
            )
            
        except Exception as e:
            logger.error(f"上传文件失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"上传文件失败: {str(e)}",
            )


@tool
class PlaywrightDragTool(BaseTool):
    """拖拽元素"""
    
    name = "playwright_drag"
    description = "Drag one element to another location"
    category = ToolCategory.WEB
    parameters = [
        ToolParameter(
            name="source_selector",
            type="string",
            description="源元素的CSS选择器",
            required=True,
        ),
        ToolParameter(
            name="target_selector",
            type="string",
            description="目标元素的CSS选择器",
            required=True,
        ),
        ToolParameter(
            name="session_id",
            type="string",
            description="浏览器会话ID",
            required=False,
        ),
    ]
    
    async def execute(
        self,
        source_selector: str,
        target_selector: str,
        session_id: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        """执行拖拽操作"""
        try:
            session = session_manager.get_active_session(session_id)
            page = session.page
            
            source = await page.query_selector(source_selector)
            target = await page.query_selector(target_selector)
            
            if not source:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"未找到源元素: {source_selector}",
                )
            
            if not target:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"未找到目标元素: {target_selector}",
                )
            
            await source.drag_to(target)
            
            return ToolResult(
                success=True,
                output=f"✅ 已将元素从 {source_selector} 拖拽到 {target_selector}",
                data={"source": source_selector, "target": target_selector},
            )
            
        except Exception as e:
            logger.error(f"拖拽失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"拖拽失败: {str(e)}",
            )


@tool
class PlaywrightClickAndSwitchTabTool(BaseTool):
    """点击并切换标签页"""
    
    name = "playwright_click_and_switch_tab"
    description = "Click link to open new tab and switch to it"
    category = ToolCategory.WEB
    parameters = [
        ToolParameter(
            name="selector",
            type="string",
            description="要点击的元素CSS选择器",
            required=True,
        ),
        ToolParameter(
            name="session_id",
            type="string",
            description="浏览器会话ID",
            required=False,
        ),
    ]
    
    async def execute(
        self,
        selector: str,
        session_id: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        """执行点击并切换标签页操作"""
        try:
            session = session_manager.get_active_session(session_id)
            context = session.context
            page = session.page
            
            # 监听新页面事件
            async with context.expect_page() as new_page_info:
                await page.click(selector)
            
            new_page = await new_page_info.value
            
            # 更新会话的当前页面
            session._page = new_page
            
            return ToolResult(
                success=True,
                output=f"✅ 已打开新标签页并切换\n当前URL: {new_page.url}",
                data={"url": new_page.url},
            )
            
        except Exception as e:
            logger.error(f"切换标签页失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"切换标签页失败: {str(e)}",
            )


@tool
class PlaywrightSaveAsPdfTool(BaseTool):
    """保存为PDF"""
    
    name = "playwright_save_as_pdf"
    description = "Save current page as PDF file"
    category = ToolCategory.WEB
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="PDF保存路径",
            required=True,
        ),
        ToolParameter(
            name="session_id",
            type="string",
            description="浏览器会话ID",
            required=False,
        ),
        ToolParameter(
            name="format",
            type="string",
            description="纸张格式",
            required=False,
            default="A4",
            enum=["A4", "A3", "Letter", "Legal", "Tabloid"],
        ),
    ]
    
    async def execute(
        self,
        path: str,
        session_id: Optional[str] = None,
        format: str = "A4",
        **kwargs: Any,
    ) -> ToolResult:
        """执行保存PDF操作"""
        try:
            session = session_manager.get_active_session(session_id)
            page = session.page
            
            await page.pdf(path=path, format=format)
            
            return ToolResult(
                success=True,
                output=f"✅ 页面已保存为PDF: {path}",
                data={"path": path, "format": format},
            )
            
        except Exception as e:
            logger.error(f"保存PDF失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"保存PDF失败: {str(e)}",
            )


# ==================== 代理和自定义功能工具 ====================

@tool
class PlaywrightCustomUserAgentTool(BaseTool):
    """设置自定义User-Agent"""
    
    name = "playwright_custom_user_agent"
    description = "Set custom User-Agent string for browser"
    category = ToolCategory.WEB
    parameters = [
        ToolParameter(
            name="user_agent",
            type="string",
            description="自定义的User-Agent字符串",
            required=True,
        ),
        ToolParameter(
            name="session_id",
            type="string",
            description="浏览器会话ID",
            required=False,
        ),
    ]
    
    async def execute(
        self,
        user_agent: str,
        session_id: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        """执行设置User-Agent操作"""
        try:
            session = session_manager.get_active_session(session_id)
            
            # 需要创建新的上下文来设置User-Agent
            old_context = session._context
            old_page = session._page
            
            # 创建新上下文
            session._context = await session._browser.new_context(
                user_agent=user_agent,
                viewport={
                    "width": session.viewport_width,
                    "height": session.viewport_height,
                },
            )
            
            # 创建新页面
            session._page = await session._context.new_page()
            
            # 关闭旧的上下文
            if old_page:
                await old_page.close()
            if old_context:
                await old_context.close()
            
            return ToolResult(
                success=True,
                output=f"✅ User-Agent 已设置为: {user_agent}",
                data={"user_agent": user_agent},
            )
            
        except Exception as e:
            logger.error(f"设置User-Agent失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"设置User-Agent失败: {str(e)}",
            )


@tool
class PlaywrightConsoleLogsTool(BaseTool):
    """获取控制台日志"""
    
    name = "playwright_console_logs"
    description = "Get browser console log output"
    category = ToolCategory.WEB
    parameters = [
        ToolParameter(
            name="session_id",
            type="string",
            description="浏览器会话ID",
            required=False,
        ),
        ToolParameter(
            name="clear",
            type="boolean",
            description="获取后是否清空日志",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="filter_type",
            type="string",
            description="过滤日志类型",
            required=False,
            enum=["all", "log", "warn", "error", "info"],
        ),
    ]
    
    async def execute(
        self,
        session_id: Optional[str] = None,
        clear: bool = False,
        filter_type: str = "all",
        **kwargs: Any,
    ) -> ToolResult:
        """执行获取控制台日志操作"""
        try:
            session = session_manager.get_active_session(session_id)
            
            logs = session.get_console_logs(clear=clear)
            
            # 过滤日志类型
            if filter_type != "all":
                logs = [log for log in logs if log["type"] == filter_type]
            
            if not logs:
                return ToolResult(
                    success=True,
                    output="控制台暂无日志",
                    data={"logs": []},
                )
            
            # 格式化输出
            output_lines = [f"控制台日志 (共 {len(logs)} 条):\n"]
            for log in logs[-50:]:  # 只显示最近50条
                output_lines.append(f"[{log['type'].upper()}] {log['text']}")
            
            return ToolResult(
                success=True,
                output="\n".join(output_lines),
                data={"logs": logs, "count": len(logs)},
            )
            
        except Exception as e:
            logger.error(f"获取控制台日志失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"获取控制台日志失败: {str(e)}",
            )
