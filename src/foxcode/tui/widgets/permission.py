"""PermissionDialog - Tool permission request dialog.

Ported from doge-code permission request components.
"""

from __future__ import annotations

from rich.text import Text
from textual.containers import Vertical
from textual.widgets import Button, Static

from foxcode.tui.theme import get_theme


class PermissionRequest(Vertical):
    """Permission approval dialog for tool calls."""

    def __init__(
        self,
        tool_name: str = "",
        description: str = "",
        args: dict | None = None,
    ):
        super().__init__()
        self._tool_name = tool_name
        self._description = description
        self._args = args or {}
        self._granted = False

    def compose(self):
        yield Static("Permission Request", classes="title")
        yield Static(f"Tool: {self._tool_name}", classes="tool-name")
        if self._description:
            yield Static(self._description)
        if self._args:
            args_text = Text()
            for k, v in self._args.items():
                args_text.append(f"  {k}: {v}\n")
            yield Static(args_text, markup=False)
        with Vertical(classes="dialog-actions"):
            self.allow_btn = Button("Allow", id="perm-allow", variant="primary")
            yield self.allow_btn
            self.deny_btn = Button("Deny", id="perm-deny")
            yield self.deny_btn
            yield Button("Always allow", id="perm-always")

    @property
    def granted(self) -> bool:
        return self._granted
