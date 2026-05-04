"""
test_handler.py — 模型处理器测试。
"""

import pytest
from foxcode.design_md.model.handler import ModelHandler, parse_color, contrast_ratio
from foxcode.design_md.model.spec import ResolvedColor, ResolvedDimension, ResolvedTypography
from foxcode.design_md.parser.spec import ParsedDesignSystem


@pytest.fixture
def handler():
    return ModelHandler()


class TestParseColor:
    def test_parse_six_digit_hex(self):
        color = parse_color("#1A1C1E")
        assert color.r == 0x1A
        assert color.hex == "#1a1c1e"

    def test_parse_three_digit_hex(self):
        color = parse_color("#fff")
        assert color.r == 255

    def test_compute_luminance(self):
        black = parse_color("#000000")
        assert black.luminance < 0.01
        white = parse_color("#FFFFFF")
        assert white.luminance > 0.99


class TestContrastRatio:
    def test_black_white_contrast(self):
        black = parse_color("#000000")
        white = parse_color("#FFFFFF")
        assert contrast_ratio(black, white) > 20

    def test_same_color_contrast(self):
        color = parse_color("#1A1C1E")
        assert abs(contrast_ratio(color, color) - 1.0) < 0.01


class TestModelHandlerPhase1:
    def test_resolve_colors(self, handler):
        parsed = ParsedDesignSystem(colors={"primary": "#1A1C1E", "secondary": "#6C7278"})
        result = handler.execute(parsed)
        assert "primary" in result.designSystem.colors

    def test_invalid_color_produces_finding(self, handler):
        parsed = ParsedDesignSystem(colors={"bad": "not-a-color"})
        result = handler.execute(parsed)
        assert any(f.path == "colors.bad" for f in result.findings)

    def test_resolve_typography(self, handler):
        parsed = ParsedDesignSystem(typography={"h1": {"fontFamily": "Sans", "fontSize": "48px", "fontWeight": 600}})
        result = handler.execute(parsed)
        assert "h1" in result.designSystem.typography


class TestModelHandlerPhase2:
    def test_resolve_color_reference(self, handler):
        parsed = ParsedDesignSystem(colors={"primary": "#1A1C1E", "primary-variant": "{colors.primary}"})
        result = handler.execute(parsed)
        assert "primary-variant" in result.designSystem.colors
        assert result.designSystem.colors["primary-variant"].hex == "#1a1c1e"

    def test_circular_reference_returns_null(self, handler):
        parsed = ParsedDesignSystem(colors={"a": "{colors.b}", "b": "{colors.a}"})
        result = handler.execute(parsed)
        assert result.designSystem is not None


class TestModelHandlerPhase3:
    def test_build_component_with_references(self, handler):
        parsed = ParsedDesignSystem(
            colors={"primary": "#1A1C1E"},
            components={"button-primary": {"backgroundColor": "{colors.primary}", "textColor": "#FFFFFF"}},
        )
        result = handler.execute(parsed)
        comp = result.designSystem.components.get("button-primary")
        assert comp is not None
        assert isinstance(comp.properties.get("backgroundColor"), ResolvedColor)

    def test_component_with_unresolved_ref(self, handler):
        parsed = ParsedDesignSystem(components={"button": {"backgroundColor": "{colors.nonexistent}"}})
        result = handler.execute(parsed)
        comp = result.designSystem.components.get("button")
        assert comp is not None
        assert len(comp.unresolvedRefs) > 0
