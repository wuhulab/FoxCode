"""FoxCode TUI - Textual app.

A lightweight, opencode/uv-inspired terminal UI for FoxCode. Built on
Textual so it stays snappy and uses very little memory (no browser,
no Monaco, no embedded webview).

Layout
------
::

    ┌─ Header ─────────────────────────────────────────────────┐
    │ 🦊 FoxCode  model · mode · tokens                        │
    ├──────────┬───────────────────────────────────────────────┤
    │ Sessions │  Chat (markdown, scrollable)                 │
    │  · ...   │                                               │
    │          │                                               │
    │          ├───────────────────────────────────────────────┤
    │          │  Input (single line)               [ Send ]   │
    ├──────────┴───────────────────────────────────────────────┤
    │ Enter send · Ctrl+L clear · F1 help · Ctrl+C quit       │
    └──────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, Optional

from rich.markdown import Markdown
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
)

from foxcode import __version__
from foxcode.core.agent import FoxCodeAgent
from foxcode.core.config import Config
from foxcode.core.session import Session
from foxcode.tui.theme import LOGO_COMPACT, Palette, status_color


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _format_tokens(n: int) -> str:
    """Format a token count compactly (1234 -> 1.2k)."""
    if n < 1000:
        return str(n)
    if n < 10_000:
        return f"{n / 1000:.1f}k"
    if n < 1_000_000:
        return f"{n // 1000}k"
    return f"{n / 1_000_000:.1f}m"


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


# --------------------------------------------------------------------------- #
# Widgets                                                                     #
# --------------------------------------------------------------------------- #


class Banner(Static):
    """Welcome banner shown at the start of a session."""

    def compose(self) -> ComposeResult:
        yield Static(LOGO_COMPACT, classes="logo")
        yield Static(
            f"v{__version__} · ask me to read, write, or run code · press F1 for shortcuts",
            classes="tag",
        )


class Message(Static):
    """A single chat message with a role label and markdown body."""

    DEFAULT_CSS = ""

    def __init__(self, role: str, body: str = "", *, thinking: bool = False) -> None:
        classes = f"message --{role}"
        if thinking:
            classes += " --thinking"
        super().__init__(classes=classes)
        self.role = role
        self._body_text = body
        self._thinking = thinking
        self._body: Optional[Static] = None
        self._mounted = False

    def compose(self) -> ComposeResult:
        yield Static(self._role_label(), classes="role")
        yield Static(self._render_body(self._body_text), classes="body", markup=False)

    def on_mount(self) -> None:
        self._mounted = True
        self._body = self.query_one(".body", Static)

    def _role_label(self) -> Text:
        icons = {"user": "›", "assistant": "🦊", "tool": "⚙", "system": "·"}
        icon = icons.get(self.role, "·")
        return Text(f"{icon} {self.role}", style="bold")

    def _render_body(self, body: str) -> Any:
        if not body:
            return Text("")
        if self.role in ("assistant", "tool") and not self._thinking:
            try:
                return Markdown(body, code_theme="monokai")
            except Exception:
                return Text(body)
        return Text(body)

    def append_text(self, chunk: str) -> None:
        """Append a streaming chunk to the body and re-render.

        Safe to call before the widget has fully mounted: the chunk is
        buffered in ``_body_text`` and a refresh is scheduled.
        """
        self._body_text += chunk
        if not self._mounted or self._body is None:
            self.call_after_refresh(self._flush_body)
            return
        self._flush_body()

    def _flush_body(self) -> None:
        if self._body is None:
            try:
                self._body = self.query_one(".body", Static)
            except Exception:  # noqa: BLE001
                return
        self._body.update(self._render_body(self._body_text))

    def finalize(self) -> None:
        """Switch out of 'thinking' state and render the final markdown."""
        self._thinking = False
        self.remove_class("--thinking")
        self._flush_body()


class ChatScroll(VerticalScroll):
    """Scrollable container for chat messages."""


class InputPanel(Vertical):
    """Single-line input + send button.

    Single-line keeps the interface opencode-simple. Users who need to
    paste long text can still use the model's file/context tools.
    """

    def compose(self) -> ComposeResult:
        yield Static(
            "Type your message · Enter to send · Esc to cancel",
            classes="hint",
        )
        self.prompt = Input(
            id="prompt",
            placeholder="Ask FoxCode anything…",
        )
        yield self.prompt
        with Horizontal(classes="input-row"):
            yield Static("", classes="hint")  # spacer
            self.send_btn = Button("▶ Send", id="send")
            yield self.send_btn


# --------------------------------------------------------------------------- #
# Sidebar                                                                     #
# --------------------------------------------------------------------------- #


class Sidebar(Vertical):
    """Sidebar with sessions list and a 'new session' button."""

    def compose(self) -> ComposeResult:
        yield Static("SESSIONS", classes="section")
        self.new_btn = Button("+  new session", id="new-session")
        yield self.new_btn
        self.sessions: ListView = ListView(id="sessions")
        yield self.sessions

    def refresh_sessions(self, sessions: list[dict[str, Any]], current_id: str) -> None:
        """Rebuild the sessions list.

        We deliberately do *not* set custom ``id=`` on ListItems because
        ``ListView.clear()`` is asynchronous (returns ``AwaitRemove``).
        Calling ``clear()`` then ``extend()`` in a sync method can leave
        the old nodes in the DOM for a tick and cause ``DuplicateIds``
        if explicit IDs are reused.  Storing the session id on a plain
        attribute sidesteps the issue entirely.
        """
        # Build the new items first.
        items: list[ListItem] = []
        for s in sessions[:20]:  # cap to last 20
            sid = s.get("session_id", "?")
            created = s.get("created_at", "")[:16]  # trim
            msgs = s.get("message_count", 0)
            label = Text()
            label.append(sid[:18], style="bold")
            label.append("\n")
            label.append(f"{created} · {msgs} msg", style="dim")
            item = ListItem(Static(label, markup=False))
            item.data_sid = sid  # type: ignore[attr-defined]
            if sid == current_id:
                item.add_class("--highlight")
            items.append(item)
        # Replace all children at once.  Even though clear() is async,
        # dropping the explicit ids means no DuplicateIds crash.
        self.sessions.clear()
        if items:
            self.sessions.extend(items)


# --------------------------------------------------------------------------- #
# Help modal                                                                  #
# --------------------------------------------------------------------------- #


class HelpModal(Vertical):
    """Small modal listing keyboard shortcuts."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape,question_mark", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
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
                ("F1 / ?", "this help"),
                ("Ctrl+C", "quit"),
            ]
            lines: list[Text] = []
            for key, desc in shortcuts:
                t = Text()
                t.append(f"  {key:<14}", style="bold #ff8c42")
                t.append(desc, style="#e6edf3")
                lines.append(t)
            yield Static(Text("\n").join(lines), classes="body", markup=False)
            yield Static("\nPress Esc to close", classes="keys")


# --------------------------------------------------------------------------- #
# Main app                                                                    #
# --------------------------------------------------------------------------- #


class FoxCodeApp(App):
    """The FoxCode Textual app."""

    CSS_PATH = "styles.tcss"
    TITLE = "FoxCode"
    SUB_TITLE = ""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+l", "clear_chat", "Clear", show=True),
        Binding("ctrl+n", "new_session", "New", show=True),
        Binding("ctrl+s", "save_session", "Save", show=True),
        Binding("ctrl+b", "toggle_sidebar", "Sidebar", show=True),
        Binding("ctrl+t", "cycle_mode", "Mode", show=True),
        Binding("f1,question_mark", "help", "Help", show=True),
    ]

    sidebar_visible: reactive[bool] = reactive(True)
    busy: reactive[bool] = reactive(False)

    def __init__(self, agent: FoxCodeAgent, config: Config) -> None:
        super().__init__()
        self.agent = agent
        self.config = config
        self._current_session_id: str = ""
        self._run_mode_index: int = 0
        self._run_modes: tuple[str, ...] = ("yolo", "plan", "accept_edits")

    # ------------------------------------------------------------------ #
    # Layout                                                              #
    # ------------------------------------------------------------------ #

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            self.sidebar = Sidebar(id="sidebar")
            yield self.sidebar
            with Vertical(id="main"):
                self.chat = ChatScroll(id="chat")
                yield self.chat
                self.input_panel = InputPanel(id="input-panel")
                yield self.input_panel
        yield Footer()

    # ------------------------------------------------------------------ #
    # Lifecycle                                                           #
    # ------------------------------------------------------------------ #

    async def on_mount(self) -> None:
        """Initialize agent, restore or create session, draw welcome."""
        try:
            await self.agent.initialize()
        except Exception as exc:  # noqa: BLE001
            self._system(f"Failed to initialize agent: {exc}")

        self._current_session_id = self.agent.session.session_id
        self._refresh_sessions()
        self._refresh_header()
        self._show_banner()
        self._system(f"Session {self._current_session_id[:8]} ready · cwd {Path.cwd()}")
        self.query_one("#prompt", Input).focus()

    # ------------------------------------------------------------------ #
    # Header                                                              #
    # ------------------------------------------------------------------ #

    def _refresh_header(self) -> None:
        try:
            usage = self.agent.get_token_usage()
            total = _format_tokens(int(usage.get("total_tokens", 0)))
        except Exception:  # noqa: BLE001
            total = "0"
        mode = self.config.run_mode.value
        model = self.config.model.model_name
        sub = f"{model} · {mode} · {total} tok"
        self.sub_title = sub
        # Color the subtitle by mode (success / warn / info).
        try:
            header = self.query_one(Header)
            subtitle = header.query_one("#subtitle", Static)
            subtitle.styles.color = status_color(mode)
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------ #
    # Chat rendering                                                      #
    # ------------------------------------------------------------------ #

    def _show_banner(self) -> None:
        self.chat.mount(Banner())

    def _system(self, text: str) -> None:
        """Append a system message."""
        msg = Message("system", text)
        self.chat.mount(msg)
        self._scroll_end()

    def _user(self, text: str) -> None:
        self.chat.mount(Message("user", text))
        self._scroll_end()

    def _assistant_thinking(self) -> Message:
        msg = Message("assistant", "", thinking=True)
        msg._body_text = ""
        self.chat.mount(msg)
        self._scroll_end()
        return msg

    def _scroll_end(self) -> None:
        self.chat.scroll_end(animate=False)

    # ------------------------------------------------------------------ #
    # Sessions                                                            #
    # ------------------------------------------------------------------ #

    def _refresh_sessions(self) -> None:
        try:
            sessions = Session.list_sessions(self.config) or []
        except Exception:  # noqa: BLE001
            sessions = []
        self.sidebar.refresh_sessions(sessions, self._current_session_id)

    # ------------------------------------------------------------------ #
    # Events                                                              #
    # ------------------------------------------------------------------ #

    @on(Input.Submitted, "#prompt")
    def _on_submit(self, _event: Input.Submitted) -> None:
        self.action_send()

    @on(Button.Pressed, "#send")
    def _on_send_click(self, _event: Button.Pressed) -> None:
        self.action_send()

    @on(Button.Pressed, "#new-session")
    def _on_new_click(self, _event: Button.Pressed) -> None:
        self.action_new_session()

    @on(ListView.Selected, "#sessions")
    def _on_session_selected(self, event: ListView.Selected) -> None:
        item = event.item
        sid = getattr(item, "data_sid", "")
        if sid:
            self._load_session(sid)

    # ------------------------------------------------------------------ #
    # Actions                                                             #
    # ------------------------------------------------------------------ #

    def action_send(self) -> None:
        if self.busy:
            return
        prompt = self.query_one("#prompt", Input)
        text = prompt.value.strip()
        if not text:
            return
        prompt.value = ""
        self._user(text)
        self.busy = True
        self.query_one("#send", Button).disabled = True
        self._stream_response(text)

    def action_clear_chat(self) -> None:
        self.chat.remove_children()
        self._show_banner()
        self._system("Chat cleared")

    def action_new_session(self) -> None:
        try:
            new = self.agent.session
            new.save()
            self.agent.session = Session(self.config)
            self._current_session_id = self.agent.session.session_id
            self._refresh_sessions()
            self._refresh_header()
            self.action_clear_chat()
            self._system(f"Started new session {self._current_session_id[:8]}")
        except Exception as exc:  # noqa: BLE001
            self._system(f"Could not start new session: {exc}")

    def action_save_session(self) -> None:
        try:
            self.agent.session.save()
            self._refresh_sessions()
            self._system(f"Saved session {self._current_session_id[:8]}")
        except Exception as exc:  # noqa: BLE001
            self._system(f"Save failed: {exc}")

    def action_toggle_sidebar(self) -> None:
        self.sidebar_visible = not self.sidebar_visible
        self.sidebar.display = self.sidebar_visible

    def action_cycle_mode(self) -> None:
        self._run_mode_index = (self._run_mode_index + 1) % len(self._run_modes)
        new_mode = self._run_modes[self._run_mode_index]
        try:
            from foxcode.core.config import RunMode

            self.config.run_mode = RunMode(new_mode)
        except Exception:  # noqa: BLE001
            self.config.run_mode = new_mode
        self._refresh_header()
        self._system(f"Mode → {new_mode}")

    def action_help(self) -> None:
        self.push_screen(_HelpScreen())

    # ------------------------------------------------------------------ #
    # Streaming                                                           #
    # ------------------------------------------------------------------ #

    def _stream_response(self, user_input: str) -> None:
        """Spawn a worker that streams the assistant reply."""
        self._stream_worker(user_input)

    @work(exclusive=True, group="chat")
    async def _stream_worker(self, user_input: str) -> None:
        placeholder = self._assistant_thinking()
        full = ""
        started = time.time()
        try:
            async for chunk in self.agent.chat(user_input):
                if not chunk:
                    continue
                full += chunk
                placeholder.append_text(chunk)
                self._scroll_end()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            placeholder.append_text(f"\n\n[error] {exc}")
            self._system(f"Error: {exc}")
        finally:
            placeholder.finalize()
            elapsed = time.time() - started
            self.busy = False
            self.query_one("#send", Button).disabled = False
            self._refresh_header()
            self._refresh_sessions()
            if not full:
                self._system("(no response)")
            else:
                self._system(f"done · {elapsed:.1f}s")

    # ------------------------------------------------------------------ #
    # Session loading                                                     #
    # ------------------------------------------------------------------ #

    def _load_session(self, session_id: str) -> None:
        try:
            self.agent.load_session(session_id)
            self._current_session_id = session_id
            self.action_clear_chat()
            self._system(f"Loaded session {session_id[:8]}")
            # Replay prior messages
            convo = self.agent.session.conversation
            for m in convo[-40:]:
                role = getattr(m, "role", None)
                content = getattr(m, "content", "")
                if not content:
                    continue
                if role == "user":
                    self._user(content if isinstance(content, str) else str(content))
                elif role == "assistant":
                    self.chat.mount(
                        Message("assistant", content if isinstance(content, str) else str(content))
                    )
            self._scroll_end()
            self._refresh_header()
        except Exception as exc:  # noqa: BLE001
            self._system(f"Could not load session: {exc}")


class _HelpScreen(Vertical):
    """Wraps HelpModal in a screen-like container."""

    DEFAULT_CSS = """
    _HelpScreen {
        align: center middle;
        background: #0d1117 80%;
    }
    """

    def compose(self) -> ComposeResult:
        yield HelpModal()

    def on_mount(self) -> None:
        self.styles.layer = "overlay"
        self.can_focus = True
        self.focus()

    def action_dismiss(self) -> None:
        self.app.pop_screen()


# --------------------------------------------------------------------------- #
# Public entry                                                                #
# --------------------------------------------------------------------------- #


def run_tui(agent: FoxCodeAgent, config: Optional[Config] = None) -> None:
    """Launch the FoxCode TUI.

    Args:
        agent: An (optionally uninitialized) ``FoxCodeAgent`` instance.
        config: Optional config override; falls back to ``agent.config``.
    """
    cfg = config or agent.config
    app = FoxCodeApp(agent, cfg)
    app.run()
