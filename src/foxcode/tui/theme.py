"""Comprehensive theme system - 1:1 port of doge-code theme with 6 themes.

Brand color: #ffd56b (warm gold) per user spec.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class Theme:
    autoAccept: str = "#ffd56b"
    bashBorder: str = "#58a6ff"
    fox: str = "#ffd56b"
    foxShimmer: str = "#ffe18c"
    foxBlue: str = "#58a6ff"
    foxBlueShimmer: str = "#79c0ff"
    permission: str = "#ffd56b"
    permissionShimmer: str = "#ffe18c"
    planMode: str = "#d29922"
    ide: str = "#58a6ff"
    promptBorder: str = "#ffd56b"
    promptBorderShimmer: str = "#ffe18c"
    text: str = "#e6edf3"
    inverseText: str = "#0d1117"
    inactive: str = "#7d8590"
    inactiveShimmer: str = "#8b949e"
    subtle: str = "#545d68"
    suggestion: str = "#7d8590"
    remember: str = "#ffd56b"
    background: str = "#0d1117"
    success: str = "#3fb950"
    error: str = "#f85149"
    warning: str = "#d29922"
    merged: str = "#a371f7"
    warningShimmer: str = "#e3b341"
    diffAdded: str = "#3fb950"
    diffRemoved: str = "#f85149"
    diffAddedDimmed: str = "#1b4a23"
    diffRemovedDimmed: str = "#4a1b1b"
    diffAddedWord: str = "#2ea043"
    diffRemovedWord: str = "#da3633"
    red_FOR_SUBAGENTS_ONLY: str = "#f85149"
    blue_FOR_SUBAGENTS_ONLY: str = "#58a6ff"
    green_FOR_SUBAGENTS_ONLY: str = "#3fb950"
    yellow_FOR_SUBAGENTS_ONLY: str = "#d29922"
    purple_FOR_SUBAGENTS_ONLY: str = "#a371f7"
    orange_FOR_SUBAGENTS_ONLY: str = "#ffd56b"
    pink_FOR_SUBAGENTS_ONLY: str = "#db61a2"
    cyan_FOR_SUBAGENTS_ONLY: str = "#39c5cf"
    professionalBlue: str = "#1f6feb"
    chromeYellow: str = "#e3b341"
    clawd_body: str = "#ffd56b"
    clawd_background: str = "#0d1117"
    userMessageBackground: str = "#161b22"
    userMessageBackgroundHover: str = "#1c2128"
    messageActionsBackground: str = "#1c2128"
    selectionBg: str = "#1f6feb"
    bashMessageBackgroundColor: str = "#0d1117"
    memoryBackgroundColor: str = "#161b22"
    rate_limit_fill: str = "#ffd56b"
    rate_limit_empty: str = "#30363d"
    fastMode: str = "#ffd56b"
    fastModeShimmer: str = "#ffe18c"
    briefLabelYou: str = "#79c0ff"
    briefLabelFox: str = "#ffd56b"
    rainbow_red: str = "#f85149"
    rainbow_orange: str = "#ffd56b"
    rainbow_yellow: str = "#d29922"
    rainbow_green: str = "#3fb950"
    rainbow_blue: str = "#58a6ff"
    rainbow_indigo: str = "#a371f7"
    rainbow_violet: str = "#db61a2"
    rainbow_red_shimmer: str = "#f97583"
    rainbow_orange_shimmer: str = "#ffe18c"
    rainbow_yellow_shimmer: str = "#e3b341"
    rainbow_green_shimmer: str = "#56d364"
    rainbow_blue_shimmer: str = "#79c0ff"
    rainbow_indigo_shimmer: str = "#bc8cff"
    rainbow_violet_shimmer: str = "#e28ad8"


LIGHT: Theme = Theme(
    autoAccept="#ffd56b",
    bashBorder="#0969da",
    fox="#ffd56b",
    foxShimmer="#ffe18c",
    foxBlue="#0969da",
    foxBlueShimmer="#2188ff",
    permission="#ffd56b",
    permissionShimmer="#ffe18c",
    planMode="#9a6700",
    ide="#0969da",
    promptBorder="#ffd56b",
    promptBorderShimmer="#ffe18c",
    text="#1f2328",
    inverseText="#ffffff",
    inactive="#656d76",
    inactiveShimmer="#6e7681",
    subtle="#8c959f",
    suggestion="#656d76",
    remember="#ffd56b",
    background="#ffffff",
    success="#1a7f37",
    error="#cf222e",
    warning="#9a6700",
    merged="#8250df",
    warningShimmer="#bb8000",
    diffAdded="#1a7f37",
    diffRemoved="#cf222e",
    diffAddedDimmed="#dafbe1",
    diffRemovedDimmed="#ffebe9",
    diffAddedWord="#abf2bc",
    diffRemovedWord="#ff8182",
    red_FOR_SUBAGENTS_ONLY="#cf222e",
    blue_FOR_SUBAGENTS_ONLY="#0969da",
    green_FOR_SUBAGENTS_ONLY="#1a7f37",
    yellow_FOR_SUBAGENTS_ONLY="#9a6700",
    purple_FOR_SUBAGENTS_ONLY="#8250df",
    orange_FOR_SUBAGENTS_ONLY="#ffd56b",
    pink_FOR_SUBAGENTS_ONLY="#bf3989",
    cyan_FOR_SUBAGENTS_ONLY="#1b7c83",
    professionalBlue="#0969da",
    chromeYellow="#bb8000",
    clawd_body="#ffd56b",
    clawd_background="#ffffff",
    userMessageBackground="#f6f8fa",
    userMessageBackgroundHover="#eaeef2",
    messageActionsBackground="#eaeef2",
    selectionBg="#0969da",
    bashMessageBackgroundColor="#ffffff",
    memoryBackgroundColor="#f6f8fa",
    rate_limit_fill="#ffd56b",
    rate_limit_empty="#d0d7de",
    fastMode="#ffd56b",
    fastModeShimmer="#ffe18c",
    briefLabelYou="#0969da",
    briefLabelFox="#ffd56b",
    rainbow_red="#cf222e",
    rainbow_orange="#ffd56b",
    rainbow_yellow="#9a6700",
    rainbow_green="#1a7f37",
    rainbow_blue="#0969da",
    rainbow_indigo="#8250df",
    rainbow_violet="#bf3989",
    rainbow_red_shimmer="#ff8182",
    rainbow_orange_shimmer="#ffe18c",
    rainbow_yellow_shimmer="#bb8000",
    rainbow_green_shimmer="#56d364",
    rainbow_blue_shimmer="#2188ff",
    rainbow_indigo_shimmer="#bc8cff",
    rainbow_violet_shimmer="#e28ad8",
)

DARK_ANSI: Theme = Theme(
    fox="ansi:yellow",
    foxShimmer="ansi:yellow",
    foxBlue="ansi:blue",
    foxBlueShimmer="ansi:blue",
    permission="ansi:yellow",
    permissionShimmer="ansi:yellow",
    promptBorder="ansi:yellow",
    promptBorderShimmer="ansi:yellow",
    remember="ansi:yellow",
    clawd_body="ansi:yellow",
    briefLabelFox="ansi:yellow",
    fastMode="ansi:yellow",
    fastModeShimmer="ansi:yellow",
    rate_limit_fill="ansi:yellow",
    autoAccept="ansi:yellow",
    orange_FOR_SUBAGENTS_ONLY="ansi:yellow",
    rainbow_orange="ansi:yellow",
    rainbow_orange_shimmer="ansi:yellow",
    rainbow_red="ansi:red",
    rainbow_red_shimmer="ansi:red",
    rainbow_yellow="ansi:yellow",
    rainbow_yellow_shimmer="ansi:yellow",
    rainbow_green="ansi:green",
    rainbow_green_shimmer="ansi:green",
    rainbow_blue="ansi:blue",
    rainbow_blue_shimmer="ansi:blue",
    rainbow_indigo="ansi:magenta",
    rainbow_indigo_shimmer="ansi:magenta",
    rainbow_violet="ansi:magenta",
    rainbow_violet_shimmer="ansi:magenta",
    red_FOR_SUBAGENTS_ONLY="ansi:red",
    blue_FOR_SUBAGENTS_ONLY="ansi:blue",
    green_FOR_SUBAGENTS_ONLY="ansi:green",
    yellow_FOR_SUBAGENTS_ONLY="ansi:yellow",
    purple_FOR_SUBAGENTS_ONLY="ansi:magenta",
    pink_FOR_SUBAGENTS_ONLY="ansi:magenta",
    cyan_FOR_SUBAGENTS_ONLY="ansi:cyan",
    success="ansi:green",
    error="ansi:red",
    warning="ansi:yellow",
    merged="ansi:magenta",
    warningShimmer="ansi:yellow",
    diffAdded="ansi:green",
    diffRemoved="ansi:red",
    diffAddedDimmed="ansi:green",
    diffRemovedDimmed="ansi:red",
    diffAddedWord="ansi:green",
    diffRemovedWord="ansi:red",
    text="ansi:white",
    inverseText="ansi:black",
    inactive="ansi:bright-black",
    inactiveShimmer="ansi:bright-black",
    subtle="ansi:bright-black",
    suggestion="ansi:bright-black",
    background="ansi:black",
    bashBorder="ansi:blue",
    planMode="ansi:yellow",
    ide="ansi:blue",
    professionalBlue="ansi:blue",
    chromeYellow="ansi:yellow",
    clawd_background="ansi:black",
    userMessageBackground="ansi:black",
    userMessageBackgroundHover="ansi:black",
    messageActionsBackground="ansi:black",
    selectionBg="ansi:blue",
    bashMessageBackgroundColor="ansi:black",
    memoryBackgroundColor="ansi:black",
    rate_limit_empty="ansi:bright-black",
    briefLabelYou="ansi:blue",
)

LIGHT_ANSI: Theme = Theme(
    fox="ansi:yellow",
    foxShimmer="ansi:yellow",
    foxBlue="ansi:blue",
    foxBlueShimmer="ansi:blue",
    permission="ansi:yellow",
    permissionShimmer="ansi:yellow",
    promptBorder="ansi:yellow",
    promptBorderShimmer="ansi:yellow",
    remember="ansi:yellow",
    clawd_body="ansi:yellow",
    briefLabelFox="ansi:yellow",
    fastMode="ansi:yellow",
    fastModeShimmer="ansi:yellow",
    rate_limit_fill="ansi:yellow",
    autoAccept="ansi:yellow",
    orange_FOR_SUBAGENTS_ONLY="ansi:yellow",
    rainbow_orange="ansi:yellow",
    rainbow_orange_shimmer="ansi:yellow",
    rainbow_red="ansi:red",
    rainbow_red_shimmer="ansi:red",
    rainbow_yellow="ansi:yellow",
    rainbow_yellow_shimmer="ansi:yellow",
    rainbow_green="ansi:green",
    rainbow_green_shimmer="ansi:green",
    rainbow_blue="ansi:blue",
    rainbow_blue_shimmer="ansi:blue",
    rainbow_indigo="ansi:magenta",
    rainbow_indigo_shimmer="ansi:magenta",
    rainbow_violet="ansi:magenta",
    rainbow_violet_shimmer="ansi:magenta",
    red_FOR_SUBAGENTS_ONLY="ansi:red",
    blue_FOR_SUBAGENTS_ONLY="ansi:blue",
    green_FOR_SUBAGENTS_ONLY="ansi:green",
    yellow_FOR_SUBAGENTS_ONLY="ansi:yellow",
    purple_FOR_SUBAGENTS_ONLY="ansi:magenta",
    pink_FOR_SUBAGENTS_ONLY="ansi:magenta",
    cyan_FOR_SUBAGENTS_ONLY="ansi:cyan",
    success="ansi:green",
    error="ansi:red",
    warning="ansi:yellow",
    merged="ansi:magenta",
    warningShimmer="ansi:yellow",
    diffAdded="ansi:green",
    diffRemoved="ansi:red",
    diffAddedDimmed="ansi:green",
    diffRemovedDimmed="ansi:red",
    diffAddedWord="ansi:green",
    diffRemovedWord="ansi:red",
    text="ansi:black",
    inverseText="ansi:white",
    inactive="ansi:bright-black",
    inactiveShimmer="ansi:bright-black",
    subtle="ansi:bright-black",
    suggestion="ansi:bright-black",
    background="ansi:white",
    bashBorder="ansi:blue",
    planMode="ansi:yellow",
    ide="ansi:blue",
    professionalBlue="ansi:blue",
    chromeYellow="ansi:yellow",
    clawd_background="ansi:white",
    userMessageBackground="ansi:white",
    userMessageBackgroundHover="ansi:white",
    messageActionsBackground="ansi:white",
    selectionBg="ansi:blue",
    bashMessageBackgroundColor="ansi:white",
    memoryBackgroundColor="ansi:white",
    rate_limit_empty="ansi:bright-black",
    briefLabelYou="ansi:blue",
)

DARK_DALTONIZED: Theme = Theme(
    fox="#ff9933",
    foxShimmer="#ffb366",
    foxBlue="#6699ff",
    foxBlueShimmer="#88bbff",
    permission="#ff9933",
    permissionShimmer="#ffb366",
    promptBorder="#ff9933",
    promptBorderShimmer="#ffb366",
    remember="#ff9933",
    clawd_body="#ff9933",
    briefLabelFox="#ff9933",
    fastMode="#ff9933",
    fastModeShimmer="#ffb366",
    rate_limit_fill="#ff9933",
    autoAccept="#ff9933",
    orange_FOR_SUBAGENTS_ONLY="#ff9933",
    rainbow_orange="#ff9933",
    rainbow_orange_shimmer="#ffb366",
)

LIGHT_DALTONIZED: Theme = Theme(
    fox="#ff9933",
    foxShimmer="#ffb366",
    foxBlue="#4477dd",
    foxBlueShimmer="#6699ff",
    permission="#ff9933",
    permissionShimmer="#ffb366",
    promptBorder="#ff9933",
    promptBorderShimmer="#ffb366",
    remember="#ff9933",
    clawd_body="#ff9933",
    briefLabelFox="#ff9933",
    fastMode="#ff9933",
    fastModeShimmer="#ffb366",
    rate_limit_fill="#ff9933",
    autoAccept="#ff9933",
    orange_FOR_SUBAGENTS_ONLY="#ff9933",
    rainbow_orange="#ff9933",
    rainbow_orange_shimmer="#ffb366",
)


DARK = Theme()

THEMES: dict[str, Theme] = {
    "dark": DARK,
    "light": LIGHT,
    "dark-ansi": DARK_ANSI,
    "light-ansi": LIGHT_ANSI,
    "dark-daltonized": DARK_DALTONIZED,
    "light-daltonized": LIGHT_DALTONIZED,
}

DEFAULT_THEME = "dark"

_active_theme = DEFAULT_THEME


def get_theme(name: str = None) -> Theme:
    if name is None:
        name = _active_theme
    return THEMES.get(name, DARK)


def set_theme(name: str) -> Theme:
    global _active_theme
    if name in THEMES:
        _active_theme = name
    return get_theme()


def list_themes() -> list[str]:
    return list(THEMES.keys())


def resolve_color(token: str, theme_name: str = DEFAULT_THEME) -> str:
    val = getattr(get_theme(theme_name), token, token)
    if val.startswith("ansi:"):
        return val
    return val


# ---------------------------------------------------------------------------
# Color utilities
# ---------------------------------------------------------------------------

def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def interpolate_color(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (
        round(c1[0] + (c2[0] - c1[0]) * t),
        round(c1[1] + (c2[1] - c1[1]) * t),
        round(c1[2] + (c2[2] - c1[2]) * t),
    )


# ---------------------------------------------------------------------------
# Spinner verb list (ported from spinnerVerbs.ts, removed "Clauding")
# ---------------------------------------------------------------------------

SPINNER_VERBS: list[str] = [
    "Foxing",
    "Thinking",
    "Working",
    "Beboppin'",
    "Reticulating",
    "Computing",
    "Processing",
    "Crunching",
    "Calculating",
    "Compiling",
    "Indexing",
    "Optimizing",
    "Generating",
    "Analyzing",
    "Reasoning",
    "Searching",
    "Scanning",
    "Reading",
    "Writing",
    "Coding",
    "Debugging",
    "Testing",
    "Building",
    "Deploying",
    "Refactoring",
    "Rewriting",
    "Formatting",
    "Linting",
    "Transpiling",
    "Bundling",
    "Resolving",
    "Fetching",
    "Downloading",
    "Uploading",
    "Syncing",
    "Backing up",
    "Restoring",
    "Migrating",
    "Transforming",
    "Parsing",
    "Validating",
    "Checking",
    "Verifying",
    "Polishing",
    "Tweaking",
    "Tuning",
    "Preparing",
    "Organizing",
    "Planning",
    "Sketching",
    "Drafting",
    "Reviewing",
    "Summarizing",
    "Explaining",
    "Teaching",
    "Learning",
    "Improving",
    "Fixing",
    "Patching",
    "Updating",
    "Upgrading",
    "Installing",
    "Configuring",
    "Connecting",
    "Authenticating",
    "Authorizing",
    "Encrypting",
    "Decrypting",
    "Serializing",
    "Deserializing",
    "Caching",
    "Loading",
    "Rendering",
    "Painting",
    "Drawing",
    "Plotting",
    "Measuring",
    "Tracking",
    "Monitoring",
    "Listening",
    "Watching",
    "Waiting",
    "Dreaming",
    "Imagining",
    "Inventing",
    "Creating",
]

# Linux standard spinner frames
SPINNER_FRAMES = ["-", "\\", "|", "/"]

LOGO_COMPACT = "\u25b6 FoxCode"

LOGO_ASCII = r"""
   ______            __           __   __          __
  / ____/  __  __   / /_  ______ / /  / /   ____ _ / /_
 / /      / / / /  / __/ / ____/ __ \/ /   / __ `// __/
/ /___   / /_/ /  / /_  / /__ / /_/ / /___/ /_/ // /_
\____/   \__,_/   \__/  \___//_.___/_____/\__,_/ \__/
"""

STATUS_COLORS: dict[str, str] = {
    "build": "#d29922",
    "plan": "#58a6ff",
    "accept_edits": "#d29922",
    "work": "#3fb950",
}


def status_color(mode: str) -> str:
    return STATUS_COLORS.get(mode.lower(), "#3fb950")
