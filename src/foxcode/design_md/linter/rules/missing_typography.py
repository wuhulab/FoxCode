"""
missing_typography.py — 检测有颜色但无排版令牌。
"""

from __future__ import annotations

from foxcode.design_md.linter.rules.types import RuleDescriptor, RuleFinding
from foxcode.design_md.model.spec import DesignSystemState, Finding


def _run(state: DesignSystemState) -> list[RuleFinding]:
    if state.colors and not state.typography:
        return [RuleFinding(message="有颜色令牌但缺少排版令牌。")]

    return []


missing_typography_rule = RuleDescriptor(
    name="missing-typography",
    severity="warning",
    description="检测有颜色但无排版令牌。",
    run=_run,
)


def missing_typography(state: DesignSystemState) -> list[Finding]:
    return [
        Finding(severity="warning", path=f.path, message=f.message)
        for f in _run(state)
    ]
