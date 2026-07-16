"""Sidebar - 1:1 port of doge-code session sidebar with sessions list."""

from __future__ import annotations

import asyncio
from typing import Any

from rich.text import Text
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Button, Static

from foxcode.tui.icons import ICONS
from foxcode.tui.theme import get_theme


class SessionRow(Static):
    """A single session row (name + meta + right-aligned \u22ee menu trigger)."""

    DEFAULT_CSS = """
    SessionRow {
        height: auto;
        background: transparent;
        color: #e6edf3;
        padding: 0 1;
    }
    SessionRow.--highlight {
        background: #1c2128;
        color: #ffd56b;
    }
    SessionRow:hover {
        background: #161b22;
    }
    """

    class Selected(Message):
        """Dispatched when the user clicks the body of the row (load session)."""

        def __init__(self, sid: str) -> None:
            self.sid = sid
            super().__init__()

    class MenuClicked(Message):
        """Dispatched when the user clicks the \u22ee menu button."""

        def __init__(self, sid: str, x: int, y: int) -> None:
            self.sid = sid
            self.x = x
            self.y = y
            super().__init__()

    def __init__(
        self,
        sid: str,
        name: str | None,
        created_at: str,
        msg_count: int,
        highlight: bool = False,
        **kwargs,
    ):
        super().__init__(markup=False, **kwargs)
        self.sid = sid
        self._name = name
        self._created = created_at
        self._msg_count = msg_count
        if highlight:
            self.add_class("--highlight")

    def render(self):
        text = Text()
        text.append((self._name or self.sid)[:22], style="bold")
        text.append("  \u22ee\n")
        text.append(
            f"{self._created} {ICONS.middle_dot} {self._msg_count} msg", style="dim"
        )
        return text

    def on_click(self, event):
        # The \u22ee occupies the last ~3 columns of the first line.
        # event.offset is relative to this widget.
        if event.offset.x >= max(1, self.content_size.width - 3):
            self.post_message(
                self.MenuClicked(self.sid, int(event.screen_x), int(event.screen_y))
            )
        else:
            self.post_message(self.Selected(self.sid))
        event.stop()


class Sidebar(Vertical):
    """Sidebar with sessions list and new-session button."""

    def compose(self):
        yield Static("SESSIONS", classes="section")
        self.new_btn = Button("+  new session", id="new-session")
        yield self.new_btn
        self.sessions: VerticalScroll = VerticalScroll(id="sessions")
        yield self.sessions

    def refresh_sessions(self, sessions: list[dict[str, Any]], current_id: str):
        async def _do():
            await self.sessions.remove_children()
            rows: list[SessionRow] = []
            for s in sessions[:20]:
                sid = s.get("session_id", "?")
                rows.append(
                    SessionRow(
                        sid=sid,
                        name=s.get("name"),
                        created_at=str(s.get("created_at", ""))[:16],
                        msg_count=s.get("message_count", 0),
                        highlight=(sid == current_id),
                    )
                )
            if rows:
                await self.sessions.mount(*rows)

        asyncio.create_task(_do())
