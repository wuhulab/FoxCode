"""REPL Screen - Main interactive TUI screen.

1:1 port of doge-code REPL.tsx (5063 lines original).
Layout: Header | Sidebar + Chat | Spinner | PromptInput | StatusBar | Footer
Features: error boundary, loading states, fullscreen mode, editing shortcuts,
multi-line input, history, session persistence, streaming, slash autocomplete.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import re
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

from rich.console import Console
from rich.markdown import Markdown
from rich.style import Style
from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import MouseDown
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Static, TextArea

from foxcode import __version__
from foxcode.tui.icons import ICONS
from foxcode.tui.theme import get_theme, status_color
from foxcode.tui.widgets.dialog import HelpDialog, ConfirmDialog, TextInputDialog, MessageViewScreen
from foxcode.tui.widgets.logo import WelcomeBanner
from foxcode.tui.widgets.config_form import ConfigFormScreen
from foxcode.tui.widgets.message import ConfigPanelWidget, MessageWidget
from foxcode.tui.widgets.message_list import VirtualMessageList
from foxcode.tui.widgets.prompt_input import PromptInput
from foxcode.tui.widgets.session_menu import SessionMenu
from foxcode.tui.widgets.sidebar import Sidebar, SessionRow
from foxcode.tui.widgets.spinner import SpinnerWidget

SESSION_DIR = Path.home() / ".foxcode" / "sessions"
MAX_MESSAGES = 200

_STRIP_TAGS = re.compile(r"\[/?[a-zA-Z0-9_=#.,\s-]+\]")


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _fmt_tokens(n: int) -> str:
    if n < 1000:
        return str(n)
    if n < 10_000:
        return f"{n / 1000:.1f}k"
    if n < 1_000_000:
        return f"{n // 1000}k"
    return f"{n / 1_000_000:.1f}m"


def safe(fn):
    """Decorator: run action in try/except, show error in chat."""
    def wrapper(self, *args, **kwargs):
        try:
            return fn(self, *args, **kwargs)
        except Exception as exc:
            self._system(f"Error in {fn.__name__}: {exc}")
            if "--debug" in __import__("sys").argv:
                traceback.print_exc()
    return wrapper


class REPLScreen(Screen):
    """Main interactive REPL screen.

    Layout:
      ┌─ Header (model {dot} mode {dot} tokens) ────────────────┐
      ├────────┬────────────────────────────────────────────────┤
      │Sidebar │  Chat (VirtualMessageList, scrollable,         │
      │        │        messages bottom-aligned)                │
      │        │  [SpinnerWidget when busy]                     │
      │        ├────────────────────────────────────────────────┤
      │        │  PromptInput (TextArea + slash autocomplete)   │
      │        ├────────────────────────────────────────────────┤
      │        │  StatusBar (model {dot} token {dot} mode)      │
      ├────────┴────────────────────────────────────────────────┤
      │ Footer: key bindings                                    │
      └─────────────────────────────────────────────────────────┘
    """

    TITLE = "FoxCode"
    SUB_TITLE = ""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+c", "ctrl_c", "Copy", show=True, priority=True),
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+y", "copy_last", "Copy block", show=True),
        Binding("ctrl+l", "clear_chat", "Clear", show=True),
        Binding("ctrl+n", "new_session", "New", show=True),
        Binding("ctrl+s", "save_session", "Save", show=True),
        Binding("ctrl+b", "toggle_sidebar", "Sidebar", show=True),
        Binding("ctrl+t", "cycle_mode", "Mode", show=True),
        Binding("f1,question_mark", "help", "Help", show=True),
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("pageup", "page_up", "Page Up", show=False),
        Binding("pagedown", "page_down", "Page Down", show=False),
        Binding("f11", "toggle_fullscreen", "Fullscreen", show=False),
        Binding("v", "view_message", "View text", show=False),
    ]

    sidebar_visible: reactive[bool] = reactive(True)
    busy: reactive[bool] = reactive(False)
    mode: reactive[str] = reactive("yolo")
    fullscreen: reactive[bool] = reactive(False)

    def __init__(self, agent=None, config=None):
        super().__init__()
        self.agent = agent
        self.config = config
        self._session_id: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._session_messages: list[dict] = []
        self._run_mode_index: int = 0
        self._run_modes: tuple[str, ...] = ("yolo", "plan", "accept_edits")
        self._token_count: int = 0
        self._model: str = "default"
        self._refreshing_sessions = False
        self._session_menu = None
        self._pending_menu_sid = None
        SESSION_DIR.mkdir(parents=True, exist_ok=True)

        # 从配置加载 TUI 状态
        self.system_log_enabled = True
        if config is not None and hasattr(config, "tui"):
            tui_cfg = config.tui
            if hasattr(tui_cfg, "sidebar_visible"):
                self.sidebar_visible = tui_cfg.sidebar_visible
            if hasattr(tui_cfg, "fullscreen"):
                self.fullscreen = tui_cfg.fullscreen
            if hasattr(tui_cfg, "system_log_enabled"):
                self.system_log_enabled = tui_cfg.system_log_enabled

    def watch_busy(self, busy: bool):
        """Reactive watcher: update UI when busy state changes."""
        if hasattr(self, "prompt_input") and self.prompt_input is not None:
            self.prompt_input.set_busy(busy)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="body"):
            self.sidebar = Sidebar(id="sidebar")
            yield self.sidebar
            with Vertical(id="main-panel"):
                self.chat = VirtualMessageList(id="chat")
                yield self.chat
                self.spinner = SpinnerWidget(id="spinner-widget")
                self.spinner.display = False
                yield self.spinner
                self.prompt_input = PromptInput(mode=self.mode, id="prompt-panel")
                yield self.prompt_input
                self.status_bar = Static(classes="status-bar", id="status-bar")
                yield self.status_bar
        yield Footer()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self):
        # 应用从配置加载的 TUI 状态
        try:
            if self.sidebar is not None:
                self.sidebar.display = self.sidebar_visible
        except Exception:
            pass
        try:
            if self.fullscreen:
                if self.sidebar is not None:
                    self.sidebar.display = False
        except Exception:
            pass
        try:
            self._show_banner()
        except Exception:
            pass
        try:
            self._refresh_header()
        except Exception:
            pass
        try:
            self._restore_session()
        except Exception:
            pass
        try:
            self._refresh_sessions_list()
        except Exception:
            pass
        try:
            self.call_after_refresh(self.prompt_input.focus_input)
        except Exception:
            try:
                self.prompt_input.focus_input()
            except Exception:
                pass

    def _show_banner(self):
        for old in list(self.chat.query(WelcomeBanner)):
            try:
                old.remove()
            except Exception:
                pass
        self.chat.mount(WelcomeBanner(classes="banner"))

    # ------------------------------------------------------------------
    # Message helpers
    # ------------------------------------------------------------------

    def _system(self, text: str):
        if not getattr(self, "system_log_enabled", True):
            return
        try:
            self.chat.add_message(MessageWidget("system", f"{_now()} {text}"))
        except Exception:
            pass

    def _user(self, text: str):
        msg = MessageWidget("user", text)
        self.chat.add_message(msg)
        self._session_messages.append({"role": "user", "content": text, "ts": _now()})

    def _assistant_thinking(self) -> MessageWidget | None:
        try:
            msg = MessageWidget("assistant", "", thinking=True)
            self.chat.add_message(msg)
            return msg
        except Exception:
            return None

    def _refresh_header(self):
        try:
            h = self.query_one(Header)
            sub = h.query_one("#subtitle", Static)
            sub.styles.color = status_color(self.mode)
            model = self._read_model()
            self.sub_title = f"{model} {ICONS.middle_dot} {self.mode} {ICONS.middle_dot} {_fmt_tokens(self._token_count)} tok"
        except Exception:
            pass
        self._refresh_status()

    def _refresh_status(self):
        """Update the status line shown below the input box."""
        try:
            model = self._read_model()
            self.status_bar.update(
                f"FoxCode TUI  模型: {model} | Token: {_fmt_tokens(self._token_count)} | 模式: {self.mode}"
            )
        except Exception:
            pass

    def _read_model(self) -> str:
        cfg = self.config
        if cfg is not None:
            model_obj = getattr(cfg, "model", None)
            if model_obj is not None and getattr(model_obj, "model_name", None):
                return model_obj.model_name
            if getattr(cfg, "model_name", None):
                return cfg.model_name
        # Fall back to the agent's active model if the config lacks one.
        agent = self.agent
        if agent is not None:
            provider = getattr(agent, "model_provider", None)
            name = getattr(provider, "model_name", None) or getattr(agent, "model_name", None)
            if name:
                return name
        return self._model or "default"

    def _scroll_end(self):
        try:
            self.chat.scroll_end(animate=True)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Spinner
    # ------------------------------------------------------------------

    def _start_spinner(self, thinking: bool = False):
        self.spinner.mode = "thinking" if thinking else "responding"
        self.spinner.thinking = thinking
        self.spinner.display = True

    def _stop_spinner(self):
        self.spinner.display = False

    # ------------------------------------------------------------------
    # Session persistence
    # ------------------------------------------------------------------

    def _save_session(self):
        try:
            path = SESSION_DIR / f"{self._session_id}.json"
            data = {
                "id": self._session_id,
                "mode": self.mode,
                "token_count": self._token_count,
                "messages": self._session_messages[-MAX_MESSAGES:],
                "ts": _now(),
            }
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            self._system(f"Save failed: {exc}")

    def _restore_session(self):
        try:
            sessions = sorted(SESSION_DIR.glob("*.json"), reverse=True)
            if not sessions:
                return
            data = json.loads(sessions[0].read_text(encoding="utf-8"))
            sid = data.get("id", self._session_id)
            self._load_tui_session(sid, announce=False)
        except Exception as exc:
            self._system(f"Restore failed: {exc}")

    # ------------------------------------------------------------------
    # Session list (sidebar history)
    # ------------------------------------------------------------------

    def _list_tui_sessions(self) -> list[dict]:
        """List locally persisted TUI sessions (newest first)."""
        sessions: list[dict] = []
        try:
            for f in sorted(SESSION_DIR.glob("*.json"), reverse=True):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                except Exception:
                    continue
                sessions.append(
                    {
                        "session_id": data.get("id", f.stem),
                        "name": data.get("name"),
                        "created_at": data.get("ts", ""),
                        "message_count": len(data.get("messages", [])),
                    }
                )
        except Exception:
            pass
        return sessions

    def _refresh_sessions_list(self):
        self._refreshing_sessions = True
        try:
            self.sidebar.refresh_sessions(self._list_tui_sessions(), self._session_id)
        except Exception:
            pass
        finally:
            self._refreshing_sessions = False

    @on(SessionRow.Selected)
    def _on_session_selected(self, event: SessionRow.Selected):
        # Ignore selections fired while we rebuild the list.
        if getattr(self, "_refreshing_sessions", False):
            return
        sid = event.sid
        if not sid:
            return
        self._load_tui_session(sid)

    @safe
    def _load_tui_session(self, sid: str, announce: bool = True):
        """Load a persisted TUI session: restore chat display AND give the
        agent an isolated context seeded with that session's history."""
        path = SESSION_DIR / f"{sid}.json"
        if not path.exists():
            self._system(f"Session not found: {sid}")
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self._system(f"Load failed: {exc}")
            return

        messages = data.get("messages", [])

        # 隔离上下文：为每个会话创建独立的 agent 会话，
        # 并载入该会话的历史，保证不同会话之间上下文不串台。
        if self.agent is not None:
            try:
                from foxcode.core.session import Session
                from foxcode.types.message import Message

                self.agent.session = Session(self.config, sid)
                conv = self.agent.session.conversation
                for m in messages:
                    role = m.get("role")
                    content = m.get("content", "")
                    if role and content:
                        conv.add_message(Message(role=role, content=content))
            except Exception:
                pass

        self._session_id = sid
        self._session_messages = list(messages)
        self._token_count = data.get("token_count", 0)
        self.chat.clear_messages()
        self._show_banner()
        for m in messages[-50:]:
            role = m.get("role", "system")
            content = m.get("content", "")
            if content:
                widget = MessageWidget(role, content)
                if role == "assistant":
                    widget.finalize()
                self.chat.add_message(widget)
        self._refresh_sessions_list()
        self._refresh_status()
        # Scroll to the newest message only after the screen is fully laid
        # out, otherwise the scroll offset is computed against a stale size
        # (the chat height isn't final during initial mount).
        self.call_after_refresh(self.chat.scroll_end, animate=False)
        if announce:
            self._system(f"Loaded session {sid[:8]}")

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    @on(Button.Pressed, "#send")
    def _on_send_click(self, event: Button.Pressed):
        with self.prevent(Button.Pressed):
            self.action_send()

    @on(Button.Pressed, "#new-session")
    def _on_new_session_click(self, event: Button.Pressed):
        with self.prevent(Button.Pressed):
            self.action_new_session()

    # ------------------------------------------------------------------
    # Session context menu (right-click history entry)
    # ------------------------------------------------------------------

    @on(MouseDown)
    def _on_mouse_down(self, event: MouseDown):
        # Right mouse button opens the session context menu.
        if event.button == 3:
            self._maybe_open_session_menu(event)
            return
        # Any other click dismisses an open menu.
        if self._session_menu is not None:
            self._dismiss_session_menu()

    def _maybe_open_session_menu(self, event: MouseDown):
        # Locate the session row under the cursor.
        w = event.widget
        item = None
        while w is not None:
            if isinstance(w, SessionRow):
                item = w
                break
            w = w.parent
        if item is None or item.parent is not self.sidebar.sessions:
            return
        sid = item.sid
        if not sid:
            return
        self._open_session_menu(sid, int(event.screen_x), int(event.screen_y))

    def _open_session_menu(self, sid: str, x: int, y: int):
        self._dismiss_session_menu()
        self._pending_menu_sid = sid
        self._session_menu = SessionMenu(
            sid, x, y, self._on_session_menu_pick
        )
        self.mount(self._session_menu)

    def _dismiss_session_menu(self):
        if self._session_menu is not None:
            try:
                self._session_menu.remove()
            except Exception:
                pass
            self._session_menu = None

    def _on_session_menu_pick(self, action: str):
        self._session_menu = None
        sid = self._pending_menu_sid
        if action == "重命名":
            self._rename_session(sid)
        elif action == "删除":
            self._delete_session(sid)

    @on(SessionRow.MenuClicked)
    def _on_session_menu_clicked(self, event: SessionRow.MenuClicked):
        """Handle ⋮ click on a sidebar session entry."""
        self._open_session_menu(event.sid, event.x, event.y)

    def _rename_session(self, sid: str):
        path = SESSION_DIR / f"{sid}.json"
        current = ""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            current = data.get("name", "") or ""
        except Exception:
            pass

        def _on_result(new_name: str | None):
            if not new_name:
                self._system("已取消重命名。")
                return
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                data["name"] = new_name
                path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                self._refresh_sessions_list()
                self._system(f"已重命名为：{new_name}")
            except Exception as exc:
                self._system(f"重命名失败: {exc}")

        self.app.push_screen(
            TextInputDialog(title="重命名会话", prompt="新名称", initial=current),
            _on_result,
        )

    def _delete_session(self, sid: str):
        def _on_result(confirmed: bool):
            if not confirmed:
                self._system("已取消删除。")
                return
            try:
                path = SESSION_DIR / f"{sid}.json"
                path.unlink(missing_ok=True)
                if self._session_id == sid:
                    # 当前会话被删除：直接重置状态，避免 action_new_session
                    # 把刚删除的会话重新写回磁盘。
                    self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
                    self._session_messages.clear()
                    self._token_count = 0
                    self.chat.clear_messages()
                    self._show_banner()
                    self._refresh_status()
                    self._system(f"New session {self._session_id[:8]}")
                self._refresh_sessions_list()
                self._system(f"已删除会话 {sid[:8]}")
            except Exception as exc:
                self._system(f"删除失败: {exc}")

        self.app.push_screen(
            ConfirmDialog(title="删除会话", body=f"确定删除会话 {sid[:8]}？此操作不可撤销。", confirm_text="删除"),
            _on_result,
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    @safe
    def action_send(self):
        text = self.prompt_input.text.strip()
        if not text:
            return
        self.prompt_input.clear()
        if text.startswith("//"):
            self.prompt_input.add_to_history(text)
            if self.busy:
                return
            self._user(text[1:])
            self._dispatch_to_agent(text[1:])
            return
        if text.startswith("/") or text.startswith("／"):
            self._run_command(text[1:].strip())
            self.prompt_input.focus_input()
            return
        self.prompt_input.add_to_history(text)
        if self.busy:
            return
        self._user(text)
        self._dispatch_to_agent(text)

    def _dispatch_to_agent(self, text: str):
        self.busy = True
        self._start_spinner(thinking=True)
        self.spinner.update_verb("Thinking")
        self._stream_response(text)

    @safe
    def action_clear_chat(self):
        self.chat.clear_messages()
        self._show_banner()
        self._session_messages.clear()
        self._system("Chat cleared")

    @safe
    def action_new_session(self):
        self._save_session()
        # 上下文隔离：为 agent 创建一个全新的、独立的会话上下文，
        # 避免新旧会话的对话历史互相串台（context leaking）。
        if self.agent is not None:
            try:
                from foxcode.core.session import Session

                self.agent.session = Session(self.config)
            except Exception:
                pass
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._session_messages.clear()
        self._token_count = 0
        self.chat.clear_messages()
        self._show_banner()
        self._refresh_sessions_list()
        self._refresh_status()
        self._system(f"New session {self._session_id[:8]}")

    @safe
    def action_save_session(self):
        self._save_session()
        self._system(f"Saved session {self._session_id[:8]}")

    @safe
    def action_toggle_sidebar(self):
        self.sidebar_visible = not self.sidebar_visible
        self.sidebar.display = self.sidebar_visible
        self._persist_tui_state()

    @safe
    def action_cycle_mode(self):
        self._run_mode_index = (self._run_mode_index + 1) % len(self._run_modes)
        self.mode = self._run_modes[self._run_mode_index]
        self.prompt_input.set_mode(self.mode)
        self._refresh_header()
        self._system(f"Mode {ICONS.forward} {self.mode}")

    @safe
    def action_toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.sidebar.display = False
            self.sidebar_visible = False
        else:
            self.sidebar.display = True
            self.sidebar_visible = True
        self._system(f"Fullscreen {ICONS.forward} {'on' if self.fullscreen else 'off'}")
        self._persist_tui_state()

    def _persist_tui_state(self):
        """将当前 TUI 状态持久化到配置文件中。"""
        cfg = self.config
        if cfg is None or not hasattr(cfg, "tui"):
            return
        try:
            cfg.tui.sidebar_visible = self.sidebar_visible
            cfg.tui.fullscreen = self.fullscreen
            cfg.tui.system_log_enabled = self.system_log_enabled
            cfg.save_tui_config()
        except Exception:
            pass

    @safe
    def action_page_up(self):
        self.chat.scroll_up(10)

    @safe
    def action_page_down(self):
        self.chat.scroll_down(10)

    @safe
    def action_history_up(self):
        self.prompt_input.history_up()

    @safe
    def action_history_down(self):
        self.prompt_input.history_down()

    @safe
    def action_select_all(self):
        self.prompt_input.action_select_all()

    @safe
    def action_cursor_end(self):
        self.prompt_input.action_cursor_end()

    @safe
    def action_cursor_home(self):
        self.prompt_input.action_cursor_home()

    @safe
    def action_kill_line(self):
        self.prompt_input.action_kill_line()

    @safe
    def action_kill_word(self):
        self.prompt_input.action_kill_word()

    @safe
    def action_clear_input(self):
        self.prompt_input.action_clear_line()

    @safe
    def action_help(self):
        self.app.push_screen(HelpDialog())

    @safe
    def action_quit(self):
        self._save_session()
        self.app.exit()

    @safe
    def action_cancel(self):
        if self.busy:
            self._system("Cancelled")
            self.busy = False
            self._stop_spinner()
            self.prompt_input.focus_input()

    @safe
    def action_ctrl_c(self):
        """Copy like a normal terminal: the focused message, the selected
        text in the input, or (as a fallback) the last assistant reply.

        Inside the input: if text is selected -> copy it; if nothing is
        selected -> quit. Focus and layout are left untouched so the input
        box never shifts position.
        """
        focused = self.focused
        # Inside the input: copy any selected text, else quit.
        if focused is self.prompt_input.text_area:
            sel = self.prompt_input.text_area.selected_text
            if sel:
                self._copy_text(sel)
            else:
                self.app.exit()
            return
        # A focused message box -> copy its full content.
        if isinstance(focused, MessageWidget):
            self._copy_text(focused.text_body)
            return
        # Any selected text in the focused widget.
        sel = getattr(focused, "selected_text", None) if focused is not None else None
        if sel:
            self._copy_text(sel)
            return
        # Nothing focused -> copy the last assistant reply.
        for m in reversed(list(self.chat.query(MessageWidget))):
            if m.role == "assistant":
                self._copy_text(m.text_body)
                return

    # ------------------------------------------------------------------
    # Copy helpers
    # ------------------------------------------------------------------

    def _copy_text(self, text: str) -> bool:
        try:
            import pyperclip

            pyperclip.copy(text)
            return True
        except Exception:
            return False

    @safe
    def action_copy_last(self):
        """Copy the currently focused message in full, or fall back to the
        last assistant reply.
        """
        focused = self.focused
        if isinstance(focused, MessageWidget):
            self._copy_text(focused.text_body)
            return
        for m in reversed(list(self.chat.query(MessageWidget))):
            if m.role == "assistant":
                self._copy_text(m.text_body)
                return

    @safe
    def action_view_message(self):
        """Open a read-only TextArea modal for the focused message so the
        user can Shift+Arrow select arbitrary text and copy with Ctrl+C.
        """
        focused = self.focused
        if not isinstance(focused, MessageWidget) or not focused.text_body:
            return
        def _on_close(_result=None):
            self.call_after_refresh(self.prompt_input.focus_input)

        self.app.push_screen(
            MessageViewScreen(focused.text_body, title=f"{focused.role} message"),
            _on_close,
        )

    # ------------------------------------------------------------------
    # Slash commands (local instruction execution, not sent to the agent)
    # ------------------------------------------------------------------

    _COMMAND_HELP = [
        ("/help", "show this command list"),
        ("/clear", "clear the chat (cancels in-progress output)"),
        ("/save", "save the current session"),
        ("/mode [name]", "set run mode: yolo | plan | accept_edits"),
        ("/new", "start a new session"),
        ("/sidebar", "toggle the sidebar"),
        ("/fullscreen", "toggle fullscreen (alias /fs)"),
        ("/log [on|off]", "toggle system log display in TUI"),
        ("/cli-log [on|off]", "toggle CLI log display in TUI"),
        ("/welcome [on|off]", "toggle welcome screen on startup"),
        ("/delete [all]", "delete current/all messages (confirm required)"),
        ("/theme [name]", "switch theme"),
        ("/history", "show input history"),
        ("/quit", "quit FoxCode (alias /exit)"),
        ("/<other>", "any other /command is forwarded to the CLI"),
    ]

    _COMMANDS = {
        "help": "_cmd_help",
        "clear": "_cmd_clear",
        "save": "_cmd_save",
        "mode": "_cmd_mode",
        "new": "_cmd_new",
        "sidebar": "_cmd_sidebar",
        "fullscreen": "_cmd_fullscreen",
        "fs": "_cmd_fullscreen",
        "log": "_cmd_log",
        "cli-log": "_cmd_cli_log",
        "welcome": "_cmd_welcome",
        "delete": "_cmd_delete",
        "theme": "_cmd_theme",
        "history": "_cmd_history",
        "quit": "_cmd_quit",
        "exit": "_cmd_quit",
    }

    def _run_command(self, raw: str):
        parts = raw.split()
        if not parts:
            self._system("Empty command. Type /help for commands.")
            return
        name = parts[0].lower()
        args = parts[1:]
        if name in ("openai", "shunxapi"):
            self._run_interactive_config(name)
            return
        method = self._COMMANDS.get(name)
        if method is not None:
            try:
                getattr(self, method)(args)
            except Exception as exc:
                self._system(f"Command error (/{name}): {exc}")
            return
        self._run_cli_command(raw)

    def _run_cli_command(self, text: str):
        name = text.split()[0] if text.split() else ""

        # 检查当前是否允许显示 CLI 日志
        def _allow_cli_log() -> bool:
            cfg = self.config
            return cfg is None or not hasattr(cfg, "tui") or cfg.tui.cli_log_enabled

        try:
            from foxcode import cli as fox_cli
        except Exception:
            if _allow_cli_log():
                self._system(f"Unknown command: /{name}. Type /help for commands.")
            return
        if self.agent is None and self.config is None:
            if _allow_cli_log():
                self._system(f"Unknown command: /{name}. Type /help for commands.")
            return
        cli_text = text if text.startswith("/") else "/" + text
        buf = io.StringIO()
        cap = Console(file=buf, markup=False, no_color=True, width=120, highlight=False)
        old_console = fox_cli.console
        old_stdout = sys.stdout
        old_stdin = sys.stdin
        fox_cli.console = cap
        sys.stdout = buf
        sys.stdin = io.StringIO("\n" * 64)
        result = True
        exc_info = None
        try:
            result = fox_cli._handle_command(cli_text, self.agent, self.config)
        except EOFError:
            result = True
        except Exception as exc:
            exc_info = exc
        finally:
            fox_cli.console = old_console
            sys.stdout = old_stdout
            sys.stdin = old_stdin

        # 当 cli_log_enabled 为 False 时不显示 CLI 日志输出
        if not _allow_cli_log():
            if result is False:
                self.action_quit()
            return

        if exc_info is not None:
            self._system(f"CLI command error (/{name}): {exc_info}")
            return

        raw = _STRIP_TAGS.sub("", buf.getvalue())
        lines = [
            ln for ln in raw.splitlines()
            if "查看可用命令" not in ln and "输入 /help" not in ln
        ]
        output = "\n".join(lines).strip()
        if output:
            self._system(output)
        else:
            self._system(f"Ran /{name}.")
        if result is False:
            self.action_quit()

    # ------------------------------------------------------------------
    # Interactive config commands (/openai, /shunxapi)
    # ------------------------------------------------------------------

    def _run_interactive_config(self, kind: str):
        """Launch an interactive modal form for config commands.

        The CLI handlers rely on ``console.input`` which cannot be answered
        from inside the TUI, so we collect the values with a native modal and
        apply them through the shared ``apply_model_settings`` helper.
        """
        cfg = self.config
        if cfg is None or getattr(cfg, "model", None) is None:
            self._system("没有可用的配置对象，无法交互式配置。")
            return
        model = cfg.model
        has_key = bool(getattr(model, "api_key", None))

        if kind == "openai":
            fields = [
                {
                    "key": "url",
                    "label": "URL",
                    "current": getattr(model, "base_url", "") or "",
                    "placeholder": "如 https://api.openai.com/v1",
                },
                {
                    "key": "key",
                    "label": "API Key",
                    "current": "已设置" if has_key else "",
                    "placeholder": "留空保持当前值",
                },
                {
                    "key": "model",
                    "label": "Model",
                    "current": getattr(model, "model_name", "") or "",
                    "placeholder": f"当前: {getattr(model, 'model_name', '')}",
                },
            ]
            title = "🔧 配置 OpenAI"
            infer = True
        elif kind == "shunxapi":
            fields = [
                {
                    "key": "key",
                    "label": "API Key",
                    "current": "已设置" if has_key else "",
                    "placeholder": "留空保持当前值",
                },
                {
                    "key": "model",
                    "label": "Model",
                    "current": getattr(model, "model_name", "") or "",
                    "placeholder": f"当前: {getattr(model, 'model_name', '')}",
                },
            ]
            title = "🔧 配置 ShunxAPI"
            infer = False
        else:
            self._system(f"未知的配置命令: {kind}")
            return

        def _on_result(result: dict | None):
            if not result:
                self._system("已取消配置。")
                return
            try:
                from foxcode import cli as fox_cli

                save_msg = fox_cli.apply_model_settings(
                    cfg,
                    self.agent,
                    url=result.get("url", ""),
                    key=result.get("key", ""),
                    model=result.get("model", ""),
                    infer_provider=infer,
                )
            except Exception as exc:
                self._system(f"配置失败: {exc}")
                return
            self._show_config_panel(kind, save_msg)
            self.prompt_input.focus_input()

        self.app.push_screen(ConfigFormScreen(title=title, fields=fields), _on_result)

    def _show_config_panel(self, kind: str, save_msg: str):
        cfg = self.config
        model = getattr(cfg, "model", None)
        if kind == "shunxapi":
            title = "✅ ShunxAPI 配置已更新"
            url = "https://ai-api2.shunx.top/v1 (默认)"
        else:
            title = "✅ OpenAI 配置已更新"
            url = getattr(model, "base_url", "") or "未设置"
        has_key = bool(getattr(model, "api_key", None)) if model else False
        body = (
            f"URL: {url}\n"
            f"Key: {'已设置' if has_key else '未设置'}\n"
            f"Model: {getattr(model, 'model_name', '') or '未设置'}\n"
            f"{save_msg}"
        )
        self.chat.add_message(ConfigPanelWidget(title, body, role="system"))

    def _cancel_stream(self):
        if self.busy:
            try:
                self.workers.cancel_group(self, "chat")
            except Exception:
                pass
            self.busy = False
            self._stop_spinner()

    def _cmd_help(self, args):
        lines = [f"{ICONS.fox} FoxCode commands (TUI):"]
        for cmd, desc in self._COMMAND_HELP:
            lines.append(f"  {ICONS.bullet} {cmd}  {desc}")
        lines.append(f"  {ICONS.bullet} //text  send a literal message starting with /")
        lines.append("")
        lines.append("Any other /command is forwarded to the CLI and run there.")
        self._system("\n".join(lines))

    def _cmd_clear(self, args):
        self._cancel_stream()
        self.action_clear_chat()

    def _cmd_new(self, args):
        self._cancel_stream()
        self.action_new_session()

    def _cmd_save(self, args):
        self.action_save_session()

    def _cmd_mode(self, args):
        if not args:
            self._system(f"Current mode: {self.mode}. Options: {', '.join(self._run_modes)}")
            return
        target = args[0].lower()
        if target not in self._run_modes:
            self._system(f"Unknown mode: {target}. Options: {', '.join(self._run_modes)}")
            return
        self._run_mode_index = self._run_modes.index(target)
        self.mode = target
        self.prompt_input.set_mode(self.mode)
        cfg = self.config
        if cfg is not None:
            if hasattr(cfg, "run_mode"):
                try:
                    cfg.run_mode = target
                except Exception:
                    pass
            elif hasattr(cfg, "mode"):
                try:
                    cfg.mode = target
                except Exception:
                    pass
        if self.agent and hasattr(self.agent, "set_mode"):
            try:
                self.agent.set_mode(target)
            except Exception:
                pass
        self._refresh_header()
        self._refresh_status()
        self._system(f"Mode {ICONS.forward} {self.mode}")

    def _cmd_sidebar(self, args):
        self.action_toggle_sidebar()
        self._system(f"Sidebar {ICONS.forward} {'on' if self.sidebar_visible else 'off'}")

    def _cmd_fullscreen(self, args):
        self.action_toggle_fullscreen()

    def _cmd_theme(self, args):
        from foxcode.tui.theme import list_themes, set_theme

        if not args:
            self._system(f"Available themes: {', '.join(list_themes())}. Current: {get_theme().fox}")
            return
        name = args[0].lower()
        if name not in list_themes():
            self._system(f"Unknown theme: {name}. Options: {', '.join(list_themes())}")
            return
        set_theme(name)
        theme = get_theme()
        self.app.styles.background = getattr(theme, "background", "#0d1117")
        self.app.refresh()
        self._refresh_header()
        self._system(f"Theme {ICONS.forward} {name}")

    def _cmd_history(self, args):
        history = self.prompt_input.get_history()
        if not history:
            self._system("No history yet.")
            return
        shown = history[-20:]
        lines = [f"{ICONS.fox} Input history ({len(history)}):"]
        for i, item in enumerate(shown, start=max(1, len(history) - 19)):
            snippet = item if len(item) <= 60 else item[:57] + "..."
            lines.append(f"  {i}. {snippet}")
        self._system("\n".join(lines))

    def _cmd_quit(self, args):
        self.action_quit()

    def _cmd_log(self, args):
        if not args:
            state = "on" if self.system_log_enabled else "off"
            self._system(f"System log display is {state}. Usage: /log on | off")
            return
        arg = args[0].lower()
        if arg == "on":
            self.system_log_enabled = True
            self._system("System log display enabled")
        elif arg == "off":
            self.system_log_enabled = False
            self._system("System log display disabled")
        else:
            self._system("Usage: /log on | off")
            return
        self._persist_tui_state()

    def _cmd_cli_log(self, args):
        cfg = self.config
        if cfg is None or not hasattr(cfg, "tui"):
            self._system("TUI 配置不可用")
            return
        if not args:
            state = "on" if cfg.tui.cli_log_enabled else "off"
            self._system(f"CLI log display is {state}. Usage: /cli-log on | off")
            return
        arg = args[0].lower()
        if arg == "on":
            cfg.tui.cli_log_enabled = True
            self._system("CLI log display enabled")
        elif arg == "off":
            cfg.tui.cli_log_enabled = False
            self._system("CLI log display disabled")
        else:
            self._system("Usage: /cli-log on | off")
            return
        try:
            cfg.save_tui_config()
        except Exception:
            pass

    def _cmd_welcome(self, args):
        cfg = self.config
        if cfg is None or not hasattr(cfg, "tui"):
            self._system("TUI 配置不可用")
            return
        if not args:
            state = "on" if cfg.tui.welcome_enabled else "off"
            self._system(f"Welcome screen is {state}. Usage: /welcome on | off")
            return
        arg = args[0].lower()
        if arg == "on":
            cfg.tui.welcome_enabled = True
            self._system("Welcome screen enabled")
        elif arg == "off":
            cfg.tui.welcome_enabled = False
            self._system("Welcome screen disabled")
        else:
            self._system("Usage: /welcome on | off")
            return
        try:
            cfg.save_tui_config()
        except Exception:
            pass

    def _cmd_delete(self, args):
        arg = args[0].lower() if args else ""
        if arg == "all":
            def _on_confirm(confirmed: bool | None):
                if confirmed:
                    self._session_messages.clear()
                    self.chat.clear_messages()
                    self._system("All messages deleted")
                else:
                    self._system("Delete cancelled")
                self.prompt_input.focus_input()

            self.app.push_screen(
                ConfirmDialog(
                    title="⚠️ 确认删除",
                    body="确定要删除所有消息吗？此操作不可恢复。",
                    confirm_text="删除",
                ),
                _on_confirm,
            )
            return
        # 默认删除当前/最近的消息（清空当前会话）
        def _on_confirm_current(confirmed: bool | None):
            if confirmed:
                self._session_messages.clear()
                self.chat.clear_messages()
                self._system("Current session messages deleted")
            else:
                self._system("Delete cancelled")
            self.prompt_input.focus_input()

        self.app.push_screen(
            ConfirmDialog(
                title="⚠️ 确认删除",
                body="确定要清空当前会话的所有消息吗？",
                confirm_text="删除",
            ),
            _on_confirm_current,
        )

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    def _stream_response(self, user_input: str):
        self._stream_worker(user_input)

    @work(exclusive=True, group="chat")
    async def _stream_worker(self, user_input: str):
        """Consume agent.chat() stream, parse tags, and render each piece
        into its own MessageWidget so users see AI speech, tool calls,
        and tool results appear one-by-one in real time.
        """
        _TAG_RE = re.compile(r'\[(say|tool|result|/result|info|warn|error)\]', re.IGNORECASE)
        _ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')

        assistant_widget: MessageWidget | None = None
        tool_widget: MessageWidget | None = None
        assistant_full = ""
        started = time.time()
        token_count = 0

        _buf = ""
        _mode = "say"

        def _ensure_assistant():
            nonlocal assistant_widget
            if assistant_widget is None:
                assistant_widget = MessageWidget("assistant", "")
                self.chat.add_message(assistant_widget)
            return assistant_widget

        def _ensure_tool():
            nonlocal tool_widget
            if tool_widget is None:
                tool_widget = MessageWidget("tool", "")
                self.chat.add_message(tool_widget)
            return tool_widget

        def _flush_buf():
            nonlocal _buf, assistant_full
            text = _buf
            _buf = ""
            if not text:
                return
            if _mode == "say":
                _ensure_assistant().append_text(text)
                assistant_full += text
            elif _mode in ("tool", "result"):
                _ensure_tool().append_text(text)
            elif _mode == "info":
                self._system(f"[info] {text.rstrip(chr(10))}")
            elif _mode == "warn":
                self._system(f"[warn] {text.rstrip(chr(10))}")
            elif _mode == "error":
                self._system(f"[error] {text.rstrip(chr(10))}")

        try:
            if self.agent and hasattr(self.agent, "chat") and callable(getattr(self.agent, "chat", None)):
                self.spinner.mode = "responding"
                self.spinner.thinking = False
                async for chunk in self.agent.chat(user_input):
                    if not chunk:
                        continue
                    chunk = _ANSI_RE.sub("", chunk)
                    _buf += chunk

                    while _buf:
                        m = _TAG_RE.search(_buf)
                        if not m:
                            _flush_buf()
                            break

                        before = _buf[:m.start()]
                        _buf = _buf[m.end():]
                        if before:
                            tmp = _buf
                            _buf = before
                            _flush_buf()
                            _buf = tmp

                        tag = m.group(1).lower()
                        if tag == "say":
                            _mode = "say"
                        elif tag == "tool":
                            _mode = "tool"
                            tool_widget = None
                        elif tag == "result":
                            _mode = "result"
                            tool_widget = None
                        elif tag == "/result":
                            _mode = "raw"
                            tool_widget = None
                        elif tag == "info":
                            _mode = "info"
                        elif tag == "warn":
                            _mode = "warn"
                        elif tag == "error":
                            _mode = "error"

                    token_count += len(chunk) // 4
                    self.spinner.update_tokens(token_count)
                    self._scroll_end()
            else:
                assistant_widget = self._assistant_thinking()
                await self._simulate_stream(assistant_widget)
                assistant_full = assistant_widget.text_body if assistant_widget else ""
                token_count = len(assistant_full) // 4
                if assistant_widget:
                    assistant_widget.finalize()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            err = f"\n\n[error] {exc}"
            if assistant_widget:
                assistant_widget.append_text(err)
                assistant_full += err
            self._system(f"Error: {exc}")
        finally:
            if assistant_widget and hasattr(assistant_widget, "finalize"):
                assistant_widget.finalize()
            elapsed = time.time() - started
            self._token_count += token_count
            self.busy = False
            self._stop_spinner()
            self._refresh_header()
            self._refresh_status()
            if assistant_full.strip():
                self._session_messages.append({"role": "assistant", "content": assistant_full, "ts": _now()})
                self._system(f"done {ICONS.middle_dot} {elapsed:.1f}s {ICONS.middle_dot} {_fmt_tokens(token_count)} tok")
            else:
                self._system("(no response)")
            self._save_session()
            self.prompt_input.focus_input()

    async def _simulate_stream(self, placeholder: MessageWidget):
        if not placeholder:
            return
        self.spinner.mode = "responding"
        self.spinner.thinking = False
        responses = [
            "Hello! I'm FoxCode, your AI coding assistant.\n\n",
            "I can help you write, read, and refactor code.\n\n",
            "Try asking me to:\n",
            f"{ICONS.bullet} Explain a codebase\n",
            f"{ICONS.bullet} Write unit tests\n",
            f"{ICONS.bullet} Refactor a function\n\n",
            "What would you like to work on?",
        ]
        for chunk in responses:
            for word in chunk.split(" "):
                await asyncio.sleep(0.03)
                placeholder.append_text(word + " ")
                self.spinner.update_tokens(len(placeholder._body) // 4)
                self._scroll_end()
