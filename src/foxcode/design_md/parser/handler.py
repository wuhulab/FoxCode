"""
parser/handler.py — Markdown 解析器实现。

从 DESIGN.md 内容中提取 YAML 前置元数据和代码块，合并为 ParsedDesignSystem。
支持两种 YAML 嵌入模式：
1. frontmatter（--- 包裹）
2. fenced yaml 代码块（```yaml ... ```）

永不抛出异常——所有错误通过 ParserResult 返回。

调用方式：
    from foxcode.design_md.parser.handler import ParserHandler
    result = ParserHandler().execute(ParserInput(content=markdown_text))
"""

from __future__ import annotations

import logging
from typing import Union

import yaml

from foxcode.design_md.parser.spec import (
    DocumentSection,
    ParserError,
    ParserInput,
    ParserResult,
    ParsedDesignSystem,
    SourceLocation,
)

logger = logging.getLogger(__name__)


class ParserHandler:
    """从 DESIGN.md 内容中提取和解析 YAML 设计令牌。"""

    def execute(self, input_data: ParserInput) -> ParserResult:
        """解析 Markdown 内容，提取 YAML 设计令牌。"""
        try:
            content = input_data.content

            if not content.strip():
                return ParserResult(
                    success=False,
                    error=ParserError(
                        code="EMPTY_CONTENT",
                        message="内容为空。",
                        recoverable=True,
                    ),
                )

            blocks = self._extract_yaml_blocks(content)
            sections, headings_with_lines = self._extract_headings_from_content(content)
            document_sections = self._slice_document_sections(content, headings_with_lines)

            if not blocks:
                return ParserResult(
                    success=False,
                    error=ParserError(
                        code="NO_YAML_FOUND",
                        message="未找到 YAML 内容。需要 frontmatter (---) 或 yaml 代码块。",
                        recoverable=True,
                    ),
                )

            return self._merge_code_blocks(blocks, sections, document_sections)

        except Exception as e:
            logger.error("解析器发生未知错误: %s", e)
            return ParserResult(
                success=False,
                error=ParserError(
                    code="UNKNOWN_ERROR",
                    message=str(e),
                    recoverable=False,
                ),
            )

    def _extract_yaml_blocks(
        self, content: str
    ) -> list[dict[str, Union[str, int]]]:
        """从 Markdown 内容中提取 YAML 块。

        支持两种格式：
        1. frontmatter：--- 包裹的 YAML 块
        2. fenced code block：```yaml 或 ```yml 包裹的代码块
        """
        blocks = []
        lines = content.split("\n")
        line_count = len(lines)
        i = 0

        # 提取 frontmatter
        if line_count > 0 and lines[0].strip() == "---":
            i = 1
            yaml_lines = []
            start_line = 1
            while i < line_count:
                if lines[i].strip() == "---":
                    blocks.append({
                        "yaml": "\n".join(yaml_lines),
                        "block": "frontmatter",
                        "startLine": start_line,
                    })
                    i += 1
                    break
                yaml_lines.append(lines[i])
                i += 1

        # 提取 fenced yaml 代码块
        block_index = 0
        while i < line_count:
            line = lines[i].strip()
            if line.startswith("```") and (line[3:].strip() in ("yaml", "yml")):
                yaml_lines = []
                start_line = i + 1  # 1-indexed
                i += 1
                while i < line_count:
                    if lines[i].strip() == "```":
                        blocks.append({
                            "yaml": "\n".join(yaml_lines),
                            "block": block_index,
                            "startLine": start_line,
                        })
                        block_index += 1
                        i += 1
                        break
                    yaml_lines.append(lines[i])
                    i += 1
            else:
                i += 1

        return blocks

    def _extract_headings_from_content(
        self, content: str
    ) -> tuple[list[str], list[dict[str, Union[str, int]]]]:
        """从原始内容中提取 H2 标题文本和行号。"""
        sections = []
        headings_with_lines = []

        for i, line in enumerate(content.split("\n")):
            if line.startswith("## "):
                text = line[3:].strip()
                if text:
                    sections.append(text)
                    # 行号从 1 开始
                    headings_with_lines.append({"text": text, "line": i + 1})

        return sections, headings_with_lines

    def _slice_document_sections(
        self,
        content: str,
        headings_with_lines: list[dict[str, Union[str, int]]],
    ) -> list[DocumentSection]:
        """按 H2 标题将内容切分为段落。"""
        lines = content.split("\n")
        document_sections = []

        if not headings_with_lines:
            # 没有 H2 标题，整个文件作为一个段落
            document_sections.append(DocumentSection(heading="", content=content))
            return document_sections

        # 第一个标题前的内容作为 prelude
        first_line = headings_with_lines[0]["line"]
        if first_line > 1:
            prelude = "\n".join(lines[: first_line - 1])
            document_sections.append(DocumentSection(heading="", content=prelude))

        # 按标题切分
        for idx, heading_info in enumerate(headings_with_lines):
            start_idx = heading_info["line"] - 1  # 转为 0-indexed
            if idx + 1 < len(headings_with_lines):
                end_idx = headings_with_lines[idx + 1]["line"] - 1
            else:
                end_idx = len(lines)

            section_content = "\n".join(lines[start_idx:end_idx])
            document_sections.append(
                DocumentSection(heading=heading_info["text"], content=section_content)
            )

        return document_sections

    def _merge_code_blocks(
        self,
        blocks: list[dict[str, Union[str, int]]],
        sections: list[str],
        document_sections: list[DocumentSection],
    ) -> ParserResult:
        """合并多个 YAML 代码块为单个 ParsedDesignSystem，检测重复顶级键。"""
        merged: dict = {}
        source_map: dict[str, SourceLocation] = {}
        seen_sections: dict[str, Union[str, int]] = {}

        for block in blocks:
            yaml_text = block["yaml"]
            try:
                parsed = yaml.safe_load(yaml_text)
                if not parsed or not isinstance(parsed, dict):
                    continue
            except yaml.YAMLError as e:
                return ParserResult(
                    success=False,
                    error=ParserError(
                        code="YAML_PARSE_ERROR",
                        message=str(e),
                        recoverable=True,
                    ),
                )

            # 检测重复顶级键
            for key in parsed:
                if key in seen_sections:
                    prev = seen_sections[key]
                    prev_desc = "frontmatter" if prev == "frontmatter" else f"代码块 {prev + 1}"
                    curr = block["block"]
                    curr_desc = "frontmatter" if curr == "frontmatter" else f"代码块 {curr + 1}"
                    return ParserResult(
                        success=False,
                        error=ParserError(
                            code="DUPLICATE_SECTION",
                            message=f"段落 '{key}' 同时定义在 {prev_desc} 和 {curr_desc} 中。",
                            recoverable=True,
                        ),
                    )

                seen_sections[key] = block["block"]
                source_map[key] = SourceLocation(
                    line=block["startLine"],
                    column=0,
                    block=block["block"],
                )

            merged.update(parsed)

        return ParserResult(
            success=True,
            data=self._to_design_system(merged, source_map, sections, document_sections),
        )

    def _to_design_system(
        self,
        raw: dict,
        source_map: dict[str, SourceLocation],
        sections: list[str],
        document_sections: list[DocumentSection],
    ) -> ParsedDesignSystem:
        """将原始解析结果映射为 ParsedDesignSystem。"""
        return ParsedDesignSystem(
            name=raw.get("name") if isinstance(raw.get("name"), str) else None,
            description=raw.get("description") if isinstance(raw.get("description"), str) else None,
            colors=raw.get("colors") if isinstance(raw.get("colors"), dict) else None,
            typography=raw.get("typography") if isinstance(raw.get("typography"), dict) else None,
            rounded=raw.get("rounded") if isinstance(raw.get("rounded"), dict) else None,
            spacing=raw.get("spacing") if isinstance(raw.get("spacing"), dict) else None,
            components=raw.get("components") if isinstance(raw.get("components"), dict) else None,
            sourceMap=source_map,
            sections=sections,
            documentSections=document_sections,
        )
