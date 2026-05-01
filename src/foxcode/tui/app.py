"""
FoxCode TUI 终端应用

提供现代化的终端交互界面，支持：
- 对话界面：与 AI 进行交互式对话
- 任务管理界面：显示和管理任务列表
- 配置界面：可视化配置管理
- 日志查看器：实时查看系统日志

使用方法：
    from foxcode.tui.app import run_app
    run_app()
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

try:
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal, Vertical
    from textual.widgets import (
        Header, Footer, Static, Input, Button, 
        ListView, ListItem, Label, RichLog
    )
    from textual.binding import Binding
    from textual.reactive import reactive
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    App = object
    ComposeResult = Any

from foxcode.core.agent import Agent
from foxcode.core.config import Config
from foxcode.core.session import SessionManager
from foxcode.types.message import Message, MessageRole


logger = logging.getLogger(__name__)


class ChatMessage(Static if TEXTUAL_AVAILABLE else object):
    """单条聊天消息组件"""
    
    def __init__(self, message: Message, **kwargs):
        super().__init__(**kwargs)
        self.message = message
    
    def compose(self) -> ComposeResult:
        if not TEXTUAL_AVAILABLE:
            return
        
        role = self.message.role.value
        content = self.message.content
        
        role_style = {
            "user": "bold blue",
            "assistant": "bold green",
            "system": "bold yellow"
        }.get(role, "bold white")
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        yield Static(
            f"[{timestamp}] [{role_style}]{role.upper()}[/]: {content}",
            classes=f"message message-{role}"
        )


class ChatPanel(Container if TEXTUAL_AVAILABLE else object):
    """聊天面板组件"""
    
    messages: reactive[List[Message]] = reactive(default_factory=list)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.message_widgets: List[ChatMessage] = []
    
    def compose(self) -> ComposeResult:
        if not TEXTUAL_AVAILABLE:
            return
        
        yield Label("💬 对话", classes="panel-title")
        yield ListView(id="message-list")
    
    def add_message(self, message: Message) -> None:
        """添加新消息到聊天面板"""
        self.messages.append(message)
        
        if TEXTUAL_AVAILABLE:
            try:
                message_list = self.query_one("#message-list", ListView)
                chat_msg = ChatMessage(message)
                message_list.append(ListItem(chat_msg))
                message_list.scroll_end()
            except Exception as e:
                logger.error(f"添加消息失败: {e}")
    
    def clear_messages(self) -> None:
        """清空所有消息"""
        self.messages.clear()
        
        if TEXTUAL_AVAILABLE:
            try:
                message_list = self.query_one("#message-list", ListView)
                message_list.clear()
            except Exception as e:
                logger.error(f"清空消息失败: {e}")


class TaskPanel(Container if TEXTUAL_AVAILABLE else object):
    """任务面板组件"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tasks: List[Dict[str, Any]] = []
    
    def compose(self) -> ComposeResult:
        if not TEXTUAL_AVAILABLE:
            return
        
        yield Label("📋 任务列表", classes="panel-title")
        yield ListView(id="task-list")
    
    def add_task(self, task_id: str, content: str, priority: str = "medium") -> None:
        """添加新任务"""
        task = {
            "id": task_id,
            "content": content,
            "priority": priority,
            "status": "pending",
            "created_at": datetime.now()
        }
        self.tasks.append(task)
        self._refresh_task_list()
    
    def update_task_status(self, task_id: str, status: str) -> None:
        """更新任务状态"""
        for task in self.tasks:
            if task["id"] == task_id:
                task["status"] = status
                break
        self._refresh_task_list()
    
    def _refresh_task_list(self) -> None:
        """刷新任务列表显示"""
        if not TEXTUAL_AVAILABLE:
            return
        
        try:
            task_list = self.query_one("#task-list", ListView)
            task_list.clear()
            
            for task in self.tasks:
                status_icon = {
                    "pending": "⏳",
                    "in_progress": "🔄",
                    "completed": "✅"
                }.get(task["status"], "❓")
                
                priority_style = {
                    "high": "red",
                    "medium": "yellow",
                    "low": "green"
                }.get(task["priority"], "white")
                
                item = ListItem(Label(
                    f"{status_icon} [{priority_style}]{task['content']}[/]"
                ))
                task_list.append(item)
        except Exception as e:
            logger.error(f"刷新任务列表失败: {e}")


class InputPanel(Container if TEXTUAL_AVAILABLE else object):
    """输入面板组件"""
    
    def __init__(self, on_submit: Optional[callable] = None, **kwargs):
        super().__init__(**kwargs)
        self.on_submit = on_submit
    
    def compose(self) -> ComposeResult:
        if not TEXTUAL_AVAILABLE:
            return
        
        yield Label("✏️ 输入", classes="panel-title")
        yield Input(placeholder="输入消息或命令...", id="user-input")
        yield Button("发送", id="send-button", variant="primary")
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """处理输入提交事件"""
        if self.on_submit and event.value.strip():
            self.on_submit(event.value)
            event.input.value = ""
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """处理按钮点击事件"""
        if event.button.id == "send-button":
            try:
                input_widget = self.query_one("#user-input", Input)
                if input_widget.value.strip() and self.on_submit:
                    self.on_submit(input_widget.value)
                    input_widget.value = ""
            except Exception as e:
                logger.error(f"发送消息失败: {e}")


class LogPanel(Container if TEXTUAL_AVAILABLE else object):
    """日志面板组件"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def compose(self) -> ComposeResult:
        if not TEXTUAL_AVAILABLE:
            return
        
        yield Label("📜 系统日志", classes="panel-title")
        yield RichLog(id="log-viewer", highlight=True, markup=True)
    
    def log(self, message: str, level: str = "info") -> None:
        """添加日志条目"""
        if not TEXTUAL_AVAILABLE:
            return
        
        try:
            log_viewer = self.query_one("#log-viewer", RichLog)
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            level_style = {
                "debug": "dim",
                "info": "white",
                "warning": "yellow",
                "error": "red"
            }.get(level, "white")
            
            log_viewer.write(f"[{timestamp}] [{level_style}]{level.upper()}[/]: {message}")
        except Exception as e:
            logger.error(f"添加日志失败: {e}")


class FoxCodeApp(App if TEXTUAL_AVAILABLE else object):
    """
    FoxCode TUI 主应用
    
    提供现代化的终端交互界面，包括：
    - 左侧：聊天面板和输入面板
    - 右侧：任务面板和日志面板
    - 顶部：标题栏
    - 底部：状态栏和快捷键提示
    """
    
    CSS = """
    .panel-title {
        text-style: bold;
        padding: 1;
        background: $primary;
        color: $text;
    }
    
    .message {
        padding: 1;
        margin: 1;
    }
    
    .message-user {
        background: $primary-darken-2;
    }
    
    .message-assistant {
        background: $success-darken-2;
    }
    
    .message-system {
        background: $warning-darken-2;
    }
    
    #user-input {
        margin: 1;
    }
    
    #send-button {
        margin: 1;
    }
    
    Screen {
        layout: grid;
        grid-size: 2 2;
        grid-columns: 2fr 1fr;
        grid-rows: 1fr auto;
    }
    
    ChatPanel {
        column-span: 1;
        row-span: 1;
    }
    
    TaskPanel {
        column-span: 1;
        row-span: 1;
    }
    
    InputPanel {
        column-span: 1;
        row-span: 1;
    }
    
    LogPanel {
        column-span: 1;
        row-span: 1;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+q", "quit", "退出"),
        Binding("ctrl+c", "quit", "退出"),
        Binding("ctrl+l", "clear_chat", "清空对话"),
        Binding("ctrl+s", "save_session", "保存会话"),
        Binding("ctrl+h", "toggle_help", "帮助"),
        Binding("tab", "focus_next", "下一个"),
        Binding("shift+tab", "focus_previous", "上一个"),
    ]
    
    TITLE = "FoxCode - AI 编码助手"
    
    def __init__(
        self,
        config: Optional[Config] = None,
        agent: Optional[Agent] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.config = config or Config()
        self.agent = agent
        self.session_manager: Optional[SessionManager] = None
        self._is_processing = False
    
    def compose(self) -> ComposeResult:
        """构建应用界面"""
        if not TEXTUAL_AVAILABLE:
            return
        
        yield Header()
        yield ChatPanel()
        yield TaskPanel()
        yield InputPanel(on_submit=self.handle_user_input)
        yield LogPanel()
        yield Footer()
    
    async def on_mount(self) -> None:
        """应用挂载时初始化"""
        if not TEXTUAL_AVAILABLE:
            return
        
        self._log("FoxCode TUI 应用启动")
        
        if not self.agent:
            try:
                self.agent = Agent(self.config)
                self._log("AI 代理初始化成功")
            except Exception as e:
                self._log(f"AI 代理初始化失败: {e}", "error")
        
        self.session_manager = SessionManager(self.config)
        self._log("会话管理器初始化完成")
        
        self._add_welcome_message()
    
    def _add_welcome_message(self) -> None:
        """添加欢迎消息"""
        welcome_text = (
            "欢迎使用 FoxCode AI 编码助手！\n\n"
            "快捷键:\n"
            "  Ctrl+Q - 退出应用\n"
            "  Ctrl+L - 清空对话\n"
            "  Ctrl+S - 保存会话\n"
            "  Ctrl+H - 显示帮助\n"
            "  Tab    - 切换焦点\n\n"
            "输入消息开始对话，或使用 /help 查看可用命令。"
        )
        
        if TEXTUAL_AVAILABLE:
            try:
                chat_panel = self.query_one(ChatPanel)
                chat_panel.add_message(Message(
                    role=MessageRole.SYSTEM,
                    content=welcome_text
                ))
            except Exception as e:
                logger.error(f"添加欢迎消息失败: {e}")
    
    async def handle_user_input(self, text: str) -> None:
        """处理用户输入"""
        if self._is_processing or not text.strip():
            return
        
        self._is_processing = True
        self._log(f"用户输入: {text[:50]}...")
        
        try:
            if TEXTUAL_AVAILABLE:
                chat_panel = self.query_one(ChatPanel)
                chat_panel.add_message(Message(
                    role=MessageRole.USER,
                    content=text
                ))
            
            if text.startswith("/"):
                await self._handle_command(text)
            else:
                await self._handle_chat(text)
        except Exception as e:
            self._log(f"处理输入失败: {e}", "error")
        finally:
            self._is_processing = False
    
    async def _handle_command(self, command: str) -> None:
        """处理命令"""
        cmd = command.lower().strip()
        
        if cmd == "/help":
            help_text = self._get_help_text()
            if TEXTUAL_AVAILABLE:
                chat_panel = self.query_one(ChatPanel)
                chat_panel.add_message(Message(
                    role=MessageRole.SYSTEM,
                    content=help_text
                ))
        elif cmd == "/clear":
            self.action_clear_chat()
        elif cmd == "/save":
            self.action_save_session()
        else:
            self._log(f"未知命令: {command}", "warning")
    
    async def _handle_chat(self, text: str) -> None:
        """处理聊天消息"""
        if not self.agent:
            self._log("AI 代理未初始化", "error")
            return
        
        try:
            self._log("正在生成回复...")
            
            response = await self.agent.chat(text)
            
            if TEXTUAL_AVAILABLE:
                chat_panel = self.query_one(ChatPanel)
                chat_panel.add_message(Message(
                    role=MessageRole.ASSISTANT,
                    content=response
                ))
            
            self._log("回复生成完成")
        except Exception as e:
            self._log(f"生成回复失败: {e}", "error")
    
    def _get_help_text(self) -> str:
        """获取帮助文本"""
        return (
            "可用命令:\n\n"
            "/help    - 显示此帮助信息\n"
            "/clear   - 清空对话历史\n"
            "/save    - 保存当前会话\n"
            "/quit    - 退出应用\n\n"
            "快捷键:\n\n"
            "Ctrl+Q   - 退出应用\n"
            "Ctrl+L   - 清空对话\n"
            "Ctrl+S   - 保存会话\n"
            "Ctrl+H   - 显示帮助\n"
            "Tab      - 切换焦点\n"
        )
    
    def action_clear_chat(self) -> None:
        """清空对话"""
        if TEXTUAL_AVAILABLE:
            try:
                chat_panel = self.query_one(ChatPanel)
                chat_panel.clear_messages()
                self._log("对话已清空")
            except Exception as e:
                self._log(f"清空对话失败: {e}", "error")
    
    def action_save_session(self) -> None:
        """保存会话"""
        if not self.session_manager:
            self._log("会话管理器未初始化", "error")
            return
        
        try:
            if TEXTUAL_AVAILABLE:
                chat_panel = self.query_one(ChatPanel)
                messages = chat_panel.messages
                
                self.session_manager.save_session(messages)
                self._log("会话已保存")
        except Exception as e:
            self._log(f"保存会话失败: {e}", "error")
    
    def action_toggle_help(self) -> None:
        """切换帮助显示"""
        help_text = self._get_help_text()
        if TEXTUAL_AVAILABLE:
            try:
                chat_panel = self.query_one(ChatPanel)
                chat_panel.add_message(Message(
                    role=MessageRole.SYSTEM,
                    content=help_text
                ))
            except Exception as e:
                logger.error(f"显示帮助失败: {e}")
    
    def _log(self, message: str, level: str = "info") -> None:
        """添加日志"""
        logger.log(getattr(logging, level.upper(), logging.INFO), message)
        
        if TEXTUAL_AVAILABLE:
            try:
                log_panel = self.query_one(LogPanel)
                log_panel.log(message, level)
            except Exception:
                pass
    
    def add_task(self, task_id: str, content: str, priority: str = "medium") -> None:
        """添加任务到任务面板"""
        if TEXTUAL_AVAILABLE:
            try:
                task_panel = self.query_one(TaskPanel)
                task_panel.add_task(task_id, content, priority)
                self._log(f"任务已添加: {content[:30]}...")
            except Exception as e:
                self._log(f"添加任务失败: {e}", "error")
    
    def update_task_status(self, task_id: str, status: str) -> None:
        """更新任务状态"""
        if TEXTUAL_AVAILABLE:
            try:
                task_panel = self.query_one(TaskPanel)
                task_panel.update_task_status(task_id, status)
                self._log(f"任务状态已更新: {task_id} -> {status}")
            except Exception as e:
                self._log(f"更新任务状态失败: {e}", "error")


def run_app(config: Optional[Config] = None, agent: Optional[Agent] = None) -> None:
    """
    运行 FoxCode TUI 应用
    
    参数:
        config: 配置对象，如果未提供则使用默认配置
        agent: AI 代理对象，如果未提供则自动创建
    
    使用方法:
        from foxcode.tui import run_app
        from foxcode.core.config import Config
        
        config = Config()
        run_app(config)
    """
    if not TEXTUAL_AVAILABLE:
        print("错误: 需要安装 textual 库才能使用 TUI 界面")
        print("请运行: pip install textual")
        return
    
    try:
        app = FoxCodeApp(config=config, agent=agent)
        app.run()
    except Exception as e:
        logger.error(f"运行 TUI 应用失败: {e}")
        print(f"错误: 运行 TUI 应用失败 - {e}")


if __name__ == "__main__":
    run_app()
