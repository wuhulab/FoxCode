"""Tabs - Tab navigation widget, ported from doge-code Tabs component."""

from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual.containers import Horizontal
from textual.widgets import Static

from foxcode.tui.theme import get_theme


class FoxTab(Static):
    """A single tab."""

    def __init__(self, label: str, active: bool = False):
        super().__init__()
        self._label = label
        self._active = active

    def render(self):
        theme = get_theme()
        if self._active:
            color = getattr(theme, "fox", "#ffd56b")
            return Text(f" {self._label} ", style=Style(color=color, bold=True))
        color = getattr(theme, "inactive", "#7d8590")
        return Text(f" {self._label} ", style=Style(color=color))


class FoxTabs(Horizontal):
    """Horizontal tab bar."""

    def __init__(self, tabs: list[str], active: int = 0):
        super().__init__()
        self._tab_labels = tabs
        self._active = active

    def compose(self):
        for i, label in enumerate(self._tab_labels):
            yield FoxTab(label, active=(i == self._active))
