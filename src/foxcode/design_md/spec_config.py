"""
spec_config.py — DESIGN.md 规范配置加载器。

从 spec_config.yaml 加载规范配置，用 pydantic 验证，导出所有派生常量。
这是规范配置的单一事实来源，所有模块通过此文件获取配置。

调用方式：
    from foxcode.design_md.spec_config import get_spec_config, CANONICAL_ORDER
    config = get_spec_config()
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel


# ── pydantic 模型定义 ──────────────────────────────────────────────


class Section(BaseModel):
    """规范段落定义，包含规范名和可选别名列表。"""

    canonical: str
    aliases: list[str] = []


class TypographyProperty(BaseModel):
    """排版属性定义，包含名称、类型和可选描述。"""

    name: str
    type: str
    description: str = ""


class ComponentSubToken(BaseModel):
    """组件子令牌定义，包含名称和类型。"""

    name: str
    type: str


class RecommendedTokens(BaseModel):
    """推荐令牌名列表，按类别分组。"""

    colors: list[str] = []
    typography: list[str] = []
    rounded: list[str] = []


class SpecExamples(BaseModel):
    """规范文档中的示例数据。"""

    colors: dict[str, str] = {}
    typography: dict[str, dict[str, str | int | float]] = {}
    components: dict[str, dict[str, str]] = {}


class SpecConfig(BaseModel):
    """完整的规范配置，对应 spec_config.yaml 的顶层结构。"""

    version: str
    units: list[str]
    sections: list[Section]
    typography_properties: list[TypographyProperty]
    component_sub_tokens: list[ComponentSubToken]
    color_roles: list[str]
    recommended_tokens: RecommendedTokens
    examples: SpecExamples = SpecExamples()


# ── 配置加载 ──────────────────────────────────────────────────────

_YAML_PATH = Path(__file__).parent / "spec_config.yaml"
_cached_config: Optional[SpecConfig] = None


def load_spec_config(yaml_path: Path | str | None = None) -> SpecConfig:
    """从 YAML 文件加载规范配置，用 pydantic 验证结构完整性。"""
    path = Path(yaml_path) if yaml_path else _YAML_PATH

    if not path.exists():
        raise FileNotFoundError(f"规范配置文件不存在: {path}")

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    return SpecConfig.model_validate(raw)


def get_spec_config() -> SpecConfig:
    """获取规范配置的惰性单例，首次调用时加载并缓存。"""
    global _cached_config

    if _cached_config is None:
        _cached_config = load_spec_config()

    return _cached_config


# ── 派生常量（先声明，再由 _build_constants 填充） ────────────────

SPEC_VERSION: str = ""
STANDARD_UNITS: tuple[str, ...] = ()
SECTIONS: tuple[str, ...] = ()
CANONICAL_ORDER: tuple[str, ...] = ()
SECTION_ALIASES: dict[str, str] = {}
VALID_TYPOGRAPHY_PROPS: tuple[str, ...] = ()
VALID_COMPONENT_SUB_TOKENS: tuple[str, ...] = ()
COLOR_ROLES: tuple[str, ...] = ()
RECOMMENDED_COLOR_TOKENS: tuple[str, ...] = ()
RECOMMENDED_TYPOGRAPHY_TOKENS: tuple[str, ...] = ()
RECOMMENDED_ROUNDED_TOKENS: tuple[str, ...] = ()
SPEC_EXAMPLES: SpecExamples = SpecExamples()


def _build_constants() -> None:
    """从配置构建所有派生常量，模块加载时执行一次。"""
    global SPEC_VERSION, STANDARD_UNITS, SECTIONS, CANONICAL_ORDER
    global SECTION_ALIASES, VALID_TYPOGRAPHY_PROPS, VALID_COMPONENT_SUB_TOKENS
    global COLOR_ROLES, RECOMMENDED_COLOR_TOKENS, RECOMMENDED_TYPOGRAPHY_TOKENS
    global RECOMMENDED_ROUNDED_TOKENS, SPEC_EXAMPLES

    cfg = get_spec_config()

    SPEC_VERSION = cfg.version
    STANDARD_UNITS = tuple(cfg.units)
    SECTIONS = tuple(s.canonical for s in cfg.sections)
    CANONICAL_ORDER = SECTIONS

    # 别名映射：别名 → 规范名
    aliases: dict[str, str] = {}
    for s in cfg.sections:
        for alias in s.aliases:
            aliases[alias] = s.canonical
    SECTION_ALIASES = aliases

    VALID_TYPOGRAPHY_PROPS = tuple(p.name for p in cfg.typography_properties)
    VALID_COMPONENT_SUB_TOKENS = tuple(t.name for t in cfg.component_sub_tokens)
    COLOR_ROLES = tuple(cfg.color_roles)
    RECOMMENDED_COLOR_TOKENS = tuple(cfg.recommended_tokens.colors)
    RECOMMENDED_TYPOGRAPHY_TOKENS = tuple(cfg.recommended_tokens.typography)
    RECOMMENDED_ROUNDED_TOKENS = tuple(cfg.recommended_tokens.rounded)
    SPEC_EXAMPLES = cfg.examples


_build_constants()


# ── 别名解析 ──────────────────────────────────────────────────────


def resolve_alias(heading: str) -> str:
    """将段落别名解析为规范名，如果已是规范名则原样返回。"""
    if heading in SECTION_ALIASES:
        return SECTION_ALIASES[heading]

    return heading
