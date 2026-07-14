"""Public icon library for FoxCode TUI.

All icons are standard Unicode symbols (no emoji, no Nerd Font PUA).
Guaranteed to render in any UTF-8 terminal.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Icons:
    """Centralized icon definitions using standard Unicode codepoints."""

    # Brand
    fox: str = "\u25b6"          # ▶ BLACK RIGHT-POINTING TRIANGLE
    fox_logo: str = "\u25c6"     # ◆ BLACK DIAMOND

    # Role indicators
    user: str = "\u203a"         # › SINGLE RIGHT-POINTING ANGLE QUOTATION MARK
    assistant: str = "\u25b8"    # ▸ BLACK RIGHT-POINTING SMALL TRIANGLE
    tool: str = "\u2699"         # ⚙ GEAR
    system: str = "\u00b7"       # · MIDDLE DOT

    # Prompt
    prompt: str = "\u276f"       # ❯ HEAVY RIGHT-POINTING ANGLE QUOTATION MARK

    # Actions
    send: str = "\u25b6"         # ▶ BLACK RIGHT-POINTING TRIANGLE
    search: str = "\u2315"       # ⌕ TELEPHONE RECORDER
    plus: str = "+"              # + PLUS SIGN
    save: str = "\u2611"         # ☑ BALLOT BOX WITH CHECK
    clear: str = "\u2302"        # ⌂ HOUSE (used for clear/reset)
    help: str = "\u003f"         # ? QUESTION MARK
    close: str = "\u2717"        # ✗ BALLOT X
    sidebar: str = "\u2261"      # ≡ IDENTICAL TO (hamburger menu)
    mode: str = "\u21c4"         # ⇄ ARROWS TO BARRIER (cycle)
    new_session: str = "\u2295"  # ⊕ CIRCLED PLUS
    back: str = "\u2190"         # ← LEFTWARDS ARROW
    forward: str = "\u2192"      # → RIGHTWARDS ARROW

    # Status
    success: str = "\u2713"      # ✓ CHECK MARK
    error: str = "\u2717"        # ✗ BALLOT X
    warning: str = "\u26a0"      # ⚠ WARNING SIGN
    info: str = "\u24d8"         # ⓘ CIRCLED INFORMATION SOURCE
    bullet: str = "\u25cf"       # ● BLACK CIRCLE
    dot: str = "\u25e6"          # ◦ WHITE BULLET

    # Direction
    up: str = "\u2191"           # ↑ UPWARDS ARROW
    down: str = "\u2193"         # ↓ DOWNWARDS ARROW
    left: str = "\u2190"         # ← LEFTWARDS ARROW
    right: str = "\u2192"        # → RIGHTWARDS ARROW

    # Response
    indent: str = "\u23bf"       # ⎿ DENTISTRY SYMBOL LIGHT VERTICAL BOTTOM

    # Punctuation
    ellipsis: str = "\u2026"     # … HORIZONTAL ELLIPSIS
    middle_dot: str = "\u00b7"   # · MIDDLE DOT
    divider: str = "\u2500"      # ─ BOX DRAWINGS LIGHT HORIZONTAL
    tilde: str = "\u223c"        # ∼ TILDE OPERATOR


ICONS = Icons()
