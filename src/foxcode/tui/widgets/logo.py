"""Logo widgets - 1:1 port of doge-code LogoV2, Clawd, AnimatedClawd, CondensedLogo.

All ASCII art and animations ported exactly from the TypeScript originals.
"""

from __future__ import annotations

import math
import random
import time
from pathlib import Path

from rich.style import Style
from rich.text import Text
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from foxcode.tui.theme import get_theme

# Mascot ASCII art lives in standalone .txt files so it can be edited without
# touching code. See src/foxcode/tui/assets/mascot/.
ART_DIR = Path(__file__).parent.parent / "assets" / "mascot"

# Each Clawd pose is stored as its own .txt file (see assets/mascot/).
POSE_FILES = {
    "default": "clawd.txt",
    "look-left": "clawd_look_left.txt",
    "look-right": "clawd_look_right.txt",
    "arms-up": "clawd_arms_up.txt",
}


def _load_art(filename: str) -> str:
    """Read a mascot art .txt file (UTF-8). Returns '' on failure."""
    try:
        return (ART_DIR / filename).read_text(encoding="utf-8")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Clawd - ASCII mascot (fox)
# Ported from doge-code/src/components/LogoV2/Clawd.tsx
# Pose system: default, arms-up, look-left, look-right
# ---------------------------------------------------------------------------


def render_clawd(pose: str = "default", theme_name: str = "dark") -> Text:
    """Render the Clawd mascot as 3 rows of Rich Text."""
    theme = get_theme(theme_name)
    body = getattr(theme, "clawd_body", "#ffd56b")

    body_style = Style(color=body)

    # All poses are edited via standalone .txt files; this function only
    # (re)applies the brand colouring to the loaded art.
    filename = POSE_FILES.get(pose, POSE_FILES["default"])
    art = _load_art(filename).rstrip("\n")
    lines: list[Text] = []
    for line_text in art.split("\n"):
        line = Text()
        for ch in line_text:
            if ch == " ":
                line.append(" ")
            else:
                line.append(ch, style=body_style)
        lines.append(line)
    return Text("\n").join(lines)

    p = POSES.get(pose, POSES["default"])
    lines = []

    r1 = Text()
    r1.append(p["r1L"], style=body_style)
    r1.append(p["r1E"], style=body_bg_style)
    r1.append(p["r1R"], style=body_style)
    lines.append(r1)

    r2 = Text()
    r2.append(p["r2L"], style=body_style)
    r2.append("\u2588\u2588\u2588\u2588\u2588", style=body_bg_style)
    r2.append(p["r2R"], style=body_style)
    lines.append(r2)

    r3 = Text(FEET, style=body_style)
    lines.append(r3)

    return Text("\n").join(lines)


# ---------------------------------------------------------------------------
# AnimatedClawd - Click-triggered animation
# Ported from doge-code/src/components/LogoV2/AnimatedClawd.tsx
# Animations: JUMP_WAVE (720ms), LOOK_AROUND (660ms)
# ---------------------------------------------------------------------------

CLAWD_HEIGHT = 3
FRAME_MS = 0.060  # 60ms


def _hold(pose: str, offset: int, frames: int) -> list[tuple[str, int]]:
    return [(pose, offset)] * frames


JUMP_WAVE: list[tuple[str, int]] = (
    _hold("default", 1, 2)
    + _hold("arms-up", 0, 3)
    + _hold("default", 0, 1)
    + _hold("default", 1, 2)
    + _hold("arms-up", 0, 3)
    + _hold("default", 0, 1)
)

LOOK_AROUND: list[tuple[str, int]] = (
    _hold("look-right", 0, 5)
    + _hold("look-left", 0, 5)
    + _hold("default", 0, 1)
)

ANIMATIONS = [JUMP_WAVE, LOOK_AROUND]


class AnimatedClawd(Static):
    """Clickable animated Clawd mascot."""

    def __init__(self):
        super().__init__()
        self._frame_idx = -1
        self._anim: list[tuple[str, int]] = []
        self._anim_start = 0.0

    def on_mount(self):
        self.set_interval(FRAME_MS, self._tick)

    def _tick(self):
        if self._frame_idx < 0:
            return
        elapsed = time.time() - self._anim_start
        idx = int(elapsed / FRAME_MS)
        if idx >= len(self._anim):
            self._frame_idx = -1
            self.refresh()
            return
        self._frame_idx = idx
        self.refresh()

    def action_click(self):
        self._anim = random.choice(ANIMATIONS)
        self._frame_idx = 0
        self._anim_start = time.time()

    def render(self):
        if self._frame_idx < 0:
            return render_clawd("default")
        pose, offset = self._anim[self._frame_idx]
        t = render_clawd(pose)
        if offset > 0:
            return Text("\n" * offset + t.plain)
        return t


# ---------------------------------------------------------------------------
# CondensedLogo - Compact header bar
# Ported from doge-code/src/components/LogoV2/CondensedLogo.tsx
# ---------------------------------------------------------------------------


class CondensedLogo(Static):
    """Compact header showing Clawd + FoxCode + model info."""

    def __init__(
        self,
        version: str = "0.1.5",
        model: str = "default",
        mode: str = "yolo",
        cwd: str = "~",
        agent_name: str = "",
    ):
        super().__init__()
        self._version = version
        self._model = model
        self._mode = mode
        self._cwd = cwd
        self._agent_name = agent_name

    def render(self):
        theme = get_theme()
        lines: list[Text] = []

        title = Text()
        title.append("  ", style=Style(color=getattr(theme, "clawd_body", "#ffd56b")))
        title.append(
            render_clawd("default").plain.replace("\n", " "),
            style=Style(color=getattr(theme, "clawd_body", "#ffd56b")),
        )
        title.append(" ", style=Style(color=getattr(theme, "clawd_body", "#ffd56b")))
        title.append("FoxCode", style=Style(bold=True, color=getattr(theme, "fox", "#ffd56b")))
        title.append(
            f" v{self._version}",
            style=Style(dim=True, color=getattr(theme, "inactive", "#7d8590")),
        )
        lines.append(title)

        info = Text()
        info.append(
            f"{self._model} \u00b7 {self._mode}",
            style=Style(dim=True, color=getattr(theme, "subtle", "#545d68")),
        )
        agent_part = f" @{self._agent_name} \u00b7 " if self._agent_name else " "
        info.append(
            f"{agent_part}{self._cwd}",
            style=Style(dim=True, color=getattr(theme, "subtle", "#545d68")),
        )
        lines.append(info)

        return Text("\n").join(lines)


# ---------------------------------------------------------------------------
# WelcomeBanner - Full welcome screen art
# Ported from doge-code/src/components/LogoV2/WelcomeV2.tsx
# ---------------------------------------------------------------------------


WELCOME_WIDTH = 58


def render_welcome_border(theme_name: str = "dark") -> Text:
    """Render the welcome border with fox brand."""
    theme = get_theme(theme_name)
    fox = getattr(theme, "fox", "#ffd56b")
    inactive = getattr(theme, "inactive", "#7d8590")

    t = Text()
    t.append("\u2026" * (WELCOME_WIDTH - 26), style=Style(color=inactive))
    t.append(" ", style=Style(color=inactive))
    t.append("FoxCode", style=Style(color=fox, bold=True))
    t.append(" ", style=Style(color=inactive))
    t.append("v0.1.5", style=Style(dim=True, color=inactive))
    t.append(" ", style=Style(color=inactive))
    t.append("\u2026" * (WELCOME_WIDTH - 14), style=Style(color=inactive))
    return t


def render_welcome_art(theme_name: str = "dark") -> Text:
    """Full welcome ASCII art with Clawd and fox-branded design.

    The art itself is loaded from welcome.txt (editable without touching
    code); this function only (re)applies the brand colouring.
    """
    theme = get_theme(theme_name)
    fox = getattr(theme, "fox", "#ffd56b")
    body = getattr(theme, "clawd_body", "#ffd56b")
    bg = getattr(theme, "clawd_background", "#0d1117")
    inactive = getattr(theme, "inactive", "#7d8590")
    txt = getattr(theme, "text", "#e6edf3")

    fox_style = Style(color=fox, bold=True)
    body_style = Style(color=body)
    body_bg = Style(color=body, bgcolor=bg)
    dim = Style(color=inactive)
    text_style = Style(color=txt)

    art = _load_art("welcome.txt").rstrip("\n")
    lines: list[Text] = []
    for line_text in art.split("\n"):
        line = Text()
        for ch in line_text:
            if ch == "*":
                line.append("*", style=fox_style)
            elif ch in "\u2588\u2589\u2599\u2591\u2593\u2590":
                line.append(ch, style=body_bg)
            elif ch == "\u259c":
                line.append(ch, style=body_style)
            else:
                line.append(ch, style=text_style)
        lines.append(line)

    return Text("\n").join(lines)


def render_welcome_full(theme_name: str = "dark") -> Text:
    """Full welcome screen with border, art, and greeting."""
    art = render_welcome_art(theme_name)
    return art


class WelcomeBanner(Static):
    """Full welcome banner widget shown at session start."""

    def render(self):
        return render_welcome_full()
