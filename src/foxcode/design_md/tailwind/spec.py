"""
tailwind/spec.py — Tailwind v3 导出类型定义。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TailwindThemeExtend:
    """Tailwind v3 theme.extend 配置。"""

    colors: dict[str, str] = field(default_factory=dict)
    fontFamily: dict[str, list[str]] = field(default_factory=dict)
    fontSize: dict[str, list] = field(default_factory=dict)
    borderRadius: dict[str, str] = field(default_factory=dict)
    spacing: dict[str, str] = field(default_factory=dict)


@dataclass
class TailwindTheme:
    """Tailwind v3 theme 配置。"""

    extend: TailwindThemeExtend = field(default_factory=TailwindThemeExtend)


@dataclass
class TailwindEmitterResult:
    """Tailwind v3 导出结果。"""

    success: bool = True
    data: Optional[dict] = None
    error: Optional[dict] = None
