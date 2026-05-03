"""
dtcg/spec.py — DTCG (W3C Design Tokens Format Module 2025.10) 类型定义。

DTCG 格式使用 $ 前缀的键名（如 $type、$value），这在 Python 中不合法，
因此 DTCG 类型使用普通 dict 表示，此文件仅定义结果类型。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DtcgEmitterResult:
    """DTCG 导出结果。"""

    success: bool = True
    data: Optional[dict] = None
    error: Optional[dict] = None
