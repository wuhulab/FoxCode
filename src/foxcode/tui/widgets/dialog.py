"""Dialog - Modal dialog system, ported from doge-code Dialogs."""

from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static, TextArea
from textual import on

from foxcode.tui.theme import get_theme


class Dialog(ModalScreen):
    """Base modal dialog with border, title, and dismiss."""

    BINDINGS = [
        ("escape", "dismiss", "Close"),
    ]

    def __init__(self, title: str = "", body: str = ""):
        super().__init__()
        self._dialog_title = title
        self._dialog_body = body

    def compose(self):
        with Vertical(classes="modal"):
            if self._dialog_title:
                yield Static(self._dialog_title, classes="title")
            yield Static(self._dialog_body, classes="body")
            yield Button("Close", id="dialog-close")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "dialog-close":
            self.dismiss()

    def action_dismiss(self):
        self.dismiss()


class ConfirmDialog(Dialog):
    """Dialog with confirm/cancel buttons."""

    def __init__(self, title: str = "", body: str = "", confirm_text: str = "Confirm"):
        super().__init__(title, body)
        self._confirm_text = confirm_text
        self._confirmed = False

    def compose(self):
        with Vertical(classes="modal"):
            if self._dialog_title:
                yield Static(self._dialog_title, classes="title")
            yield Static(self._dialog_body, classes="body")
            with Vertical(classes="dialog-actions"):
                yield Button(self._confirm_text, id="dialog-confirm", variant="primary")
                yield Button("Cancel", id="dialog-cancel")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "dialog-confirm":
            self._confirmed = True
            self.dismiss(True)
        elif event.button.id == "dialog-cancel":
            self.dismiss(False)

    @property
    def confirmed(self) -> bool:
        return self._confirmed


class TextInputDialog(ModalScreen):
    """Modal with a single text input (used for renaming sessions)."""

    BINDINGS = [
        ("escape", "dismiss", "Cancel"),
    ]

    def __init__(self, title: str = "", prompt: str = "", initial: str = ""):
        super().__init__()
        self._title = title
        self._prompt = prompt
        self._initial = initial

    def compose(self):
        with Vertical(classes="modal"):
            if self._title:
                yield Static(self._title, classes="title")
            yield Input(value=self._initial, placeholder=self._prompt, id="text-input")
            with Vertical(classes="dialog-actions"):
                yield Button("OK", id="dialog-ok", variant="primary")
                yield Button("Cancel", id="dialog-cancel")

    def on_mount(self):
        self.query_one(Input).focus()

    @on(Input.Submitted)
    def _submitted(self, event: Input.Submitted):
        self.dismiss(event.value.strip())

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "dialog-ok":
            self.dismiss(self.query_one(Input).value.strip())
        elif event.button.id == "dialog-cancel":
            self.dismiss(None)


class MessageViewScreen(ModalScreen):
    """Modal screen showing raw message text in a read-only TextArea.

    Allows the user to Shift+Arrow select arbitrary text and copy with Ctrl+C.
    """

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("ctrl+c", "copy_selected", "Copy"),
    ]

    def __init__(self, text: str, title: str = "Message text"):
        super().__init__()
        self._text = text
        self._title = title

    def compose(self):
        with Vertical(classes="modal"):
            if self._title:
                yield Static(self._title, classes="title")
            yield TextArea(self._text, read_only=True)
            yield Static(
                "Esc to close  |  Shift+Arrows to select  |  Ctrl+C to copy",
                classes="body",
            )

    def on_mount(self):
        self.query_one(TextArea).focus()

    def action_copy_selected(self):
        """Copy the current TextArea selection to the system clipboard."""
        try:
            ta = self.query_one(TextArea)
            sel = getattr(ta, "selected_text", None)
            if sel:
                import pyperclip
                pyperclip.copy(sel)
        except Exception:
            pass


class HelpDialog(Dialog):
    """Keyboard shortcuts help modal."""

    def compose(self):
        theme = get_theme()
        fox = getattr(theme, "fox", "#ffd56b")
        text_color = getattr(theme, "text", "#e6edf3")
        dim = getattr(theme, "inactive", "#7d8590")

        with Vertical(classes="modal"):
            yield Static("Keyboard shortcuts", classes="title")
            shortcuts = [
                ("Enter", "send message"),
                ("Shift+Enter", "insert newline"),
                ("Ctrl+L", "clear chat"),
                ("Ctrl+N", "new session"),
                ("Ctrl+S", "save session"),
                ("Ctrl+B", "toggle sidebar"),
                ("Ctrl+T", "cycle mode"),
                ("V", "view focused message (select & copy)"),
                ("Ctrl+Y", "copy focused / last assistant message"),
                ("F1 / ?", "this help"),
                ("Ctrl+C", "copy selection / focused msg / quit"),
            ]
            lines: list[Text] = []
            for key, desc in shortcuts:
                t = Text()
                t.append(f"  {key:<14}", style=Style(bold=True, color=fox))
                t.append(desc, style=Style(color=text_color))
                lines.append(t)
            yield Static(Text("\n").join(lines), classes="body", markup=False)
            yield Static("\nPress Esc to close", style=Style(color=dim))
