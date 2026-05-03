"""
fixer/handler.py — 段落顺序修复实现。

将段落重新排序为规范顺序，保留 prelude 在顶部，未知段落追加到末尾。

调用方式：
    from foxcode.design_md.fixer.handler import fix_section_order
    result = fix_section_order(FixerInput(sections=document_sections))
"""

from __future__ import annotations

from foxcode.design_md.fixer.spec import FixerInput, FixerResult
from foxcode.design_md.linter.rules.section_order import CANONICAL_ORDER, resolve_alias


def fix_section_order(input_data: FixerInput) -> FixerResult:
    """将段落重新排序为规范顺序。"""
    sections = input_data.sections

    # 分离 prelude、已知段落、未知段落
    prelude = next((s for s in sections if s.heading == ""), None)

    known = [
        s for s in sections
        if s.heading != "" and resolve_alias(s.heading) in CANONICAL_ORDER
    ]

    unknown = [
        s for s in sections
        if s.heading != "" and resolve_alias(s.heading) not in CANONICAL_ORDER
    ]

    # 已知段落按规范顺序排序
    known.sort(key=lambda s: CANONICAL_ORDER.index(resolve_alias(s.heading)))

    # 组装结果
    result_sections = []
    if prelude:
        result_sections.append(prelude)
    result_sections.extend(known)
    result_sections.extend(unknown)

    fixed_content = "\n".join(s.content for s in result_sections)

    before_order = [s.heading for s in sections if s.heading != ""]
    after_order = [s.heading for s in result_sections if s.heading != ""]

    return FixerResult(
        success=True,
        fixedContent=fixed_content,
        details={"beforeOrder": before_order, "afterOrder": after_order},
    )
