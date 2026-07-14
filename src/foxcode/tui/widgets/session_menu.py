"""SessionMenu - floating right-click menu for a history session entry."""

from __future__ import annotations

from textual import on
from textual.widgets import OptionList


class SessionMenu(OptionList):
    """A small floating menu (重命名 / 删除) anchored at the cursor."""

    BINDINGS = [
        ("escape", "dismiss_menu", "Close"),
    ]

    def __init__(self, sid: str, x: int, y: int, on_pick, **kwargs):
        super().__init__("重命名", "删除", **kwargs)
        self.sid = sid
        self._x = x
        self._y = y
        self._on_pick = on_pick

    def on_mount(self):
        self.styles.position = "absolute"
        self.styles.offset = (self._x, self._y)
        self.styles.background = "#161b22"
        self.styles.border = ("round", "#ffd56b")
        self.styles.min_width = 16
        self.focus()

    def action_dismiss_menu(self):
        self.remove()

    @on(OptionList.OptionSelected)
    def _pick(self, event: OptionList.OptionSelected):
        self._on_pick(str(event.option.prompt))
        self.remove()
