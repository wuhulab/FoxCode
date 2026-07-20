"""FoxCode PySide Desktop GUI - 主窗口"""
import logging
import sys
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QApplication, QSizePolicy,
)
from PySide6.QtCore import Qt, QSize, Signal, Slot, QThread, QObject
from PySide6.QtGui import QFont, QIcon

from foxcode.pyside_gui.theme import GLOBAL_STYLESHEET, BG_PRIMARY, BORDER
from foxcode.pyside_gui.widgets.toolbar import Toolbar
from foxcode.pyside_gui.widgets.project_bar import ProjectBar
from foxcode.pyside_gui.widgets.session_panel import SessionPanel
from foxcode.pyside_gui.widgets.chat_area import ChatArea
from foxcode.pyside_gui.widgets.input_bar import InputBar


class AgentWorker(QObject):
    """在后台线程中运行 FoxCodeAgent 的异步聊天。"""

    finished = Signal(str)   # 完整回复文本
    chunk = Signal(str)      # 流式片段（暂留接口）
    error = Signal(str)

    def __init__(self, agent, prompt: str, parent=None):
        super().__init__(parent)
        self._agent = agent
        self._prompt = prompt

    @Slot()
    def run(self):
        """在 QThread 中执行，用新事件循环驱动异步 agent.chat。"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self._run_chat())
            self.finished.emit(result)
        except Exception as exc:
            logger.warning(f"聊天线程异常: {exc}", exc_info=True)
            self.error.emit(str(exc))
        finally:
            loop.close()

    async def _run_chat(self) -> str:
        full_reply = ""
        async for event in self._agent.chat(self._prompt):
            if hasattr(event, "text"):
                full_reply += event.text
                self.chunk.emit(event.text)
            elif isinstance(event, str):
                full_reply += event
                self.chunk.emit(event)
        return full_reply


class MainWindow(QMainWindow):
    """FoxCode 桌面客户端主窗口 —— Codex 风格纯白配色。"""

    def __init__(self, agent=None, parent=None):
        super().__init__(parent)
        self._agent = agent
        self._worker_thread: Optional[QThread] = None

        self._setup_window()
        self._build_ui()
        self._connect_signals()

    # ── 窗口基础 ────────────────────────────────────────
    def _setup_window(self):
        self.setWindowTitle("FoxCode")
        self.setMinimumSize(QSize(960, 640))
        self.resize(1280, 800)
        self.setStyleSheet(GLOBAL_STYLESHEET)
        # 无边框窗口（自定义标题栏）
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
        )

    # ── 构建 UI ─────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1) 顶部工具栏
        self._toolbar = Toolbar()
        root_layout.addWidget(self._toolbar)

        # 2) 主体区域 = 项目栏 + 会话面板 + 聊天区
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # 2a) 项目图标栏（最左）
        self._project_bar = ProjectBar()
        body_layout.addWidget(self._project_bar)

        # 2b) 会话列表
        self._session_panel = SessionPanel()
        body_layout.addWidget(self._session_panel)

        # 分隔线
        sep = QWidget()
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background-color: {BORDER};")
        body_layout.addWidget(sep)

        # 2c) 聊天 + 输入区（右侧主体）
        chat_container = QWidget()
        chat_layout = QVBoxLayout(chat_container)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)

        self._chat_area = ChatArea()
        chat_layout.addWidget(self._chat_area, stretch=1)

        self._input_bar = InputBar()
        chat_layout.addWidget(self._input_bar)

        body_layout.addWidget(chat_container, stretch=1)

        root_layout.addWidget(body, stretch=1)

    # ── 信号连接 ────────────────────────────────────────
    def _connect_signals(self):
        # 窗口控制
        self._toolbar.minimize_clicked.connect(self.showMinimized)
        self._toolbar.maximize_clicked.connect(self._toggle_maximize)
        self._toolbar.close_clicked.connect(self.close)

        # 会话
        self._session_panel.new_chat_requested.connect(self._on_new_chat)
        self._session_panel.session_selected.connect(self._on_session_selected)

        # 消息发送
        self._input_bar.message_submitted.connect(self._on_send_message)

    # ── 事件处理 ────────────────────────────────────────
    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _on_new_chat(self):
        self._chat_area.clear_messages()

    def _on_session_selected(self, index: int):
        # TODO: 加载对应会话的消息历史
        pass

    @Slot(str)
    def _on_send_message(self, text: str):
        """用户发送消息。"""
        # 显示用户消息
        self._chat_area.add_message(text, is_user=True)
        self._input_bar.set_enabled(False)

        if self._agent is not None:
            self._run_agent(text)
        else:
            # 没有 agent 时显示提示
            self._chat_area.add_message(
                "[Agent 未初始化] 请通过 foxcode --pyside 启动以连接 AI 后端。",
                is_user=False,
            )
            self._input_bar.set_enabled(True)
            self._input_bar.focus_input()

    def _run_agent(self, prompt: str):
        """在后台线程中调用 agent.chat 并将结果显示在聊天区。"""
        self._worker_thread = QThread()
        worker = AgentWorker(self._agent, prompt)
        worker.moveToThread(self._worker_thread)

        self._worker_thread.started.connect(worker.run)
        worker.finished.connect(self._on_agent_reply)
        worker.error.connect(self._on_agent_error)
        worker.finished.connect(self._worker_thread.quit)
        worker.error.connect(self._worker_thread.quit)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)

        # prevent GC
        self._current_worker = worker
        self._worker_thread.start()

    @Slot(str)
    def _on_agent_reply(self, reply: str):
        self._chat_area.add_message(reply, is_user=False)
        self._input_bar.set_enabled(True)
        self._input_bar.focus_input()

    @Slot(str)
    def _on_agent_error(self, error_msg: str):
        self._chat_area.add_message(f"⚠ 错误: {error_msg}", is_user=False)
        self._input_bar.set_enabled(True)
        self._input_bar.focus_input()
