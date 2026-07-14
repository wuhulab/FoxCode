"""CostDialog - Cost threshold warning dialog.

Ported from doge-code cost tracking UI.
"""

from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Button, Static

from foxcode.tui.design_system.progress import ProgressBar
from foxcode.tui.theme import get_theme


class CostWarning(Vertical):
    """Displays a cost threshold warning."""

    def __init__(self, cost: float = 0.0, threshold: float = 0.0):
        super().__init__()
        self._cost = cost
        self._threshold = threshold

    def compose(self):
        theme = get_theme()
        yield Static("Cost Warning", classes="title")
        yield Static(
            f"Current cost: ${self._cost:.4f} / ${self._threshold:.4f} threshold"
        )
        yield ProgressBar(progress=self._cost, total=self._threshold)
        with Vertical(classes="dialog-actions"):
            yield Button("Continue", id="cost-continue", variant="primary")
            yield Button("Stop", id="cost-stop")
