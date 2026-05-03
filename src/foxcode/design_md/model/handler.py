"""
model/handler.py — 模型处理器实现。

从 ParsedDesignSystem 构建 DesignSystemState，包含三阶段解析：
1. Phase 1：解析原始令牌（colors/typography/rounded/spacing），构建符号表
2. Phase 2：解析链式引用（{path.to.token} 格式）
3. Phase 3：构建组件（解析组件属性中的引用）

永不抛出异常——所有错误通过 ModelResult.findings 返回。

调用方式：
    from foxcode.design_md.model.handler import ModelHandler, contrast_ratio
    result = ModelHandler().execute(parsed_design_system)
"""

from __future__ import annotations

import logging
import re
from typing import Optional, Union

from foxcode.design_md.model.spec import (
    ComponentDef,
    DesignSystemState,
    Finding,
    ModelResult,
    ResolvedColor,
    ResolvedDimension,
    ResolvedTypography,
    ResolvedValue,
    is_parseable_dimension,
    is_token_reference,
    is_valid_color,
    parse_dimension_parts,
)
from foxcode.design_md.parser.spec import ParsedDesignSystem

logger = logging.getLogger(__name__)

MAX_REFERENCE_DEPTH = 10


class ModelHandler:
    """从解析后的 YAML 令牌构建已解析的设计系统状态。"""

    def execute(self, input_data: ParsedDesignSystem) -> ModelResult:
        """执行三阶段解析，返回 DesignSystemState 和 findings。"""
        try:
            findings: list[Finding] = []
            symbol_table: dict[str, ResolvedValue] = {}
            colors: dict[str, ResolvedColor] = {}
            typography: dict[str, ResolvedTypography] = {}
            rounded: dict[str, ResolvedDimension] = {}
            spacing: dict[str, ResolvedDimension] = {}

            # ── Phase 1：解析原始令牌 ──────────────────────────
            self._resolve_colors_phase1(input_data, findings, symbol_table, colors)
            self._resolve_typography(input_data, findings, symbol_table, typography)
            self._resolve_rounded_phase1(input_data, findings, symbol_table, rounded)
            self._resolve_spacing_phase1(input_data, findings, symbol_table, spacing)

            # ── Phase 2：解析链式引用 ──────────────────────────
            self._resolve_color_references(input_data, symbol_table, colors)
            self._resolve_rounded_references(input_data, symbol_table, rounded)
            self._resolve_spacing_references(input_data, symbol_table, spacing)

            # ── Phase 3：构建组件 ──────────────────────────────
            components = self._build_components(input_data, symbol_table)

            return ModelResult(
                designSystem=DesignSystemState(
                    name=input_data.name,
                    description=input_data.description,
                    colors=colors,
                    typography=typography,
                    rounded=rounded,
                    spacing=spacing,
                    components=components,
                    symbolTable=symbol_table,
                    sections=input_data.sections,
                ),
                findings=findings,
            )

        except Exception as e:
            logger.error("模型构建发生未知错误: %s", e)
            return ModelResult(
                designSystem=DesignSystemState(),
                findings=[Finding(severity="error", message=f"模型构建意外错误: {e}")],
            )

    # ── Phase 1：原始令牌解析 ──────────────────────────────────

    def _resolve_colors_phase1(
        self,
        input_data: ParsedDesignSystem,
        findings: list[Finding],
        symbol_table: dict[str, ResolvedValue],
        colors: dict[str, ResolvedColor],
    ) -> None:
        """Phase 1：解析颜色令牌，引用先存储原始值。"""
        if not input_data.colors:
            return

        for name, raw in input_data.colors.items():
            if is_token_reference(raw):
                # 引用先存储原始值，Phase 2 再解析
                symbol_table[f"colors.{name}"] = raw
            elif is_valid_color(raw):
                resolved = parse_color(raw)
                colors[name] = resolved
                symbol_table[f"colors.{name}"] = resolved
            else:
                findings.append(Finding(
                    severity="error",
                    path=f"colors.{name}",
                    message=f"'{raw}' 不是有效的颜色。需要 hex 颜色代码（如 #ffffff）。",
                ))
                symbol_table[f"colors.{name}"] = raw

    def _resolve_typography(
        self,
        input_data: ParsedDesignSystem,
        findings: list[Finding],
        symbol_table: dict[str, ResolvedValue],
        typography: dict[str, ResolvedTypography],
    ) -> None:
        """解析排版令牌。"""
        if not input_data.typography:
            return

        for name, props in input_data.typography.items():
            resolved = _parse_typography(props, f"typography.{name}", findings)
            typography[name] = resolved
            symbol_table[f"typography.{name}"] = resolved

    def _resolve_rounded_phase1(
        self,
        input_data: ParsedDesignSystem,
        findings: list[Finding],
        symbol_table: dict[str, ResolvedValue],
        rounded: dict[str, ResolvedDimension],
    ) -> None:
        """Phase 1：解析圆角令牌。"""
        if not input_data.rounded:
            return

        for name, raw in input_data.rounded.items():
            if not isinstance(raw, str):
                continue

            if is_parseable_dimension(raw):
                resolved = _parse_dimension(raw)
                if resolved.unit not in ("px", "rem", "em"):
                    findings.append(Finding(
                        severity="error",
                        path=f"rounded.{name}",
                        message=f"'{raw}' 的单位 '{resolved.unit}' 无效。只允许 px、rem 和 em。",
                    ))
                rounded[name] = resolved
                symbol_table[f"rounded.{name}"] = resolved
            elif is_token_reference(raw):
                symbol_table[f"rounded.{name}"] = raw
            else:
                findings.append(Finding(
                    severity="error",
                    path=f"rounded.{name}",
                    message=f"'{raw}' 不是有效的尺寸。",
                ))
                symbol_table[f"rounded.{name}"] = raw

    def _resolve_spacing_phase1(
        self,
        input_data: ParsedDesignSystem,
        findings: list[Finding],
        symbol_table: dict[str, ResolvedValue],
        spacing: dict[str, ResolvedDimension],
    ) -> None:
        """Phase 1：解析间距令牌。"""
        if not input_data.spacing:
            return

        for name, raw in input_data.spacing.items():
            if isinstance(raw, str) and is_parseable_dimension(raw):
                resolved = _parse_dimension(raw)
                spacing[name] = resolved
                symbol_table[f"spacing.{name}"] = resolved
            else:
                symbol_table[f"spacing.{name}"] = raw

    # ── Phase 2：链式引用解析 ──────────────────────────────────

    def _resolve_color_references(
        self,
        input_data: ParsedDesignSystem,
        symbol_table: dict[str, ResolvedValue],
        colors: dict[str, ResolvedColor],
    ) -> None:
        """Phase 2：解析颜色中的链式引用。"""
        if not input_data.colors:
            return

        for name, raw in input_data.colors.items():
            if is_token_reference(raw):
                resolved = _resolve_reference(symbol_table, raw[1:-1], set())
                if isinstance(resolved, ResolvedColor):
                    colors[name] = resolved
                    symbol_table[f"colors.{name}"] = resolved

    def _resolve_rounded_references(
        self,
        input_data: ParsedDesignSystem,
        symbol_table: dict[str, ResolvedValue],
        rounded: dict[str, ResolvedDimension],
    ) -> None:
        """Phase 2：解析圆角中的链式引用。"""
        if not input_data.rounded:
            return

        for name, raw in input_data.rounded.items():
            if isinstance(raw, str) and is_token_reference(raw):
                resolved = _resolve_reference(symbol_table, raw[1:-1], set())
                if isinstance(resolved, ResolvedDimension):
                    rounded[name] = resolved
                    symbol_table[f"rounded.{name}"] = resolved

    def _resolve_spacing_references(
        self,
        input_data: ParsedDesignSystem,
        symbol_table: dict[str, ResolvedValue],
        spacing: dict[str, ResolvedDimension],
    ) -> None:
        """Phase 2：解析间距中的链式引用。"""
        if not input_data.spacing:
            return

        for name, raw in input_data.spacing.items():
            if isinstance(raw, str) and is_token_reference(raw):
                resolved = _resolve_reference(symbol_table, raw[1:-1], set())
                if isinstance(resolved, ResolvedDimension):
                    spacing[name] = resolved
                    symbol_table[f"spacing.{name}"] = resolved

    # ── Phase 3：构建组件 ──────────────────────────────────────

    def _build_components(
        self,
        input_data: ParsedDesignSystem,
        symbol_table: dict[str, ResolvedValue],
    ) -> dict[str, ComponentDef]:
        """Phase 3：构建组件，解析属性中的引用。"""
        components: dict[str, ComponentDef] = {}

        if not input_data.components:
            return components

        for comp_name, props in input_data.components.items():
            properties: dict[str, ResolvedValue] = {}
            unresolved_refs: list[str] = []

            for prop_name, raw_value in props.items():
                # 数值直接存储
                if isinstance(raw_value, (int, float)):
                    properties[prop_name] = raw_value
                elif isinstance(raw_value, str) and is_token_reference(raw_value):
                    ref_path = raw_value[1:-1]
                    resolved = _resolve_reference(symbol_table, ref_path, set())
                    if resolved is not None:
                        properties[prop_name] = resolved
                    else:
                        unresolved_refs.append(raw_value)
                        properties[prop_name] = raw_value
                elif isinstance(raw_value, str) and is_valid_color(raw_value):
                    properties[prop_name] = parse_color(raw_value)
                elif isinstance(raw_value, str) and is_parseable_dimension(raw_value):
                    properties[prop_name] = _parse_dimension(raw_value)
                else:
                    properties[prop_name] = raw_value

            components[comp_name] = ComponentDef(
                properties=properties,
                unresolvedRefs=unresolved_refs,
            )

        return components


# ── 纯工具函数 ──────────────────────────────────────────────────


def parse_color(raw: str) -> ResolvedColor:
    """将 hex 颜色字符串解析为 ResolvedColor，包含 RGB + WCAG 亮度。"""
    hex_val = raw

    # 规范化 #RGB → #RRGGBB
    if len(hex_val) == 4:
        hex_val = f"#{hex_val[1]}{hex_val[1]}{hex_val[2]}{hex_val[2]}{hex_val[3]}{hex_val[3]}"

    # 规范化 #RGBA → #RRGGBBAA
    if len(hex_val) == 5:
        hex_val = f"#{hex_val[1]}{hex_val[1]}{hex_val[2]}{hex_val[2]}{hex_val[3]}{hex_val[3]}{hex_val[4]}{hex_val[4]}"

    hex_val = hex_val.lower()

    r = int(hex_val[1:3], 16)
    g = int(hex_val[3:5], 16)
    b = int(hex_val[5:7], 16)

    a: Optional[float] = None
    if len(hex_val) == 9:
        a = int(hex_val[7:9], 16) / 255

    luminance = _compute_luminance(r, g, b)

    return ResolvedColor(hex=hex_val, r=r, g=g, b=b, a=a, luminance=luminance)


def _compute_luminance(r: int, g: int, b: int) -> float:
    """计算 WCAG 2.1 相对亮度，使用 sRGB 线性化。"""
    def linearize(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def _parse_dimension(raw: str) -> ResolvedDimension:
    """将尺寸字符串解析为 ResolvedDimension。"""
    parts = parse_dimension_parts(raw)
    if parts is None:
        raise ValueError(f"无效的尺寸: {raw}")

    return ResolvedDimension(value=parts[0], unit=parts[1])


def _parse_typography(
    props: dict[str, Union[str, int, float]],
    path: str,
    findings: list[Finding],
) -> ResolvedTypography:
    """将排版属性对象解析为 ResolvedTypography。"""
    result = ResolvedTypography()

    # fontFamily
    ff = props.get("fontFamily")
    if isinstance(ff, str):
        if is_valid_color(ff):
            findings.append(Finding(
                severity="error",
                path=f"{path}.fontFamily",
                message=f"'{ff}' 看起来是颜色值，不是有效的字体族名。",
            ))
        result.fontFamily = ff

    # fontWeight
    fw = props.get("fontWeight")
    if fw is not None:
        fw_value: Optional[int] = None
        if isinstance(fw, (int, float)):
            fw_value = int(fw)
        elif isinstance(fw, str):
            try:
                fw_value = int(float(fw))
            except (ValueError, TypeError):
                pass

        if fw_value is None:
            findings.append(Finding(
                severity="error",
                path=f"{path}.fontWeight",
                message=f"'{fw}' 不是有效的字重。需要数字。",
            ))
        else:
            result.fontWeight = fw_value

    # fontFeature 和 fontVariation
    if isinstance(props.get("fontFeature"), str):
        result.fontFeature = props["fontFeature"]
    if isinstance(props.get("fontVariation"), str):
        result.fontVariation = props["fontVariation"]

    # 尺寸类属性：fontSize、lineHeight、letterSpacing
    for prop in ("fontSize", "lineHeight", "letterSpacing"):
        raw = props.get(prop)
        if not isinstance(raw, str):
            continue

        if is_parseable_dimension(raw):
            parsed = _parse_dimension(raw)
            if parsed.unit not in ("px", "rem", "em"):
                findings.append(Finding(
                    severity="error",
                    path=f"{path}.{prop}",
                    message=f"'{raw}' 的单位 '{parsed.unit}' 无效。只允许 px、rem 和 em。",
                ))
            setattr(result, prop, parsed)
        elif prop == "lineHeight" and re.match(r"^\d*\.?\d+$", raw):
            # lineHeight 可以是无单位乘数
            result.lineHeight = ResolvedDimension(value=float(raw), unit="")
        elif not is_token_reference(raw):
            findings.append(Finding(
                severity="error",
                path=f"{path}.{prop}",
                message=f"'{raw}' 不是有效的尺寸。",
            ))

    return result


def _resolve_reference(
    symbol_table: dict[str, ResolvedValue],
    path: str,
    visited: set[str],
    depth: int = 0,
) -> ResolvedValue | None:
    """解析令牌引用，支持链式解析和循环检测。"""
    if depth > MAX_REFERENCE_DEPTH:
        return None

    if path in visited:
        return None  # 循环引用

    visited.add(path)

    value = symbol_table.get(path)
    if value is None:
        return None

    # 如果值本身是引用字符串，继续追踪
    if isinstance(value, str) and is_token_reference(value):
        inner_path = value[1:-1]
        return _resolve_reference(symbol_table, inner_path, visited, depth + 1)

    return value


def contrast_ratio(a: ResolvedColor, b: ResolvedColor) -> float:
    """计算两个已解析颜色之间的 WCAG 2.1 对比度。"""
    l1 = max(a.luminance, b.luminance)
    l2 = min(a.luminance, b.luminance)
    return (l1 + 0.05) / (l2 + 0.05)
