"""
linter/spec.py — 规则检查类型定义。

定义 LintResult、GradedTokenEdits、TokenEditEntry 等类型。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from foxcode.design_md.model.spec import Finding, Severity


@dataclass
class LintResult:
    """规则检查结果，包含 findings 和汇总统计。"""

    findings: list[Finding] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=lambda: {"errors": 0, "warnings": 0, "infos": 0})


@dataclass
class TokenEditEntry:
    """令牌编辑条目，包含路径、当前值、建议值和关联的 findings。"""

    path: str
    currentValue: str = ""
    suggestedValue: str = ""
    findings: list[Finding] = field(default_factory=list)


@dataclass
class GradedTokenEdits:
    """分级编辑菜单，按严重级别分组。"""

    fixes: list[TokenEditEntry] = field(default_factory=list)
    improvements: list[TokenEditEntry] = field(default_factory=list)
    suggestions: list[TokenEditEntry] = field(default_factory=list)
