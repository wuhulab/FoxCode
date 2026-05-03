"""
dtcg/handler.py — DTCG emitter 实现。

将 DesignSystemState 映射为 W3C Design Tokens Format Module 2025.10 格式。
纯函数，无副作用。

调用方式：
    from foxcode.design_md.dtcg.handler import DtcgEmitterHandler
    result = DtcgEmitterHandler().execute(design_system)
"""

from __future__ import annotations

from typing import Any

from foxcode.design_md.model.spec import (
    DesignSystemState,
    ResolvedColor,
    ResolvedDimension,
    ResolvedTypography,
)
from foxcode.design_md.dtcg.spec import DtcgEmitterResult

_DTCG_SCHEMA_URL = "https://www.designtokens.org/schemas/2025.10/format.json"


class DtcgEmitterHandler:
    """将 DesignSystemState 映射为 DTCG tokens.json 格式。"""

    def execute(self, state: DesignSystemState) -> DtcgEmitterResult:
        """执行导出，返回 DtcgEmitterResult。"""
        try:
            file_data: dict[str, Any] = {"$schema": _DTCG_SCHEMA_URL}

            if state.name or state.description:
                file_data["$description"] = state.description or state.name

            color_group = self._map_colors(state)
            if color_group:
                file_data["color"] = color_group

            spacing_group = self._map_dimension_group(state.spacing)
            if spacing_group:
                file_data["spacing"] = spacing_group

            rounded_group = self._map_dimension_group(state.rounded)
            if rounded_group:
                file_data["rounded"] = rounded_group

            typography_group = self._map_typography(state)
            if typography_group:
                file_data["typography"] = typography_group

            return DtcgEmitterResult(success=True, data=file_data)
        except Exception as e:
            return DtcgEmitterResult(success=False, error={"message": str(e)})

    def _map_colors(self, state: DesignSystemState) -> dict[str, Any] | None:
        if not state.colors:
            return None

        group: dict[str, Any] = {"$type": "color"}
        for name, color in state.colors.items():
            group[name] = {"$value": self._color_to_value(color)}
        return group

    def _color_to_value(self, color: ResolvedColor) -> dict[str, Any]:
        return {
            "colorSpace": "srgb",
            "components": [
                self._round(color.r / 255),
                self._round(color.g / 255),
                self._round(color.b / 255),
            ],
            "hex": color.hex.lower(),
        }

    def _map_dimension_group(
        self, dims: dict[str, ResolvedDimension]
    ) -> dict[str, Any] | None:
        if not dims:
            return None

        group: dict[str, Any] = {"$type": "dimension"}
        for name, dim in dims.items():
            group[name] = {"$value": {"value": dim.value, "unit": dim.unit}}
        return group

    def _map_typography(self, state: DesignSystemState) -> dict[str, Any] | None:
        if not state.typography:
            return None

        group: dict[str, Any] = {}
        for name, typo in state.typography.items():
            group[name] = {
                "$type": "typography",
                "$value": self._typography_to_value(typo),
            }
        return group

    def _typography_to_value(self, typo: ResolvedTypography) -> dict[str, Any]:
        value: dict[str, Any] = {}
        if typo.fontFamily:
            value["fontFamily"] = typo.fontFamily
        if typo.fontSize:
            value["fontSize"] = {"value": typo.fontSize.value, "unit": typo.fontSize.unit}
        if typo.fontWeight is not None:
            value["fontWeight"] = typo.fontWeight
        if typo.letterSpacing:
            value["letterSpacing"] = {"value": typo.letterSpacing.value, "unit": typo.letterSpacing.unit}
        if typo.lineHeight:
            # DTCG lineHeight 是 fontSize 的无单位乘数
            value["lineHeight"] = typo.lineHeight.value
        return value

    def _round(self, n: float) -> float:
        """四舍五入到 3 位小数。"""
        return round(n * 1000) / 1000
