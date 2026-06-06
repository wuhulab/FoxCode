"""FoxCode TUI theme - inspired by opencode & uv.

A restrained, dark palette with a single warm accent (fox orange)
and plenty of whitespace. Everything below lives in the TCSS too;
this module is for runtime values (logo, status colors).
"""

from __future__ import annotations


class Palette:
    """Color tokens used by the TUI.

    Hex strings are friendly to both Rich and CSS. They mirror the
    variables defined in ``styles.tcss`` so previews match.
    """

    # Surfaces
    BG = "#0d1117"  # app background
    SURFACE = "#161b22"  # panels, sidebars
    ELEVATED = "#1c2128"  # hovered/active rows
    BORDER = "#30363d"  # subtle dividers
    BORDER_STRONG = "#484f58"

    # Text
    TEXT = "#e6edf3"  # primary
    MUTED = "#7d8590"  # secondary
    DIM = "#545d68"  # hints, placeholders

    # Brand
    ACCENT = "#ff8c42"  # fox orange
    ACCENT_SOFT = "#ffa866"
    ACCENT_BG = "#3a2418"  # tinted background for chips

    # Status
    SUCCESS = "#3fb950"
    WARNING = "#d29922"
    ERROR = "#f85149"
    INFO = "#58a6ff"

    # Roles
    USER = "#79c0ff"
    ASSISTANT = "#e6edf3"
    TOOL = "#a371f7"
    SYSTEM = "#7d8590"


LOGO = r"""
   __        __   ___    __  __          __
  /__`  /\/ | __|  |  |__) |  \    |__/ |__)
  .__/ /~~\| |    |  |  \)|__/    |  \ |  \
"""

LOGO_COMPACT = "🦊 FoxCode"

# Footer key hints, kept terse like opencode.
HINTS = [
    ("Enter", "send"),
    ("Shift+Enter", "newline"),
    ("Ctrl+L", "clear"),
    ("Ctrl+N", "new"),
    ("Ctrl+S", "save"),
    ("Ctrl+B", "sidebar"),
    ("F1", "help"),
    ("Ctrl+C", "quit"),
]


def status_color(mode: str) -> str:
    """Map a run-mode name to a status color."""
    mode = (mode or "").lower()
    if mode in {"yolo", "accept_edits"}:
        return Palette.WARNING
    if mode == "plan":
        return Palette.INFO
    return Palette.SUCCESS
