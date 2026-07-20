"""PromptInput - port of doge-code input area.

Multi-line TextArea with history, editing shortcuts (Ctrl+A/E/K/W/U),
mode indicator, send button, hint line.
"""

from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual import events, on
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, OptionList, Static, TextArea

from foxcode.tui.icons import ICONS
from foxcode.tui.theme import get_theme


HISTORY_MAX = 200

# Catalogue of slash commands shown by the autocomplete popup.
COMMANDS: list[tuple[str, str]] = [
    ("/help", "显示命令列表"),
    ("/clear", "清空聊天"),
    ("/save", "保存当前会话"),
    ("/mode", "设置运行模式 yolo|plan|accept_edits"),
    ("/new", "新建会话"),
    ("/sidebar", "切换侧边栏"),
    ("/fullscreen", "全屏 (别名 /fs)"),
    ("/log", "切换系统日志显示 on|off"),
    ("/cli-log", "切换 CLI 日志显示 on|off"),
    ("/welcome", "切换欢迎界面 on|off"),
    ("/delete", "删除当前消息 (all 删除所有)"),
    ("/theme", "切换主题"),
    ("/history", "显示输入历史"),
    ("/quit", "退出 (别名 /exit)"),
    ("/openai", "调整模型供应商"),
    ("/shunxapi", "配置 ShunxAPI"),
]


class CommandSuggest(OptionList):
    """Autocomplete popup for slash commands."""

    BINDINGS = []

    def __init__(self, **kwargs):
        super().__init__(id="cmd-suggest")
        self._cmds: list[str] = []

    def set_options(self, matches: list[tuple[str, str]]):
        self.clear_options()
        self._cmds = [cmd for cmd, _ in matches]
        theme = get_theme()
        gold = getattr(theme, "fox", "#ffd56b")
        dim = getattr(theme, "inactive", "#7d8590")
        for cmd, desc in matches:
            prompt = Text.assemble(
                (cmd, Style(color=gold, bold=True)),
                (f"  {desc}", Style(color=dim)),
            )
            self.add_option(prompt)
        if matches:
            self.highlighted = 0

    @property
    def selected_command(self) -> str | None:
        if self.highlighted is None or self.highlighted >= len(self._cmds):
            return None
        return self._cmds[self.highlighted]

    @on(OptionList.OptionSelected)
    def _chosen(self, event: OptionList.OptionSelected):
        if self._prompt is not None:
            self._prompt.accept_suggestion()


class _SendTextArea(TextArea):
    """TextArea that sends on Enter, newlines on Shift+Enter."""

    class Submitted(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    async def _on_key(self, event: events.Key) -> None:
        prompt = getattr(self, "_prompt", None)
        suggest_active = prompt is not None and prompt.suggest_visible()
        if event.key == "shift+enter":
            event.stop()
            event.prevent_default()
            self.insert("\n")
            if prompt is not None:
                prompt.update_suggestions(self.text)
            return
        if event.key == "enter":
            if suggest_active and prompt.suggest.selected_command:
                prompt.accept_suggestion()
            self.post_message(self.Submitted(self.text))
            event.stop()
            event.prevent_default()
            return
        if event.key in ("down", "tab"):
            if suggest_active:
                prompt.suggest_move(1)
                event.stop()
                event.prevent_default()
                return
        elif event.key == "up":
            if suggest_active:
                prompt.suggest_move(-1)
                event.stop()
                event.prevent_default()
                return
            # In command mode, reveal the completion list on Up even if it
            # is not currently visible. This never moves the input box.
            if prompt is not None and prompt.text.startswith("/") \
                    and not prompt.text.startswith("//"):
                prompt.update_suggestions(self.text)
                if prompt.suggest_visible():
                    event.stop()
                    event.prevent_default()
                    return
        elif event.key == "escape":
            if suggest_active:
                prompt.hide_suggestions()
                event.stop()
                event.prevent_default()
                return
        await super()._on_key(event)
        if prompt is not None:
            prompt.update_suggestions(self.text)


class PromptInput(Vertical):
    """Multi-line prompt with TextArea, history, editing shortcuts."""

    def __init__(self, mode: str = "yolo", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mode = mode
        self._history: list[str] = []
        self._history_index: int = -1
        self._history_temp: str = ""

    def compose(self):
        with Horizontal(classes="input-row"):
            self.mode_indicator = Static(f"{ICONS.prompt} ", classes="prompt-char")
            yield self.mode_indicator
            self.text_area = _SendTextArea(
                id="prompt-textarea",
                text="",
                soft_wrap=True,
                show_line_numbers=False,
            )
            self.text_area._prompt = self
            yield self.text_area
        # The popup is created here but NOT yielded into PromptInput.
        # It is moved to PromptInput's parent (#main-panel) in on_mount so
        # its height is governed by the parent panel (~34 rows) instead of
        # being squashed by PromptInput's max-height: 9.
        self.suggest = CommandSuggest()
        self.suggest._prompt = self
        self.suggest.display = False
        self.send_btn = Button(f"{ICONS.send} Send", id="send")
        yield self.send_btn
        yield Static(
            f"Enter send {ICONS.middle_dot} Shift+Enter newline {ICONS.middle_dot} "
            f"/command local {ICONS.middle_dot} Ctrl+A/E/K/W edit {ICONS.middle_dot} "
            f"Up/Down history {ICONS.middle_dot} F1 help",
            classes="hint",
        )

    async def on_mount(self):
        # Mount suggest as a sibling immediately before PromptInput inside
        # #main-panel.  Because chat precedes it in the Vertical layout,
        # suggest's static region y is exactly PromptInput's top edge.
        # position:absolute prevents it from advancing y, so PromptInput
        # and chat never shift, while overlay:screen gives it a full-screen
        # clip so it cannot be cropped by overflow:hidden.
        if self.suggest.parent is not self.parent:
            if self.suggest.parent is not None:
                await self.suggest.remove()
            await self.parent.mount(self.suggest, before=self)

    @on(events.Resize)
    def _on_resize(self, event: events.Resize):
        # Keep the popup flush above PromptInput after terminal resizes.
        if self.suggest_visible():
            self._position_suggestions()

    @on(_SendTextArea.Submitted)
    def _on_text_area_submitted(self, event: _SendTextArea.Submitted):
        self.screen.action_send()

    @property
    def text(self) -> str:
        return self.text_area.text

    @text.setter
    def text(self, value: str):
        self.text_area.text = value

    def focus_input(self):
        self.text_area.focus()

    def set_busy(self, busy: bool):
        self.text_area.read_only = busy
        self.send_btn.disabled = busy

    # ------------------------------------------------------------------
    # Slash-command autocomplete
    # ------------------------------------------------------------------

    def update_suggestions(self, text: str):
        if text.startswith("//") or not text.startswith("/"):
            self.hide_suggestions()
            return
        query = text[1:].lower()
        matches = [
            (cmd, desc)
            for cmd, desc in COMMANDS
            if cmd[1:].lower().startswith(query)
        ]
        if not matches:
            self.hide_suggestions()
            return
        self.suggest.set_options(matches)
        # For position:absolute widgets Textual resets the origin to (0,0)
        # of the parent content box.  We therefore compute a positive offset
        # so the popup bottom edge sits flush with PromptInput's top border.
        anchor = self.region.y - self.parent.region.y
        popup_height_guess = min(len(matches) + 2, 14)
        self.suggest.offset = (0, anchor - popup_height_guess)
        self.suggest.display = True
        self.call_after_refresh(self._position_suggestions)

    def suggest_visible(self) -> bool:
        return self.suggest.display

    def _position_suggestions(self):
        if not self.suggest.display:
            return
        # Tighten to the exact rendered height after layout.
        popup_height = self.suggest.region.height
        if not popup_height:
            return
        anchor = self.region.y - self.parent.region.y
        self.suggest.offset = (0, anchor - popup_height)

    def suggest_move(self, delta: int):
        if not self.suggest_visible():
            return
        if delta > 0:
            self.suggest.action_cursor_down()
        else:
            self.suggest.action_cursor_up()

    def accept_suggestion(self):
        cmd = self.suggest.selected_command
        if not cmd:
            self.hide_suggestions()
            return
        self.text_area.text = cmd + " "
        self.hide_suggestions()
        self.text_area.focus()

    def hide_suggestions(self):
        self.suggest.display = False


    def clear(self):
        self.text_area.text = ""

    def add_to_history(self, item: str):
        if item and (not self._history or self._history[-1] != item):
            self._history.append(item)
            if len(self._history) > HISTORY_MAX:
                self._history.pop(0)
        self._history_index = len(self._history)

    def get_history(self) -> list[str]:
        return list(self._history)

    def history_up(self) -> bool:
        if not self._history:
            return False
        if self._history_index == len(self._history):
            self._history_temp = self.text_area.text
        if self._history_index > 0:
            self._history_index -= 1
            self.text_area.text = self._history[self._history_index]
            self._cursor_end()
            return True
        return False

    def history_down(self) -> bool:
        if self._history_index < len(self._history):
            self._history_index += 1
            if self._history_index < len(self._history):
                self.text_area.text = self._history[self._history_index]
            else:
                self.text_area.text = self._history_temp
            self._cursor_end()
            return True
        return False

    def _cursor_end(self):
        lines = self.text_area.text.split("\n")
        self.text_area.cursor = (len(lines) - 1, len(lines[-1]))

    # ------------------------------------------------------------------
    # Editing actions (Ctrl+A/E/K/W/U)
    # ------------------------------------------------------------------

    def action_select_all(self):
        lines = self.text_area.text.split("\n")
        if lines and lines[0]:
            last_line = len(lines) - 1
            self.text_area.selection = ((0, 0), (last_line, len(lines[last_line])))

    def action_cursor_end(self):
        self._cursor_end()

    def action_cursor_home(self):
        self.text_area.cursor = (0, 0)

    def action_kill_line(self):
        lines = self.text_area.text.split("\n")
        row, col = self.text_area.cursor
        if row < len(lines):
            lines[row] = lines[row][:col]
            self.text_area.text = "\n".join(lines)
            self.text_area.cursor = (row, col)

    def action_kill_word(self):
        lines = self.text_area.text.split("\n")
        row, col = self.text_area.cursor
        if row < len(lines):
            line = lines[row]
            rest = line[:col].rstrip()
            new_col = rest.rfind(" ")
            if new_col < 0:
                new_col = 0
            else:
                new_col += 1
            lines[row] = rest[:new_col] + line[col:]
            self.text_area.text = "\n".join(lines)
            self.text_area.cursor = (row, new_col)

    def action_clear_line(self):
        lines = self.text_area.text.split("\n")
        row, col = self.text_area.cursor
        if row < len(lines):
            lines[row] = lines[row][col:]
            self.text_area.text = "\n".join(lines)
            self.text_area.cursor = (row, 0)

    def set_mode(self, mode: str):
        self._mode = mode
        self.mode_indicator.update(self._render_mode_char())

    def _render_mode_char(self) -> str:
        color_map = {"yolo": "#d29922", "plan": "#58a6ff", "accept_edits": "#d29922"}
        color = color_map.get(self._mode, "#ffd56b")
        return f"{ICONS.prompt} "


class PromptInputModeIndicator(Static):
    """Standalone mode character indicator."""

    def __init__(self, mode: str = "yolo", *, loading: bool = False):
        super().__init__()
        self._mode = mode
        self._loading = loading

    def render(self):
        color_map = {"yolo": "#d29922", "plan": "#58a6ff", "accept_edits": "#d29922"}
        color = color_map.get(self._mode, "#ffd56b")
        if self._loading:
            return Text(f"{ICONS.prompt} ", style=Style(color=color, dim=True))
        return Text(f"{ICONS.prompt} ", style=Style(color=color, bold=True))
