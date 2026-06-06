"""FoxCode TUI - Lightweight terminal UI built on Textual.

Inspired by opencode and uv: minimal, fast, low memory.

Usage:
    from foxcode.tui import run_tui
    run_tui(agent)
"""

from foxcode.tui.app import FoxCodeApp, run_tui

__all__ = ["FoxCodeApp", "run_tui"]
