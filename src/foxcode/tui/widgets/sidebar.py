"""Sidebar - 1:1 port of doge-code session sidebar with sessions list."""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.containers import Vertical
from textual.widgets import Button, ListItem, ListView, Static

from foxcode.tui.icons import ICONS
from foxcode.tui.theme import get_theme


class Sidebar(Vertical):
    """Sidebar with sessions list and new-session button."""

    def compose(self):
        yield Static("SESSIONS", classes="section")
        self.new_btn = Button("+  new session", id="new-session")
        yield self.new_btn
        self.sessions: ListView = ListView(id="sessions")
        yield self.sessions

    def refresh_sessions(self, sessions: list[dict[str, Any]], current_id: str):
        items: list[ListItem] = []
        for s in sessions[:20]:
            sid = s.get("session_id", "?")
            name = s.get("name")
            created = str(s.get("created_at", ""))[:16]
            msgs = s.get("message_count", 0)
            label = Text()
            label.append((name or sid)[:22], style="bold")
            label.append("\n")
            label.append(f"{created} {ICONS.middle_dot} {msgs} msg", style="dim")
            item = ListItem(Static(label, markup=False))
            item.data_sid = sid
            if sid == current_id:
                item.add_class("--highlight")
            items.append(item)
        self.sessions.clear()
        if items:
            self.sessions.extend(items)
