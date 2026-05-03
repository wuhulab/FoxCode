"""
orphaned_tokens.py — 检测定义了但从未被组件引用的颜色令牌。
排除 MD3 标准族中的令牌。
"""

from __future__ import annotations

from foxcode.design_md.linter.rules.types import RuleDescriptor, RuleFinding
from foxcode.design_md.model.spec import DesignSystemState, Finding, ResolvedColor


# MD3 标准颜色族，这些族中的令牌永不标记为孤立
MD3_STANDARD_FAMILIES = frozenset({
    "primary", "secondary", "tertiary", "error", "surface", "background", "outline",
})


def _color_family(name: str) -> str:
    """将 MD3 令牌名缩减为家族根名。

    去除 on-、inverse- 前缀和 -container*、-fixed* 等后缀。
    """
    root = name
    for prefix in ("on-", "inverse-"):
        if root.startswith(prefix):
            root = root[len(prefix):]
    for suffix in ("-container", "-container-variant", "-fixed", "-fixed-dim"):
        if root.endswith(suffix):
            root = root[: -len(suffix)]

    return root


def _run(state: DesignSystemState) -> list[RuleFinding]:
    if not state.colors or not state.components:
        return []

    # 收集所有被组件引用的颜色名
    referenced = set()
    for comp in state.components.values():
        for prop_value in comp.properties.values():
            if isinstance(prop_value, ResolvedColor):
                # 查找哪个颜色名对应这个值
                for name, color in state.colors.items():
                    if color.hex == prop_value.hex:
                        referenced.add(name)

    # 检查孤立令牌
    findings: list[RuleFinding] = []
    for name in state.colors:
        if name in referenced:
            continue

        family = _color_family(name)
        if family in MD3_STANDARD_FAMILIES:
            continue

        # 如果同族中有令牌被引用，也不标记为孤立
        family_referenced = any(
            _color_family(ref_name) == family for ref_name in referenced
        )
        if family_referenced:
            continue

        findings.append(RuleFinding(
            path=f"colors.{name}",
            message=f"颜色令牌 '{name}' 已定义但未被任何组件引用。",
        ))

    return findings


orphaned_tokens_rule = RuleDescriptor(
    name="orphaned-tokens",
    severity="warning",
    description="检测定义了但从未被组件引用的颜色令牌。",
    run=_run,
)


def orphaned_tokens(state: DesignSystemState) -> list[Finding]:
    return [
        Finding(severity="warning", path=f.path, message=f.message)
        for f in _run(state)
    ]
