"""ConfigFormScreen - Interactive modal for editing config fields in the TUI.

Ported from the CLI's ``console.input`` based /openai and /shunxapi flows so
that those commands can be answered interactively inside the Textual UI
instead of being fed empty stdin.
"""

from __future__ import annotations

from textual.containers import Horizontal, Vertical
from textual import on
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from foxcode.tui.theme import get_theme


class ConfigFormScreen(ModalScreen):
    """Modal form that collects values for a set of config fields.

    On submit it dismisses with a dict mapping field key -> entered text
    (only non-empty values are included). Esc / Cancel dismiss with ``None``.
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+c", "cancel", "Cancel"),
    ]

    def __init__(self, *, title: str, fields: list[dict], submit_text: str = "保存"):
        super().__init__()
        self._title = title
        self._fields = fields
        self._submit_text = submit_text

    def compose(self):
        theme = get_theme()
        fox = getattr(theme, "fox", "#ffd56b")
        dim = getattr(theme, "inactive", "#7d8590")
        with Vertical(classes="config-form"):
            yield Static(self._title, classes="title")
            yield Static(
                "直接回车保持当前值 · Enter 保存 · Esc 取消",
                classes="subtitle",
            )
            for f in self._fields:
                label = f["label"]
                current = f.get("current", "")
                placeholder = f.get("placeholder", "")
                hint = f"{label}" + (f"  (当前: {current})" if current else "")
                yield Label(hint, classes="field-label")
                yield Input(
                    placeholder=placeholder or "",
                    id=f"field-{f['key']}",
                )
            with Horizontal(classes="dialog-actions"):
                yield Button(self._submit_text, id="form-submit", variant="primary")
                yield Button("取消", id="form-cancel")

    def on_mount(self):
        try:
            self.query_one("#field-" + self._fields[0]["key"], Input).focus()
        except Exception:
            pass

    def _collect(self) -> dict:
        values: dict = {}
        for f in self._fields:
            inp = self.query_one(f"#field-{f['key']}", Input)
            v = inp.value.strip()
            if v:
                values[f["key"]] = v
        return values

    @on(Button.Pressed, "#form-submit")
    def _on_submit(self, event: Button.Pressed) -> None:
        with self.prevent(Button.Pressed):
            self.dismiss(self._collect())

    @on(Input.Submitted)
    def _on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(self._collect())

    @on(Button.Pressed, "#form-cancel")
    def _on_cancel(self, event: Button.Pressed) -> None:
        with self.prevent(Button.Pressed):
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
