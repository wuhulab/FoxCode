"""
missing_primary.py — 检测颜色已定义但缺少 primary。
"""

from __future__ import annotations

from foxcode.design_md.linter.rules.types import RuleDescriptor, RuleFinding
from foxcode.design_md.model.spec import DesignSystemState, Finding


def _run(state: DesignSystemState) -> list[RuleFinding]:
    if not state.colors:
        return []

    if "primary" not in state.colors:
        return [RuleFinding(message="颜色已定义但缺少 'primary' 令牌。")]

    return []


missing_primary_rule = RuleDescriptor(
    name="missing-primary",
    severity="warning",
    description="颜色已定义但缺少 primary。",
    run=_run,
)


def missing_primary(state: DesignSystemState) -> list[Finding]:
    return [
        Finding(severity="warning", path=f.path, message=f.message)
        for f in _run(state)
    ]
