"""
linter/rules/types.py — 规则类型定义。

定义 LintRule 和 RuleDescriptor 类型。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from foxcode.design_md.model.spec import DesignSystemState, Finding, Severity


@dataclass
class RuleFinding:
    """规则产生的发现，severity 可选（默认使用规则描述符的级别）。"""

    message: str
    path: str = ""
    severity: Optional[Severity] = None


# LintRule：纯函数，接收 DesignSystemState，返回 Finding 列表
LintRule = Callable[[DesignSystemState], list[Finding]]


@dataclass
class RuleDescriptor:
    """规则描述符，包含名称、严重级别、描述和执行函数。"""

    name: str
    severity: Severity
    description: str
    run: Callable[[DesignSystemState], list[RuleFinding]] = field(default_factory=list)
