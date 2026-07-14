"""DiffViewer - Colorized diff display, ported from doge-code diff components."""

from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual.containers import Vertical
from textual.widgets import Static

from foxcode.tui.theme import get_theme


class DiffViewer(Vertical):
    """Displays a unified diff with theme-aware colors."""

    def __init__(self, diff_text: str, filename: str = ""):
        super().__init__()
        self._diff_text = diff_text
        self._filename = filename

    def compose(self):
        theme = get_theme()
        added = getattr(theme, "diffAdded", "#3fb950")
        removed = getattr(theme, "diffRemoved", "#f85149")
        dim = getattr(theme, "inactive", "#7d8590")

        if self._filename:
            yield Static(self._filename, classes="diff-header")

        rendered = Text()
        for line in self._diff_text.split("\n"):
            if line.startswith("+"):
                rendered.append(line + "\n", style=Style(color=added))
            elif line.startswith("-"):
                rendered.append(line + "\n", style=Style(color=removed))
            elif line.startswith("@@"):
                rendered.append(line + "\n", style=Style(color=dim, italic=True))
            elif line.startswith("diff --git") or line.startswith("---") or line.startswith("+++"):
                rendered.append(line + "\n", style=Style(color=dim, bold=True))
            else:
                rendered.append(line + "\n")

        yield Static(rendered, markup=False)
