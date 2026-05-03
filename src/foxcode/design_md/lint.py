"""
lint.py — 核心 lint() 编排函数。

完整的 DESIGN.md 验证管道：Parser → Model → Linter → Tailwind。
处理可恢复错误，返回 LintReport。

调用方式：
    from foxcode.design_md.lint import lint
    report = lint(markdown_content)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from foxcode.design_md.linter.runner import run_linter
from foxcode.design_md.linter.rules.types import LintRule
from foxcode.design_md.model.handler import ModelHandler
from foxcode.design_md.model.spec import DesignSystemState, Finding
from foxcode.design_md.parser.handler import ParserHandler
from foxcode.design_md.parser.spec import DocumentSection, ParserInput, ParsedDesignSystem
from foxcode.design_md.tailwind.handler import TailwindEmitterHandler
from foxcode.design_md.tailwind.spec import TailwindEmitterResult

logger = logging.getLogger(__name__)


@dataclass
class LintOptions:
    """lint() 的可选配置。"""

    rules: Optional[list[LintRule]] = None


@dataclass
class LintReport:
    """lint() 的完整输出报告。"""

    designSystem: DesignSystemState = field(default_factory=DesignSystemState)
    findings: list[Finding] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=lambda: {"errors": 0, "warnings": 0, "infos": 0})
    tailwindConfig: Optional[TailwindEmitterResult] = None
    sections: list[str] = field(default_factory=list)
    documentSections: list[DocumentSection] = field(default_factory=list)


def lint(content: str, options: LintOptions | None = None) -> LintReport:
    """验证 DESIGN.md 文档。

    解析 Markdown，解析所有设计令牌为类型化模型，
    运行 lint 规则，生成 Tailwind CSS 主题配置。

    Args:
        content: 原始 DESIGN.md 内容（含 YAML frontmatter 或代码块的 Markdown）
        options: 可选配置（自定义规则等）
    """
    parser = ParserHandler()
    model = ModelHandler()
    tailwind = TailwindEmitterHandler()

    parse_result = parser.execute(ParserInput(content=content))

    # 处理解析失败
    if not parse_result.success:
        if parse_result.error and parse_result.error.recoverable:
            empty_parsed = ParsedDesignSystem()
            model_result = model.execute(empty_parsed)
            sections = _extract_sections_from_content(content)

            return LintReport(
                designSystem=model_result.designSystem,
                findings=[Finding(severity="warning", message=parse_result.error.message)],
                summary={"errors": 0, "warnings": 1, "infos": 0},
                tailwindConfig=tailwind.execute(model_result.designSystem),
                sections=[s.heading for s in sections if s.heading],
                documentSections=sections,
            )

        # 不可恢复的错误是致命的
        raise RuntimeError(f"解析失败: {parse_result.error.message if parse_result.error else '未知错误'}")

    model_result = model.execute(parse_result.data)
    lint_result = run_linter(model_result.designSystem, options.rules if options else None)
    tailwind_config = tailwind.execute(model_result.designSystem)

    # 合并 model findings 和 linter findings
    all_findings = model_result.findings + lint_result.findings
    summary = {
        "errors": sum(1 for f in model_result.findings if f.severity == "error") + lint_result.summary["errors"],
        "warnings": sum(1 for f in model_result.findings if f.severity == "warning") + lint_result.summary["warnings"],
        "infos": sum(1 for f in model_result.findings if f.severity == "info") + lint_result.summary["infos"],
    }

    return LintReport(
        designSystem=model_result.designSystem,
        findings=all_findings,
        summary=summary,
        tailwindConfig=tailwind_config,
        sections=parse_result.data.sections or [],
        documentSections=parse_result.data.documentSections or [],
    )


def _extract_sections_from_content(content: str) -> list[DocumentSection]:
    """从原始 Markdown 内容中提取 H2 段落，作为解析失败时的后备。"""
    lines = content.split("\n")
    sections: list[DocumentSection] = []
    current_start = 0
    current_heading = ""

    for i, line in enumerate(lines):
        if line.startswith("## "):
            # 推入前一个段落
            if i > 0:
                sections.append(DocumentSection(
                    heading=current_heading,
                    content="\n".join(lines[current_start:i]),
                ))
            current_heading = line[3:].strip()
            current_start = i

    # 推入最后一个段落
    sections.append(DocumentSection(
        heading=current_heading,
        content="\n".join(lines[current_start:]),
    ))

    return sections
