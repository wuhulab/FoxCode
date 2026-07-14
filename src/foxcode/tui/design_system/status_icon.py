"""StatusIcon - Status indicator icons, ported from doge-code."""

from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual.widgets import Static

from foxcode.tui.icons import ICONS as I
from foxcode.tui.theme import get_theme


STATUS_ICON_MAP = {
    "success": I.success,
    "error": I.error,
    "warning": I.warning,
    "info": I.info,
    "dot": I.bullet,
    "spinner": I.dot,
}


class StatusIcon(Static):
    """A status icon (checkmark, error, warning, etc)."""

    def __init__(self, status: str = "dot"):
        super().__init__()
        self._status = status

    def render(self):
        theme = get_theme()
        color_map = {
            "success": getattr(theme, "success", "#3fb950"),
            "error": getattr(theme, "error", "#f85149"),
            "warning": getattr(theme, "warning", "#d29922"),
            "info": getattr(theme, "foxBlue", "#58a6ff"),
            "dot": getattr(theme, "inactive", "#7d8590"),
            "spinner": getattr(theme, "fox", "#ffd56b"),
        }
        icon = STATUS_ICON_MAP.get(self._status, I.bullet)
        color = color_map.get(self._status, "#7d8590")
        return Text(f" {icon} ", style=Style(color=color))
