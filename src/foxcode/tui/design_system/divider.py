"""Divider - Horizontal divider line, ported from doge-code."""

from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual.widgets import Static

from foxcode.tui.icons import ICONS
from foxcode.tui.theme import get_theme


class Divider(Static):
    """Horizontal divider with theme-aware color."""

    def __init__(self, label: str = "", width: int | None = None):
        super().__init__()
        self._label = label
        self._divider_width = width

    def render(self):
        theme = get_theme()
        color = getattr(theme, "inactive", "#7d8590")
        label = self._label
        d = ICONS.divider
        if label:
            return Text(
                f"{d} {label} {d}",
                style=Style(color=color),
            )
        return Text(
            d * 80,
            style=Style(color=color),
        )
