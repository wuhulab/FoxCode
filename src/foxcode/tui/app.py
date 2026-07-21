"""FoxCode TUI - Main Textual application.

1:1 port of doge-code's main App + REPL architecture.
Entry point: run_tui(agent, config)

Startup flow (port of doge-code bootstrap-entry.ts -> main.tsx -> replLauncher.tsx):
  1. run_tui() creates FoxCodeApp
  2. app.run() starts the Textual event loop
  3. on_mount() shows WelcomeScreen, then transitions to REPLScreen
"""

from __future__ import annotations

import sys
from typing import Optional

from textual.app import App
from textual.binding import Binding

from foxcode.tui.screens.repl import REPLScreen
from foxcode.tui.screens.welcome import WelcomeScreen
from foxcode.tui.theme import get_theme
from foxcode.utils.error_logger import log_exception
import logging

logger = logging.getLogger(__name__)


def _ensure_utf8():
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            logger.warning("设置 stdout 编码为 UTF-8 失败", exc_info=True)
            pass
        try:
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            logger.warning("设置 stderr 编码为 UTF-8 失败", exc_info=True)
            pass


class FoxCodeApp(App):
    """The FoxCode Textual terminal UI.

    Architecture mirrors doge-code's App.tsx provider stack:
    ThemeProvider -> AppState -> REPL
    """

    CSS_PATH = "styles.tcss"
    TITLE = "FoxCode"
    SUB_TITLE = ""

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
    ]

    def __init__(self, agent=None, config=None):
        super().__init__()
        self.agent = agent
        self.config = config
        self._repl: REPLScreen | None = None

    def on_mount(self):
        """Show welcome screen first (unless disabled), then transition to REPL."""
        theme = get_theme()
        self.styles.background = getattr(theme, "background", "#0d1117")

        # 检查配置是否禁用了欢迎界面
        show_welcome = True
        if self.config is not None and hasattr(self.config, "tui"):
            show_welcome = getattr(self.config.tui, "welcome_enabled", True)

        if not show_welcome:
            self._show_repl()
            return

        def _on_welcome_dismiss(result=None):
            self._show_repl()

        self.push_screen(WelcomeScreen(), _on_welcome_dismiss)

    def _show_repl(self):
        self._repl = REPLScreen(agent=self.agent, config=self.config)
        self.push_screen(self._repl)

    def on_exception(self, exc: Exception) -> bool:
        log_exception(type(exc), exc, exc.__traceback__, context="tui_app")
        logger.error("TUI App 未处理异常", exc_info=exc)
        return False

    def action_quit(self):
        self.exit()


def run_tui(agent=None, config=None) -> None:
    """Launch the FoxCode TUI.

    Args:
        agent: Optional FoxCodeAgent instance.
        config: Optional config instance.

    Usage:
        from foxcode.tui import run_tui
        run_tui()
    """
    import logging

    _ensure_utf8()

    # 抑制终端日志输出，避免破坏 TUI 界面
    # 文件日志 handler 仍正常工作，终端输出在 TUI 关闭后自动恢复
    _tui_old_log_level = None
    try:
        from foxcode.cli import _stream_handler as _cli_stream
        _tui_old_log_level = _cli_stream.level
        _cli_stream.setLevel(logging.CRITICAL + 1)
    except Exception:
        logger.warning("获取 CLI stream handler 失败", exc_info=True)
        _cli_stream = None
        _tui_old_log_level = None

    try:
        app = FoxCodeApp(agent=agent, config=config)
        app.run()
    finally:
        if _cli_stream is not None and _tui_old_log_level is not None:
            try:
                _cli_stream.setLevel(_tui_old_log_level)
            except Exception:
                logger.warning("恢复 CLI stream 日志级别失败", exc_info=True)
                pass
