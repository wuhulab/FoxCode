"""
spec_gen/renderers.py — Markdown 渲染器函数。

生成规范文档中使用的各种示例和列表。
"""

from __future__ import annotations

from foxcode.design_md.spec_config import get_spec_config, SPEC_EXAMPLES


def frontmatter_example() -> str:
    """生成 frontmatter 示例。"""
    lines = ["---"]
    if SPEC_EXAMPLES.colors:
        lines.append("colors:")
        for name, value in SPEC_EXAMPLES.colors.items():
            lines.append(f"  {name}: \"{value}\"")
    lines.append("---")
    return "\n".join(lines)


def colors_example() -> str:
    """生成颜色 YAML 示例。"""
    cfg = get_spec_config()
    lines = ["colors:"]
    for name in cfg.recommended_tokens.colors:
        value = SPEC_EXAMPLES.colors.get(name, "#000000")
        lines.append(f"  {name}: \"{value}\"")
    return "\n".join(lines)


def typography_example() -> str:
    """生成排版 YAML 示例。"""
    lines = ["typography:"]
    for name, props in SPEC_EXAMPLES.typography.items():
        lines.append(f"  {name}:")
        for key, value in props.items():
            if isinstance(value, str):
                lines.append(f"    {key}: \"{value}\"")
            else:
                lines.append(f"    {key}: {value}")
    return "\n".join(lines)


def components_example() -> str:
    """生成组件 YAML 示例。"""
    lines = ["components:"]
    for name, props in SPEC_EXAMPLES.components.items():
        lines.append(f"  {name}:")
        for key, value in props.items():
            lines.append(f"    {key}: \"{value}\"")
    return "\n".join(lines)


def typography_property_list() -> str:
    """生成排版属性列表。"""
    cfg = get_spec_config()
    lines = []
    for prop in cfg.typography_properties:
        desc = f" — {prop.description}" if prop.description else ""
        lines.append(f"- **{prop.name}** (`{prop.type}`){desc}")
    return "\n".join(lines)


def section_order_list() -> str:
    """生成段落顺序列表。"""
    cfg = get_spec_config()
    lines = []
    for i, section in enumerate(cfg.sections, 1):
        aliases = f" (aliases: {', '.join(section.aliases)})" if section.aliases else ""
        lines.append(f"{i}. **{section.canonical}**{aliases}")
    return "\n".join(lines)


def component_sub_token_list() -> str:
    """生成组件子令牌列表。"""
    cfg = get_spec_config()
    lines = []
    for token in cfg.component_sub_tokens:
        lines.append(f"- **{token.name}** (`{token.type}`)")
    return "\n".join(lines)


def recommended_tokens() -> str:
    """生成推荐令牌名列表。"""
    cfg = get_spec_config()
    lines = ["### Colors", ""]
    for name in cfg.recommended_tokens.colors:
        lines.append(f"- `{name}`")
    lines.extend(["", "### Typography", ""])
    for name in cfg.recommended_tokens.typography:
        lines.append(f"- `{name}`")
    lines.extend(["", "### Rounded", ""])
    for name in cfg.recommended_tokens.rounded:
        lines.append(f"- `{name}`")
    return "\n".join(lines)
