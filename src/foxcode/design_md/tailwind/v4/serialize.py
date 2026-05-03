"""
tailwind/v4/serialize.py — CSS @theme 序列化。

将 TailwindV4ThemeData 序列化为 CSS @theme { ... } 块字符串。
纯函数，无 I/O。

调用方式：
    from foxcode.design_md.tailwind.v4.serialize import serialize_to_css
    css = serialize_to_css(theme_data)
"""

from __future__ import annotations

from foxcode.design_md.tailwind.v4.spec import TailwindV4ThemeData

# 类别 → CSS 变量前缀，迭代顺序即输出顺序
_CATEGORIES: list[tuple[str, str]] = [
    ("colors", "--color-"),
    ("fontFamily", "--font-"),
    ("fontSize", "--text-"),
    ("lineHeight", "--leading-"),
    ("letterSpacing", "--tracking-"),
    ("fontWeight", "--font-weight-"),
    ("borderRadius", "--radius-"),
    ("spacing", "--spacing-"),
]


def serialize_to_css(data: TailwindV4ThemeData) -> str:
    """将 Tailwind v4 主题数据序列化为 CSS @theme 块。"""
    lines = []

    for attr_name, prefix in _CATEGORIES:
        entries = getattr(data, attr_name, None)
        if not entries:
            continue

        for name, value in entries.items():
            lines.append(f"  {prefix}{name}: {value};")

    if not lines:
        return "@theme {\n}\n"

    return f"@theme {{\n{chr(10).join(lines)}\n}}\n"
