"""
broken_ref.py — 检测未解析的令牌引用和未知组件子令牌。
"""

from __future__ import annotations

from foxcode.design_md.linter.rules.types import RuleDescriptor, RuleFinding
from foxcode.design_md.model.spec import ComponentDef, DesignSystemState, Finding
from foxcode.design_md.spec_config import VALID_COMPONENT_SUB_TOKENS


def _run(state: DesignSystemState) -> list[RuleFinding]:
    findings: list[RuleFinding] = []

    # 检测组件中未解析的引用
    for comp_name, comp in state.components.items():
        for ref in comp.unresolvedRefs:
            findings.append(RuleFinding(
                path=f"components.{comp_name}",
                message=f"未解析的引用 '{ref}'。",
            ))

        # 检测未知组件子令牌
        for prop_name in comp.properties:
            if prop_name not in VALID_COMPONENT_SUB_TOKENS:
                findings.append(RuleFinding(
                    path=f"components.{comp_name}.{prop_name}",
                    message=f"未知的组件子令牌 '{prop_name}'。",
                ))

    return findings


broken_ref_rule = RuleDescriptor(
    name="broken-ref",
    severity="error",
    description="检测未解析的令牌引用和未知组件子令牌。",
    run=_run,
)


def broken_ref(state: DesignSystemState) -> list[Finding]:
    """broken_ref 规则的 LintRule 接口。"""
    return [
        Finding(
            severity=f.severity or broken_ref_rule.severity,
            path=f.path,
            message=f.message,
        )
        for f in _run(state)
    ]
