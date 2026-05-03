"""
spec_gen/helpers.py — 规范文档辅助函数。

提供 get_spec_content() 和 get_rules_table() 函数。
"""

from __future__ import annotations

from foxcode.design_md.linter.rules import DEFAULT_RULE_DESCRIPTORS
from foxcode.design_md.spec_config import SPEC_VERSION


def get_spec_content() -> str:
    """获取规范文档内容。"""
    return _SPEC_CONTENT


def get_rules_table(descriptors: list | None = None) -> str:
    """生成规则 Markdown 表格。"""
    rules = descriptors or DEFAULT_RULE_DESCRIPTORS
    lines = ["| 规则 | 严重级别 | 描述 |", "| --- | --- | --- |"]
    for r in rules:
        lines.append(f"| {r.name} | {r.severity} | {r.description} |")
    return "\n".join(lines)


# 内嵌的规范文档内容（简化版，替代 MDX 编译器）
_SPEC_CONTENT = f"""# DESIGN.md Format Specification

Version: {SPEC_VERSION}

## Overview

A DESIGN.md file bridges design systems and code. It consists of two layers:

1. **YAML frontmatter or code blocks** — machine-readable design tokens with precise values
2. **Markdown prose** — human-readable design rationale explaining "why"

## Sections

The following sections are recognized in canonical order:

1. **Overview** (aliases: Brand & Style)
2. **Colors**
3. **Typography**
4. **Layout** (aliases: Layout & Spacing)
5. **Elevation & Depth** (aliases: Elevation)
6. **Shapes**
7. **Components**
8. **Do's and Don'ts**

## Token Format

### Colors
Colors are specified as hex values: `#RRGGBB` or `#RRGGBBAA`.

### Typography
Typography tokens support: fontFamily, fontSize, fontWeight, lineHeight, letterSpacing, fontFeature, fontVariation.

### Dimensions
Dimensions use the format: `value + unit` (e.g., `16px`, `1.5rem`).
Standard units: px, em, rem.

### Token References
Tokens can reference other tokens using `{{section.token}}` syntax.
"""
