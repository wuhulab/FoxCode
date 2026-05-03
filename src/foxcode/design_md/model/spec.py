"""
model/spec.py — 核心类型定义和验证辅助函数。

定义设计系统的所有数据类型：ResolvedColor、ResolvedDimension、
ResolvedTypography、ComponentDef、DesignSystemState、Finding 等。
同时提供颜色、尺寸、令牌引用的验证辅助函数。

调用方式：
    from foxcode.design_md.model.spec import is_valid_color, ResolvedColor
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, Optional, Union

from foxcode.design_md.spec_config import (
    STANDARD_UNITS,
    VALID_TYPOGRAPHY_PROPS,
    VALID_COMPONENT_SUB_TOKENS,
)


# ── 严重级别 ──────────────────────────────────────────────────────

Severity = Literal["error", "warning", "info"]


@dataclass
class Finding:
    """规则检查发现的问题。"""

    severity: Severity
    message: str
    path: str = ""


# ── 解析后的值类型 ────────────────────────────────────────────────


@dataclass
class ResolvedColor:
    """解析后的颜色值，包含 hex、RGB 分量和 WCAG 亮度。"""

    type: str = field(default="color", init=False)
    hex: str = ""
    r: int = 0
    g: int = 0
    b: int = 0
    a: Optional[float] = None
    luminance: float = 0.0


@dataclass
class ResolvedDimension:
    """解析后的尺寸值，包含数值和单位。"""

    type: str = field(default="dimension", init=False)
    value: float = 0.0
    unit: str = ""


@dataclass
class ResolvedTypography:
    """解析后的排版值，包含字体、大小、行高等属性。"""

    type: str = field(default="typography", init=False)
    fontFamily: Optional[str] = None
    fontSize: Optional[ResolvedDimension] = None
    fontWeight: Optional[int] = None
    lineHeight: Optional[ResolvedDimension] = None
    letterSpacing: Optional[ResolvedDimension] = None
    fontFeature: Optional[str] = None
    fontVariation: Optional[str] = None


# 联合类型：已解析的值可以是颜色、尺寸、排版或原始字符串
ResolvedValue = Union[ResolvedColor, ResolvedDimension, ResolvedTypography, str, int, float]


@dataclass
class ComponentDef:
    """组件定义，包含属性映射和未解析的引用列表。"""

    properties: dict[str, ResolvedValue] = field(default_factory=dict)
    unresolvedRefs: list[str] = field(default_factory=list)


@dataclass
class DesignSystemState:
    """完整的设计系统状态，包含所有解析后的令牌。"""

    colors: dict[str, ResolvedColor] = field(default_factory=dict)
    typography: dict[str, ResolvedTypography] = field(default_factory=dict)
    rounded: dict[str, ResolvedDimension] = field(default_factory=dict)
    spacing: dict[str, ResolvedDimension] = field(default_factory=dict)
    components: dict[str, ComponentDef] = field(default_factory=dict)
    symbolTable: dict[str, ResolvedValue] = field(default_factory=dict)
    name: Optional[str] = None
    description: Optional[str] = None
    sections: Optional[list[str]] = None


# ── 模型结果类型 ──────────────────────────────────────────────────


@dataclass
class ModelResult:
    """模型处理器的输出，包含设计系统状态和发现的问题。"""

    designSystem: DesignSystemState = field(default_factory=DesignSystemState)
    findings: list[Finding] = field(default_factory=list)


# ── 验证辅助函数 ──────────────────────────────────────────────────

# 所有已知 CSS 长度/百分比单位
_CSS_UNITS = frozenset({
    # 绝对单位
    "px", "cm", "mm", "in", "pt", "pc",
    # 相对于字体
    "em", "rem", "ex", "ch", "cap", "ic", "lh", "rlh",
    # 视口 — 经典
    "vh", "vw", "vmin", "vmax",
    # 视口 — 动态/小/大 (CSS Level 4)
    "dvh", "dvw", "dvmin", "dvmax",
    "svh", "svw", "svmin", "svmax",
    "lvh", "lvw", "lvmin", "lvmax",
    # 容器查询单位
    "cqw", "cqh", "cqi", "cqb", "cqmin", "cqmax",
    # 百分比
    "%",
})

# 规范标准单位集合
_STANDARD_UNITS_SET = frozenset(STANDARD_UNITS)

# 颜色正则：#RGB, #RGBA, #RRGGBB, #RRGGBBAA
_COLOR_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")

# 尺寸正则：可选符号 + 数字(含小数) + 单位
_DIMENSION_RE = re.compile(r"^(-?\d*\.?\d+)([a-zA-Z%]+)$")

# 令牌引用正则：{section.token}
_TOKEN_REF_RE = re.compile(r"^\{[a-zA-Z0-9._-]+\}$")


def parse_dimension_parts(raw: str) -> Optional[tuple[float, str]]:
    """将尺寸字符串解析为 (数值, 单位) 元组，无法解析时返回 None。"""
    match = _DIMENSION_RE.match(raw)
    if not match:
        return None

    value = float(match.group(1))
    if value != value:  # NaN 检查
        return None

    return value, match.group(2)


def is_valid_color(raw: str) -> bool:
    """验证是否为有效的 hex 颜色字符串，支持 #RGB/#RGBA/#RRGGBB/#RRGGBBAA。"""
    return bool(_COLOR_RE.match(raw))


def is_standard_dimension(raw: str) -> bool:
    """验证尺寸字符串是否使用规范标准单位（px 或 rem）。"""
    parts = parse_dimension_parts(raw)
    if parts is None:
        return False

    return parts[1] in _STANDARD_UNITS_SET


def is_parseable_dimension(raw: str) -> bool:
    """验证尺寸字符串是否可解析（任何已知 CSS 单位）。"""
    parts = parse_dimension_parts(raw)
    if parts is None:
        return False

    return parts[1] in _CSS_UNITS


def is_token_reference(raw: str) -> bool:
    """验证字符串是否为令牌引用格式 {section.token}。"""
    return bool(_TOKEN_REF_RE.match(raw))
