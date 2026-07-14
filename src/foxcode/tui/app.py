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


def _ensure_utf8():
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
        try:
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
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
        """Show welcome screen first, then transition to REPL."""
        theme = get_theme()
        self.styles.background = getattr(theme, "background", "#0d1117")

        def _on_welcome_dismiss(result=None):
            self._show_repl()

        self.push_screen(WelcomeScreen(), _on_welcome_dismiss)

    def _show_repl(self):
        self._repl = REPLScreen(agent=self.agent, config=self.config)
        self.push_screen(self._repl)

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
    _ensure_utf8()
    app = FoxCodeApp(agent=agent, config=config)
    app.run()
