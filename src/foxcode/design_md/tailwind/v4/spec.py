"""
tailwind/v4/spec.py — Tailwind v4 导出类型定义。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TailwindV4ThemeData:
    """Tailwind v4 主题数据，排版拆分为 5 个独立类别。"""

    colors: dict[str, str] = field(default_factory=dict)
    fontFamily: dict[str, str] = field(default_factory=dict)
    fontSize: dict[str, str] = field(default_factory=dict)
    lineHeight: dict[str, str] = field(default_factory=dict)
    letterSpacing: dict[str, str] = field(default_factory=dict)
    fontWeight: dict[str, str] = field(default_factory=dict)
    borderRadius: dict[str, str] = field(default_factory=dict)
    spacing: dict[str, str] = field(default_factory=dict)


@dataclass
class TailwindV4EmitterResult:
    """Tailwind v4 导出结果。"""

    success: bool = True
    data: Optional[dict] = None
    error: Optional[dict] = None
