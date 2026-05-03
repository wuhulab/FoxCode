"""
tailwind/v4/handler.py — Tailwind v4 emitter 实现。

将 DesignSystemState 映射为 Tailwind v4 主题数据。
验证令牌名符合 CSS 标识符规则，fontFamily 值用双引号包裹。
"""

from __future__ import annotations

import re

from foxcode.design_md.model.spec import DesignSystemState, ResolvedDimension
from foxcode.design_md.tailwind.v4.spec import TailwindV4EmitterResult, TailwindV4ThemeData

_CSS_IDENTIFIER_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9-]*$")


class TailwindV4EmitterHandler:
    """将 DesignSystemState 映射为 Tailwind v4 主题数据。"""

    def execute(self, state: DesignSystemState) -> TailwindV4EmitterResult:
        """执行导出，返回 TailwindV4EmitterResult。"""
        try:
            theme = TailwindV4ThemeData(
                colors=self._map_colors(state),
                fontFamily=self._map_font_families(state),
                fontSize=self._map_font_sizes(state),
                lineHeight=self._map_line_heights(state),
                letterSpacing=self._map_letter_spacings(state),
                fontWeight=self._map_font_weights(state),
                borderRadius=self._map_dimensions(state.rounded),
                spacing=self._map_dimensions(state.spacing),
            )

            # 验证令牌名符合 CSS 标识符规则
            for category_name, entries in [
                ("colors", theme.colors),
                ("fontFamily", theme.fontFamily),
                ("fontSize", theme.fontSize),
                ("borderRadius", theme.borderRadius),
                ("spacing", theme.spacing),
            ]:
                for name in entries:
                    if not _CSS_IDENTIFIER_RE.match(name):
                        return TailwindV4EmitterResult(
                            success=False,
                            error={"message": f"令牌名 '{name}' 不是有效的 CSS 标识符。"},
                        )

            return TailwindV4EmitterResult(
                success=True,
                data={"theme": theme},
            )
        except Exception as e:
            return TailwindV4EmitterResult(
                success=False,
                error={"message": str(e)},
            )

    def _map_colors(self, state: DesignSystemState) -> dict[str, str]:
        return {name: color.hex for name, color in state.colors.items()}

    def _map_font_families(self, state: DesignSystemState) -> dict[str, str]:
        """fontFamily 值用双引号包裹，转义内部引号。"""
        result = {}
        for name, typo in state.typography.items():
            if typo.fontFamily:
                escaped = typo.fontFamily.replace("\\", "\\\\").replace('"', '\\"')
                result[name] = f'"{escaped}"'
        return result

    def _map_font_sizes(self, state: DesignSystemState) -> dict[str, str]:
        result = {}
        for name, typo in state.typography.items():
            if typo.fontSize:
                result[name] = self._dim_to_string(typo.fontSize)
        return result

    def _map_line_heights(self, state: DesignSystemState) -> dict[str, str]:
        result = {}
        for name, typo in state.typography.items():
            if typo.lineHeight:
                result[name] = self._dim_to_string(typo.lineHeight)
        return result

    def _map_letter_spacings(self, state: DesignSystemState) -> dict[str, str]:
        result = {}
        for name, typo in state.typography.items():
            if typo.letterSpacing:
                result[name] = self._dim_to_string(typo.letterSpacing)
        return result

    def _map_font_weights(self, state: DesignSystemState) -> dict[str, str]:
        result = {}
        for name, typo in state.typography.items():
            if typo.fontWeight is not None:
                result[name] = str(typo.fontWeight)
        return result

    def _map_dimensions(self, dims: dict[str, ResolvedDimension]) -> dict[str, str]:
        return {name: self._dim_to_string(dim) for name, dim in dims.items()}

    def _dim_to_string(self, dim: ResolvedDimension) -> str:
        return f"{dim.value}{dim.unit}"
