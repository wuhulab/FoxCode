"""MessageResponse - 1:1 port of doge-code message rendering.

Each message has a role label, markdown body, and the ⎿ response indent marker.
"""

from __future__ import annotations

import re

from rich.markdown import Markdown
from rich.panel import Panel
from rich.style import Style
from rich.text import Text
from textual.widgets import Static, RichLog

from foxcode.tui.theme import get_theme
from foxcode.tui.icons import ICONS


ROLE_ICONS = {
    "user": ICONS.user,
    "assistant": ICONS.assistant,
    "tool": ICONS.tool,
    "system": ICONS.system,
}


class MessageWidget(Static):
    """A single chat message. Ported from doge-code's Message component."""

    can_focus = True

    def __init__(
        self,
        role: str,
        body: str = "",
        *,
        thinking: bool = False,
        message_color: str = "fox",
    ):
        self.role = role
        self._body = body
        self._thinking = thinking
        self._message_color = message_color
        self._is_response = role == "assistant" and not thinking
        super().__init__()

    def append_text(self, chunk: str):
        self._body += chunk
        self.refresh()

    def finalize(self):
        self._thinking = False
        self.refresh()

    @property
    def text_body(self) -> str:
        return self._body

    def render(self):
        theme = get_theme()
        lines = []

        role_style = Style(bold=True)
        if self.role == "user":
            role_color = getattr(theme, "briefLabelYou", "#79c0ff")
            role_style = Style(color=role_color, bold=True)
        elif self.role == "assistant":
            role_color = getattr(theme, self._message_color, "#ffd56b")
            role_style = Style(color=role_color, bold=True)
        elif self.role == "tool":
            role_style = Style(color=getattr(theme, "purple_FOR_SUBAGENTS_ONLY", "#a371f7"), bold=True)
        else:
            role_style = Style(color=getattr(theme, "inactive", "#7d8590"))

        icon = ROLE_ICONS.get(self.role, ICONS.middle_dot)
        role_line = Text(f"{icon} {self.role}", style=role_style)
        lines.append(role_line)

        if not self._body:
            lines.append(Text(""))
            return Text("\n").join(lines)

        if self._thinking:
            inactive = getattr(theme, "inactive", "#7d8590")
            lines.append(Text(self._body, style=Style(color=inactive, italic=True)))
        elif self.role in ("assistant", "tool"):
            # Render the full body verbatim. The agent embeds control tokens
            # like [say]/[tool]/[result] inside assistant/tool output; running
            # it through Markdown + from_markup would strip those tokens and
            # omit the model's spoken content and tool calls.
            lines.append(Text(self._body))
        else:
            lines.append(Text(self._body))

        return Text("\n").join(lines)


class ConfigPanelWidget(MessageWidget):
    """A system box rendered as a Rich Panel (used for config display)."""

    def __init__(self, panel_title: str, body: str, role: str = "system"):
        super().__init__(role, body)
        self._panel_title = panel_title

    def render(self):
        theme = get_theme()
        border = getattr(theme, "promptBorder", "#ffd56b")
        return Panel(
            self._body,
            title=self._panel_title,
            border_style=border,
            expand=False,
        )


class MessageResponse(RichLog):
    """Wrapper that renders assistant responses with indent marker.

    Ported from doge-code's MessageResponse (U+23BF bracket).
    """

    def __init__(self, body: str, height: int | None = None):
        super().__init__(highlight=True, markup=True)
        self._body = body
        self._response_height = height

    def on_mount(self):
        self._render_body()

    def _render_body(self):
        self.clear()
        lines = self._body.split("\n")
        theme = get_theme()
        dim = getattr(theme, "inactive", "#7d8590")

        for i, line in enumerate(lines):
            if i == 0:
                t = Text()
                t.append(f"  {ICONS.indent}  ", style=Style(color=dim))
                t.append(line)
                self.write(t)
            else:
                t = Text()
                t.append(f"     {line}")
                self.write(t)
