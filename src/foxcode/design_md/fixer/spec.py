"""
fixer/spec.py — 修复器类型定义。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from foxcode.design_md.parser.spec import DocumentSection


@dataclass
class FixerInput:
    """修复器输入。"""

    content: str = ""
    sections: list[DocumentSection] = field(default_factory=list)


@dataclass
class FixerResult:
    """修复器输出。"""

    success: bool = True
    fixedContent: str = ""
    details: Optional[dict] = None
    error: Optional[dict] = None
