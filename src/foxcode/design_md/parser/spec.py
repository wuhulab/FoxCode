"""
parser/spec.py — 解析器数据类型定义。

定义 ParserInput、ParserResult、ParsedDesignSystem、SourceLocation 等类型，
供 parser/handler.py 使用。

调用方式：
    from foxcode.design_md.parser.spec import ParsedDesignSystem
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional, Union


# ── 错误码 ────────────────────────────────────────────────────────

ParserErrorCode = Literal[
    "EMPTY_CONTENT",
    "NO_YAML_FOUND",
    "YAML_PARSE_ERROR",
    "DUPLICATE_SECTION",
    "UNKNOWN_ERROR",
]


@dataclass
class ParserError:
    """解析器错误信息。"""

    code: ParserErrorCode
    message: str
    recoverable: bool = False


# ── 源码位置 ──────────────────────────────────────────────────────


@dataclass
class SourceLocation:
    """YAML 块在源文件中的位置信息。"""

    line: int
    column: int = 0
    block: Union[str, int] = "frontmatter"


# ── 文档段落 ──────────────────────────────────────────────────────


@dataclass
class DocumentSection:
    """按 H2 标题切分的文档段落。"""

    heading: str
    content: str


# ── 解析后的设计系统 ──────────────────────────────────────────────


@dataclass
class ParsedDesignSystem:
    """解析器输出的原始设计系统数据，尚未经过模型处理。"""

    sourceMap: dict[str, SourceLocation] = field(default_factory=dict)
    name: Optional[str] = None
    description: Optional[str] = None
    colors: Optional[dict[str, str]] = None
    typography: Optional[dict[str, dict[str, Union[str, int, float]]]] = None
    rounded: Optional[dict[str, str]] = None
    spacing: Optional[dict[str, str]] = None
    components: Optional[dict[str, dict[str, str]]] = None
    sections: list[str] = field(default_factory=list)
    documentSections: list[DocumentSection] = field(default_factory=list)


# ── 解析器输入/输出 ───────────────────────────────────────────────


@dataclass
class ParserInput:
    """解析器输入，包含原始 Markdown 内容。"""

    content: str


@dataclass
class ParserResult:
    """解析器输出，成功时包含 ParsedDesignSystem，失败时包含 ParserError。"""

    success: bool
    data: Optional[ParsedDesignSystem] = None
    error: Optional[ParserError] = None
