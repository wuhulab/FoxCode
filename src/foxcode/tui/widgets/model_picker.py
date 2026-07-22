"""ModelPickerScreen - Modal screen for selecting an AI model.

Fetches available models from a remote API and presents them as a
selectable list.  On selection it dismisses with the chosen model id.
"""

from __future__ import annotations

import logging

import httpx
from textual import on
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, ListItem, ListView, Static

logger = logging.getLogger(__name__)

BASE_URL = "https://fai.shunx.top"
API_URL = f"{BASE_URL}/v1"
API_KEY = "sk-C4Dy0S5OFKJ7QoPu8erQc2tTDklW2fBIry34CA8tmFcC1tGr"


class ModelPickerScreen(ModalScreen):
    """Modal that fetches models and lets the user pick one."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+c", "cancel", "Cancel"),
    ]

    def __init__(self):
        super().__init__()
        self._models: list[str] = []
        self._loading = True
        self._error: str | None = None

    def compose(self):
        with Vertical(classes="model-picker"):
            yield Static("FoxCode Free - 选择模型", classes="title")
            if self._loading:
                yield Static("正在获取可用模型列表...", id="status")
            if self._error:
                yield Static(f"[red]{self._error}[/red]", id="error")
            yield ListView(id="model-list", classes="model-list")
            yield Label("方向键导航 · Enter 选择 · Esc 取消", classes="hint")

    def on_mount(self):
        self._fetch_models()

    def _fetch_models(self):
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(
                    f"{API_URL}/models",
                    headers={"Authorization": f"Bearer {API_KEY}"},
                )
                resp.raise_for_status()
                data = resp.json()
                models = [m["id"] for m in data.get("data", []) if m.get("id")]
                models.sort()
                self._models = models
                list_view = self.query_one("#model-list", ListView)
                list_view.clear()
                for m in models:
                    list_view.append(ListItem(Label(m)))
                self.query_one("#status", Static).remove()
        except Exception as e:
            logger.error(f"获取模型列表失败: {e}", exc_info=True)
            self._error = f"获取模型列表失败: {e}"
            status = self.query_one("#status", Static)
            status.update(f"[red]{self._error}[/red]")

    @on(ListView.Selected)
    def _on_selected(self, event: ListView.Selected):
        list_view = self.query_one("#model-list", ListView)
        idx = list_view.index
        if idx is not None and 0 <= idx < len(self._models):
            self.dismiss(self._models[idx])

    def action_cancel(self) -> None:
        self.dismiss(None)
