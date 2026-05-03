"""
section_order.py — 检测段落顺序不符合规范。

提供 CANONICAL_ORDER 常量和 resolve_alias 函数供 fixer 使用。
"""

from __future__ import annotations

from foxcode.design_md.linter.rules.types import RuleDescriptor, RuleFinding
from foxcode.design_md.model.spec import DesignSystemState, Finding
from foxcode.design_md.spec_config import CANONICAL_ORDER, resolve_alias as _resolve_alias


# 重新导出，供 fixer 使用
CANONICAL_ORDER = CANONICAL_ORDER


def resolve_alias(heading: str) -> str:
    """将段落别名解析为规范名。"""
    return _resolve_alias(heading)


def _run(state: DesignSystemState) -> list[RuleFinding]:
    if not state.sections:
        return []

    # 将段落名解析为规范名
    canonical = [resolve_alias(s) for s in state.sections]

    # 检查规范名是否按 CANONICAL_ORDER 排序
    order_map = {name: idx for idx, name in enumerate(CANONICAL_ORDER)}

    # 只检查已知段落
    known = [(s, order_map.get(c, -1)) for s, c in zip(state.sections, canonical) if c in order_map]

    for i in range(len(known) - 1):
        if known[i][1] > known[i + 1][1]:
            return [RuleFinding(
                message=f"段落顺序不符合规范。当前: {', '.join(state.sections)}。",
            )]

    return []


section_order_rule = RuleDescriptor(
    name="section-order",
    severity="warning",
    description="段落顺序不符合规范。",
    run=_run,
)


def section_order(state: DesignSystemState) -> list[Finding]:
    return [
        Finding(severity="warning", path=f.path, message=f.message)
        for f in _run(state)
    ]
