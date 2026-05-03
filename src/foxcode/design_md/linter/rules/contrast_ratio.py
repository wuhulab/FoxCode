"""
contrast_ratio.py — 组件 backgroundColor/textColor 对比度低于 WCAG AA (4.5:1)。
"""

from __future__ import annotations

from foxcode.design_md.linter.rules.types import RuleDescriptor, RuleFinding
from foxcode.design_md.model.handler import contrast_ratio
from foxcode.design_md.model.spec import DesignSystemState, Finding, ResolvedColor


def _run(state: DesignSystemState) -> list[RuleFinding]:
    findings: list[RuleFinding] = []

    for comp_name, comp in state.components.items():
        bg = comp.properties.get("backgroundColor")
        fg = comp.properties.get("textColor")

        if not isinstance(bg, ResolvedColor) or not isinstance(fg, ResolvedColor):
            continue

        ratio = contrast_ratio(bg, fg)
        if ratio < 4.5:
            findings.append(RuleFinding(
                path=f"components.{comp_name}",
                message=f"对比度 {ratio:.2f}:1 低于 WCAG AA 标准 (4.5:1)。",
            ))

    return findings


contrast_check_rule = RuleDescriptor(
    name="contrast-ratio",
    severity="warning",
    description="组件 backgroundColor/textColor 对比度低于 WCAG AA (4.5:1)。",
    run=_run,
)


def contrast_check(state: DesignSystemState) -> list[Finding]:
    return [
        Finding(severity="warning", path=f.path, message=f.message)
        for f in _run(state)
    ]
