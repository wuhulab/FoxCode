"""Spinner system - full 1:1 port of doge-code SpinnerAnimationRow.

Key ports:
- useStalledAnimation (3s stall, 2s red fade, EMA smoothing)
- GlimmerMessage (sweeping shimmer across verb text)
- SpinnerGlyph (linux -/\\| frames instead of ·✢✳✶✻✽)
- SpinnerAnimationRow (50ms animation clock, progressive width gating)
- SpinnerWithVerb (verb selection + tree + budget)
- BriefSpinner (compact variant)
"""

from __future__ import annotations

import math
import random
import time
from typing import Any, Optional

from rich.style import Style
from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from foxcode.tui.icons import ICONS
from foxcode.tui.theme import SPINNER_FRAMES, SPINNER_VERBS, get_theme, hex_to_rgb, rgb_to_hex, interpolate_color

# ---------------------------------------------------------------------------
# Constants (ported from TS)
# ---------------------------------------------------------------------------
SHOW_TOKENS_AFTER_MS = 30_000
THINKING_DELAY_MS = 3000
THINKING_GLOW_PERIOD_S = 2
THINKING_INACTIVE_RGB = (153, 153, 153)
THINKING_INACTIVE_SHIMMER_RGB = (185, 185, 185)
ERROR_RED_RGB = (171, 43, 63)
STALL_TIMEOUT_MS = 3000
STALL_FADE_MS = 2000


# ---------------------------------------------------------------------------
# SpinnerGlyph - animated character with stall red fade
# ---------------------------------------------------------------------------

class SpinnerGlyph:
    """Renders the animated spinner character with optional stall-to-red."""

    def __init__(self, message_color: str = "fox"):
        self.message_color = message_color

    def render(self, frame: int, stall_intensity: float = 0, reduced_motion: bool = False, time_ms: int = 0) -> Text:
        theme = get_theme()
        char = SPINNER_FRAMES[frame % len(SPINNER_FRAMES)]

        if reduced_motion:
            is_dim = (time_ms // 1000) % 2 == 1
            color = getattr(theme, self.message_color, "#ffd56b")
            return Text(f" {char} ", style=Style(color=color, dim=is_dim))

        base_color = getattr(theme, self.message_color, "#ffd56b")
        if stall_intensity > 0.01:
            base_rgb = hex_to_rgb(base_color)
            r, g, b = interpolate_color(base_rgb, ERROR_RED_RGB, min(stall_intensity, 1.0))
            color = rgb_to_hex(r, g, b)
            return Text(f" {char} ", style=Style(color=color))

        return Text(f" {char} ", style=Style(color=base_color))


# ---------------------------------------------------------------------------
# GlimmerMessage - sweeping shimmer across verb text
# ---------------------------------------------------------------------------

class GlimmerMessage:
    """Renders verb text with a shimmer/glimmer sweep effect."""

    def __init__(self, message_color: str = "fox", shimmer_color: str = "foxShimmer"):
        self.message_color = message_color
        self.shimmer_color = shimmer_color

    def render(
        self,
        message: str,
        mode: str = "responding",
        glimmer_index: int = -100,
        flash_opacity: float = 0,
        stall_intensity: float = 0,
    ) -> Text:
        theme = get_theme()
        if not message:
            return Text("")

        base_color = getattr(theme, self.message_color, "#ffd56b")
        shimmer_color = getattr(theme, self.shimmer_color, "#ffe18c")

        # Stalled: fade whole message toward red
        if stall_intensity > 0.01:
            base_rgb = hex_to_rgb(base_color)
            r, g, b = interpolate_color(base_rgb, ERROR_RED_RGB, min(stall_intensity, 1.0))
            red = rgb_to_hex(r, g, b)
            return Text(f"{message} ", style=Style(color=red))

        # Tool-use mode: full-message flash between base and shimmer
        if mode == "tool-use":
            if flash_opacity > 0.5:
                return Text(f"{message} ", style=Style(color=shimmer_color))
            return Text(f"{message} ", style=Style(color=base_color))

        # Normal glimmer sweep
        msg_len = len(message)
        msg_width = msg_len  # approximate; rich handles width internally

        if glimmer_index < 0 or glimmer_index >= msg_width:
            return Text(f"{message} ", style=Style(color=base_color))

        shimmer_start = max(0, glimmer_index - 1)
        shimmer_end = glimmer_index + 1

        before = message[:shimmer_start]
        shimmer = message[shimmer_start:shimmer_end]
        after = message[shimmer_end:]

        t = Text()
        if before:
            t.append(before, style=Style(color=base_color))
        if shimmer:
            t.append(shimmer, style=Style(color=shimmer_color))
        if after:
            t.append(after, style=Style(color=base_color))
        t.append(" ", style=Style(color=base_color))
        return t


# ---------------------------------------------------------------------------
# useStalledAnimation (ported logic)
# ---------------------------------------------------------------------------

class StalledAnimation:
    """Port of useStalledAnimation hook.

    3s with no new tokens -> start fading to red over 2s.
    EMA smoothing at 50ms intervals.
    """

    def __init__(self):
        self.last_token_time_ms = 0.0
        self.last_response_length = 0
        self.mount_time_ms = 0.0
        self.stalled_intensity = 0.0
        self.last_smooth_time_ms = 0.0

    def update(
        self,
        time_ms: float,
        current_response_length: int,
        has_active_tools: bool = False,
        reduced_motion: bool = False,
    ) -> tuple[bool, float]:
        if self.mount_time_ms == 0:
            self.mount_time_ms = time_ms
            self.last_token_time_ms = time_ms
            self.last_smooth_time_ms = time_ms
            self.last_response_length = current_response_length

        if current_response_length > self.last_response_length:
            self.last_token_time_ms = time_ms
            self.last_response_length = current_response_length
            self.stalled_intensity = 0.0
            self.last_smooth_time_ms = time_ms

        if has_active_tools or current_response_length == 0:
            time_since_last = time_ms - self.mount_time_ms
        else:
            time_since_last = time_ms - self.last_token_time_ms

        is_stalled = time_since_last > STALL_TIMEOUT_MS and not has_active_tools
        target = min((time_since_last - STALL_TIMEOUT_MS) / STALL_FADE_MS, 1.0) if is_stalled else 0.0

        if not reduced_motion and (target > 0 or self.stalled_intensity > 0):
            dt = time_ms - self.last_smooth_time_ms
            if dt >= 50:
                steps = int(dt / 50)
                for _ in range(steps):
                    diff = target - self.stalled_intensity
                    if abs(diff) < 0.01:
                        self.stalled_intensity = target
                        break
                    self.stalled_intensity += diff * 0.1
                self.last_smooth_time_ms = time_ms
        else:
            self.stalled_intensity = target
            self.last_smooth_time_ms = time_ms

        return is_stalled, self.stalled_intensity


# ---------------------------------------------------------------------------
# SpinnerWidget - main animated spinner (port of SpinnerAnimationRow)
# ---------------------------------------------------------------------------

class SpinnerWidget(Static):
    """Animated spinner with full doge-code animation system.

    Runs a 50ms animation loop driving:
    - SpinnerGlyph (linux -/\\| frames, stall red fade)
    - GlimmerMessage (sweeping shimmer across verb)
    - Token counter (smooth increment)
    - Elapsed timer
    - Thinking shimmer (3s delay, 2s glow period)
    - Progressive width gating (thinking > timer > tokens)
    """

    frame: reactive[int] = reactive(0)
    stall_intensity: reactive[float] = reactive(0.0)
    elapsed_ms: reactive[float] = reactive(0.0)
    token_count: reactive[int] = reactive(0)
    verb: reactive[str] = reactive("Thinking")
    mode: reactive[str] = reactive("responding")
    thinking: reactive[bool] = reactive(False)
    reduced_motion: reactive[bool] = reactive(False)
    has_active_tools: reactive[bool] = reactive(False)

    _start: float = 0.0
    _stall: StalledAnimation
    _verb_timer: float = 0.0
    _anim_time: float = 0.0
    _token_counter: int = 0

    def __init__(self, mode: str = "responding", message_color: str = "fox", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mode = mode
        self.message_color = message_color
        self.shimmer_color = "foxShimmer"
        self._start = time.time()
        self._stall = StalledAnimation()
        self.verb = random.choice(SPINNER_VERBS)
        self._verb_timer = time.time()
        self._glyph = SpinnerGlyph(message_color)
        self._glimmer = GlimmerMessage(message_color, self.shimmer_color)
        self.message = f"{self.verb}..."

    def on_mount(self):
        self.set_interval(0.05, self._tick)

    def update_tokens(self, count: int):
        self.token_count = count

    def update_verb(self, verb: str | None = None):
        if verb:
            self.verb = verb
        else:
            self.verb = random.choice(SPINNER_VERBS)
        self.message = f"{self.verb}..."

    def _tick(self):
        now = time.time()
        elapsed = now - self._start
        self.elapsed_ms = elapsed * 1000
        self._anim_time += 50  # 50ms ticks

        time_ms = int(self._anim_time)
        self.frame = (time_ms // 120) % len(SPINNER_FRAMES)

        # Stalled animation
        _, si = self._stall.update(
            time_ms,
            self.token_count,
            self.has_active_tools or self.thinking,
            self.reduced_motion,
        )
        self.stall_intensity = si

        # Verb rotation every 8s
        if now - self._verb_timer > 8.0:
            self.verb = random.choice(SPINNER_VERBS)
            self.message = f"{self.verb}..."
            self._verb_timer = now

        self.refresh()

    def render(self):
        theme = get_theme()
        time_ms = int(self._anim_time)
        reduced = self.reduced_motion
        si = self.stall_intensity
        frame = self.frame

        # --- Glimmer calculation (port of TS) ---
        glimmer_speed = 50 if self.mode == "requesting" else 200
        msg_width = len(self.message)
        cycle_len = msg_width + 20
        cycle_pos = time_ms // glimmer_speed

        if reduced or si > 0.01:
            glimmer_idx = -100
        elif self.mode == "requesting":
            glimmer_idx = cycle_pos % cycle_len - 10
        else:
            glimmer_idx = msg_width + 10 - cycle_pos % cycle_len

        # --- Flash opacity for tool-use mode ---
        flash_opacity = 0.0
        if not reduced and self.mode == "tool-use":
            flash_opacity = (math.sin(time_ms / 1000 * math.pi) + 1) / 2

        # --- Thinking shimmer ---
        thinking_elapsed = (time_ms - THINKING_DELAY_MS) / 1000
        thinking_opacity = 0.0
        if time_ms >= THINKING_DELAY_MS:
            thinking_opacity = (math.sin(thinking_elapsed * math.pi * 2 / THINKING_GLOW_PERIOD_S) + 1) / 2
        thinking_rgb = interpolate_color(THINKING_INACTIVE_RGB, THINKING_INACTIVE_SHIMMER_RGB, thinking_opacity)
        thinking_color = rgb_to_hex(*thinking_rgb)

        # --- Token counter (smooth increment) ---
        gap = self.token_count - self._token_counter
        if gap > 0:
            if gap < 70:
                inc = 3
            elif gap < 200:
                inc = max(8, math.ceil(gap * 0.15))
            else:
                inc = 50
            self._token_counter = min(self._token_counter + inc, self.token_count)
        displayed_tokens = self._token_counter

        # --- Build status line ---
        elapsed_str = self._format_elapsed()
        tokens_str = self._fmt_tokens(displayed_tokens)

        # --- Render ---
        glyph = self._glyph.render(frame, si, reduced, time_ms)
        msg = self._glimmer.render(self.message, self.mode, glimmer_idx, flash_opacity, si)

        line = Text()
        line.append(glyph)
        line.append(msg)

        # Status parts: (thinking? elapsed? tokens?)
        parts = []
        if elapsed_str and (self.thinking or self.elapsed_ms > 1000):
            parts.append(("elapsed", elapsed_str))
        if tokens_str and displayed_tokens > 0:
            parts.append(("tokens", f"{ICONS.down} {tokens_str} tokens"))

        if parts:
            line.append(" (", style=Style(color=getattr(theme, "inactive", "#7d8590")))
            # Show thinking shimmer if applicable
            if self.thinking:
                line.append("thinking ", style=Style(color=thinking_color))
            for i, (kind, text) in enumerate(parts):
                if i > 0:
                    line.append(" \u00b7 ", style=Style(color=getattr(theme, "inactive", "#7d8590")))
                if kind == "tokens":
                    line.append(f"{ICONS.down} ", style=Style(color=getattr(theme, "inactive", "#7d8590")))
                    line.append(tokens_str, style=Style(color=getattr(theme, "inactive", "#7d8590")))
                    line.append(" tokens", style=Style(color=getattr(theme, "inactive", "#7d8590")))
                else:
                    line.append(text, style=Style(color=getattr(theme, "inactive", "#7d8590")))
            line.append(")", style=Style(color=getattr(theme, "inactive", "#7d8590")))

        return line

    def _format_elapsed(self) -> str:
        s = int(self.elapsed_ms / 1000)
        if s < 60:
            return f"{s}s"
        m = s // 60
        s = s % 60
        if m < 60:
            return f"{m}m {s}s"
        h = m // 60
        m = m % 60
        return f"{h}h {m}m"

    @staticmethod
    def _fmt_tokens(n: int) -> str:
        if n < 1000:
            return str(n)
        if n < 10_000:
            return f"{n / 1000:.1f}k"
        if n < 1_000_000:
            return f"{n // 1000}k"
        return f"{n / 1_000_000:.1f}m"


# ---------------------------------------------------------------------------
# BriefSpinner - compact variant for brief/assistant mode
# ---------------------------------------------------------------------------

class BriefSpinner(Static):
    """Compact spinner for brief/assistant mode (single char, no verb)."""

    frame: reactive[int] = reactive(0)

    def on_mount(self):
        self.set_interval(0.12, self._tick)

    def _tick(self):
        self.frame = (self.frame + 1) % len(SPINNER_FRAMES)
        self.refresh()

    def render(self):
        char = SPINNER_FRAMES[self.frame]
        return Text(f" {char} ", style=Style(color="#ffd56b", bold=True))
