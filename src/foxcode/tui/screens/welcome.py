"""WelcomeScreen - Full startup welcome screen.

Ported from doge-code LogoV2 component.
"""

from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Static
from textual import work

from foxcode.tui.icons import ICONS
from foxcode.tui.theme import get_theme
from foxcode.tui.widgets.logo import WelcomeBanner


class WelcomeScreen(Screen):
    """Full-screen welcome shown on startup before entering REPL."""

    BINDINGS = [
        ("escape,enter,space", "dismiss", "Continue"),
    ]

    def compose(self):
        with Vertical(classes="welcome-screen"):
            yield WelcomeBanner(classes="welcome-art")
            yield Static(
                f"Press Enter or Space to continue{ICONS.ellipsis}",
                classes="welcome-hint",
            )

    def action_dismiss(self):
        self.dismiss()

    def on_mount(self):
        self.focus()
