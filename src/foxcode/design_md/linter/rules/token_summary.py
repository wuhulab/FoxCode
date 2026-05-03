"""
token_summary.py — 各类令牌数量汇总。
"""

from __future__ import annotations

from foxcode.design_md.linter.rules.types import RuleDescriptor, RuleFinding
from foxcode.design_md.model.spec import DesignSystemState, Finding


def _run(state: DesignSystemState) -> list[RuleFinding]:
    counts = {
        "colors": len(state.colors),
        "typography": len(state.typography),
        "rounded": len(state.rounded),
        "spacing": len(state.spacing),
        "components": len(state.components),
    }

    parts = [f"{k}: {v}" for k, v in counts.items()]
    return [RuleFinding(message=f"令牌汇总 — {', '.join(parts)}")]


token_summary_rule = RuleDescriptor(
    name="token-summary",
    severity="info",
    description="各类令牌数量汇总。",
    run=_run,
)


def token_summary(state: DesignSystemState) -> list[Finding]:
    return [
        Finding(severity="info", path=f.path, message=f.message)
        for f in _run(state)
    ]
