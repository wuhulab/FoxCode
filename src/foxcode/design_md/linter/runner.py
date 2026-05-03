"""
linter/runner.py — 规则运行器。

执行规则集并聚合 findings，提供分级评估功能。

调用方式：
    from foxcode.design_md.linter.runner import run_linter, pre_evaluate
    result = run_linter(design_system)
"""

from __future__ import annotations

from foxcode.design_md.linter.spec import GradedTokenEdits, LintResult, TokenEditEntry
from foxcode.design_md.linter.rules.types import LintRule, RuleDescriptor
from foxcode.design_md.model.spec import DesignSystemState, Finding


def run_linter(
    state: DesignSystemState,
    rules: list[LintRule] | None = None,
) -> LintResult:
    """执行规则集并聚合 findings。

    Args:
        state: 已解析的设计系统状态
        rules: 自定义规则列表，为 None 时使用 DEFAULT_RULES
    """
    if rules is None:
        from foxcode.design_md.linter.rules import DEFAULT_RULES
        rules = DEFAULT_RULES

    all_findings: list[Finding] = []
    for rule in rules:
        findings = rule(state)
        all_findings.extend(findings)

    summary = _compute_summary(all_findings)

    return LintResult(findings=all_findings, summary=summary)


def pre_evaluate(findings: list[Finding]) -> GradedTokenEdits:
    """将 findings 分级为 fixes（error）、improvements（warning）、suggestions（info）。"""
    fixes = []
    improvements = []
    suggestions = []

    for finding in findings:
        entry = TokenEditEntry(
            path=finding.path or "",
            findings=[finding],
        )

        if finding.severity == "error":
            fixes.append(entry)
        elif finding.severity == "warning":
            improvements.append(entry)
        else:
            suggestions.append(entry)

    return GradedTokenEdits(
        fixes=fixes,
        improvements=improvements,
        suggestions=suggestions,
    )


def _compute_summary(findings: list[Finding]) -> dict[str, int]:
    """计算 findings 的汇总统计。"""
    errors = sum(1 for f in findings if f.severity == "error")
    warnings = sum(1 for f in findings if f.severity == "warning")
    infos = sum(1 for f in findings if f.severity == "info")

    return {"errors": errors, "warnings": warnings, "infos": infos}
