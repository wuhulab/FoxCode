"""ThemedBox - Theme-aware container wrapper."""

from __future__ import annotations

from textual.containers import Vertical

from foxcode.tui.theme import get_theme


class ThemedBox(Vertical):
    """A themed container that applies background from theme."""

    def __init__(self, theme_key: str = "background", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._theme_key = theme_key

    def on_mount(self):
        theme = get_theme()
        color = getattr(theme, self._theme_key, "#0d1117")
        self.styles.background = color
