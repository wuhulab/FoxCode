"""ProgressBar - Animated progress bar, ported from doge-code."""

from __future__ import annotations

from rich.progress_bar import ProgressBar as RichProgressBar
from rich.style import Style
from textual.widgets import Static

from foxcode.tui.theme import get_theme


class ProgressBar(Static):
    """Theme-aware progress bar."""

    def __init__(self, progress: float = 0.0, total: float = 100.0, width: int = 40):
        super().__init__()
        self._progress = progress
        self._total = total
        self._bar_width = width

    def render(self):
        theme = get_theme()
        color = getattr(theme, "fox", "#ffd56b")
        empty_color = getattr(theme, "rate_limit_empty", "#30363d")
        ratio = self._progress / self._total if self._total > 0 else 0
        filled = round(ratio * self._bar_width)
        empty = self._bar_width - filled
        bar = "\u2588" * filled + "\u2591" * empty
        return Text(
            f"[{bar}] {self._progress:.0f}/{self._total:.0f}",
            style=Style(color=color),
        )
