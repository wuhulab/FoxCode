"""
linter/rules/__init__.py — 默认规则集和重新导出。

组装 DEFAULT_RULES 列表，提供各规则的 LintRule 接口重新导出。
"""

from __future__ import annotations

from foxcode.design_md.linter.rules.types import LintRule, RuleDescriptor
from foxcode.design_md.model.spec import DesignSystemState, Finding

from foxcode.design_md.linter.rules.broken_ref import broken_ref_rule, broken_ref
from foxcode.design_md.linter.rules.missing_primary import missing_primary_rule, missing_primary
from foxcode.design_md.linter.rules.contrast_ratio import contrast_check_rule, contrast_check
from foxcode.design_md.linter.rules.orphaned_tokens import orphaned_tokens_rule, orphaned_tokens
from foxcode.design_md.linter.rules.token_summary import token_summary_rule, token_summary
from foxcode.design_md.linter.rules.missing_sections import missing_sections_rule, missing_sections
from foxcode.design_md.linter.rules.missing_typography import missing_typography_rule, missing_typography
from foxcode.design_md.linter.rules.section_order import section_order_rule, section_order


# 默认规则描述符列表，按顺序
DEFAULT_RULE_DESCRIPTORS: list[RuleDescriptor] = [
    broken_ref_rule,
    missing_primary_rule,
    contrast_check_rule,
    orphaned_tokens_rule,
    token_summary_rule,
    missing_sections_rule,
    missing_typography_rule,
    section_order_rule,
]


def _to_lint_rule(descriptor: RuleDescriptor) -> LintRule:
    """将 RuleDescriptor 转换为 LintRule，注入 severity。"""
    def rule(state: DesignSystemState) -> list[Finding]:
        raw_findings = descriptor.run(state)
        return [
            Finding(
                severity=f.severity or descriptor.severity,
                path=f.path,
                message=f.message,
            )
            for f in raw_findings
        ]
    return rule


# 默认规则列表，可直接传给 run_linter
DEFAULT_RULES: list[LintRule] = [_to_lint_rule(d) for d in DEFAULT_RULE_DESCRIPTORS]
