"""VirtualMessageList - Virtualized scrollable message list.

Ported from doge-code's VirtualMessageList with useVirtualScroll.
"""

from __future__ import annotations

from typing import Callable

from textual.containers import VerticalScroll
from textual.widgets import Static

from foxcode.tui.theme import get_theme
from foxcode.tui.widgets.message import MessageWidget


class VirtualMessageList(VerticalScroll):
    """Scrollable container for chat messages with virtual rendering."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._messages: list[MessageWidget] = []

    @property
    def messages(self) -> list[MessageWidget]:
        return self._messages

    def add_message(self, msg: MessageWidget):
        self._messages.append(msg)
        self.mount(msg)
        # The scrollable height is only correct after the layout has fully
        # settled. Retry scroll_end across a few refreshes so it lands at the
        # bottom once the container is constrained.
        self._scroll_to_bottom()

    def on_resize(self, event=None) -> None:
        self._scroll_to_bottom()

    def _scroll_to_bottom(self, depth: int = 0) -> None:
        self.scroll_end(animate=False)
        if depth < 12:
            self.app.call_after_refresh(lambda: self._scroll_to_bottom(depth + 1))

    def clear_messages(self):
        self.remove_children()
        self._messages.clear()

    def remove_last(self):
        if self._messages:
            last = self._messages.pop()
            if last in self.children:
                self.remove(last)

    def replay_messages(self, messages: list[MessageWidget]):
        self.clear_messages()
        for msg in messages:
            self.mount(msg)
            self._messages.append(msg)
        self.app.call_after_refresh(self.scroll_end, animate=False)


class SearchBar(Static):
    """Inline search bar for message search."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._query = ""
        self._match_count = 0
        self._current_match = 0

    def set_query(self, query: str, matches: int = 0, current: int = 0):
        self._query = query
        self._match_count = matches
        self._current_match = current
        self.refresh()

    def render(self):
        if not self._query:
            return ""
        match_display = f"({self._current_match + 1}/{self._match_count})" if self._match_count > 0 else "(no matches)"
        return f"Search: {self._query}  {match_display}"
