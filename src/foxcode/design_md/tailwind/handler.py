"""
tailwind/handler.py — Tailwind v3 emitter 实现。

将 DesignSystemState 映射为 Tailwind theme.extend JSON 配置。
纯函数，无副作用。

调用方式：
    from foxcode.design_md.tailwind.handler import TailwindEmitterHandler
    result = TailwindEmitterHandler().execute(design_system)
"""

from __future__ import annotations

from foxcode.design_md.model.spec import DesignSystemState, ResolvedDimension
from foxcode.design_md.tailwind.spec import TailwindEmitterResult


class TailwindEmitterHandler:
    """将 DesignSystemState 映射为 Tailwind v3 theme.extend 配置。"""

    def execute(self, state: DesignSystemState) -> TailwindEmitterResult:
        """执行导出，返回 TailwindEmitterResult。"""
        try:
            theme_extend = {
                "colors": self._map_colors(state),
                "fontFamily": self._map_font_families(state),
                "fontSize": self._map_font_sizes(state),
                "borderRadius": self._map_dimensions(state.rounded),
                "spacing": self._map_dimensions(state.spacing),
            }

            return TailwindEmitterResult(
                success=True,
                data={"theme": {"extend": theme_extend}},
            )
        except Exception as e:
            return TailwindEmitterResult(
                success=False,
                error={"message": str(e)},
            )

    def _map_colors(self, state: DesignSystemState) -> dict[str, str]:
        """颜色 → {name: hex}"""
        return {name: color.hex for name, color in state.colors.items()}

    def _map_font_families(self, state: DesignSystemState) -> dict[str, list[str]]:
        """排版 → {name: [fontFamily]}"""
        result = {}
        for name, typo in state.typography.items():
            if typo.fontFamily:
                result[name] = [typo.fontFamily]
        return result

    def _map_font_sizes(self, state: DesignSystemState) -> dict[str, list]:
        """排版 → {name: [fontSize, {lineHeight, letterSpacing, fontWeight}]}"""
        result = {}
        for name, typo in state.typography.items():
            if typo.fontSize:
                meta = {}
                if typo.lineHeight:
                    meta["lineHeight"] = self._dim_to_string(typo.lineHeight)
                if typo.letterSpacing:
                    meta["letterSpacing"] = self._dim_to_string(typo.letterSpacing)
                if typo.fontWeight is not None:
                    meta["fontWeight"] = str(typo.fontWeight)
                result[name] = [self._dim_to_string(typo.fontSize), meta]
        return result

    def _map_dimensions(self, dims: dict[str, ResolvedDimension]) -> dict[str, str]:
        """尺寸 → {name: value+unit}"""
        return {name: self._dim_to_string(dim) for name, dim in dims.items()}

    def _dim_to_string(self, dim: ResolvedDimension) -> str:
        """将 ResolvedDimension 转为字符串。"""
        return f"{dim.value}{dim.unit}"
