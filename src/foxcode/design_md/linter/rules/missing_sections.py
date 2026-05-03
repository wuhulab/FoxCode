"""
missing_sections.py — 检测缺少 spacing/rounded 可选段落。
"""

from __future__ import annotations

from foxcode.design_md.linter.rules.types import RuleDescriptor, RuleFinding
from foxcode.design_md.model.spec import DesignSystemState, Finding


def _run(state: DesignSystemState) -> list[RuleFinding]:
    findings: list[RuleFinding] = []

    if not state.rounded:
        findings.append(RuleFinding(message="缺少可选段落 'Shapes' (rounded)。"))

    if not state.spacing:
        findings.append(RuleFinding(message="缺少可选段落 'Layout' (spacing)。"))

    return findings


missing_sections_rule = RuleDescriptor(
    name="missing-sections",
    severity="info",
    description="检测缺少 spacing/rounded 可选段落。",
    run=_run,
)


def missing_sections(state: DesignSystemState) -> list[Finding]:
    return [
        Finding(severity="info", path=f.path, message=f.message)
        for f in _run(state)
    ]
