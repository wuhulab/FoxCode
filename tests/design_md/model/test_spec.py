"""
test_spec.py — 核心类型和验证辅助函数测试。
"""

import pytest
from foxcode.design_md.model.spec import (
    is_valid_color, is_standard_dimension, is_parseable_dimension,
    parse_dimension_parts, is_token_reference,
    ResolvedColor, ResolvedDimension, ResolvedTypography, Finding, DesignSystemState,
)


class TestIsValidColor:
    def test_valid_six_digit_hex(self):
        assert is_valid_color("#1A1C1E") is True
    def test_valid_three_digit_hex(self):
        assert is_valid_color("#fff") is True
    def test_invalid_missing_hash(self):
        assert is_valid_color("1A1C1E") is False
    def test_invalid_empty(self):
        assert is_valid_color("") is False


class TestParseDimensionParts:
    def test_parse_px(self):
        assert parse_dimension_parts("42px") == (42.0, "px")
    def test_parse_rem(self):
        assert parse_dimension_parts("1.5rem") == (1.5, "rem")
    def test_parse_bare_number_returns_none(self):
        assert parse_dimension_parts("42") is None


class TestIsStandardDimension:
    def test_px_is_standard(self):
        assert is_standard_dimension("16px") is True
    def test_vh_is_not_standard(self):
        assert is_standard_dimension("100vh") is False


class TestIsParseableDimension:
    def test_percent_is_parseable(self):
        assert is_parseable_dimension("50%") is True
    def test_bare_number_is_not_parseable(self):
        assert is_parseable_dimension("42") is False


class TestIsTokenReference:
    def test_valid_reference(self):
        assert is_token_reference("{colors.primary}") is True
    def test_plain_string_is_not_reference(self):
        assert is_token_reference("#1A1C1E") is False


class TestDataclassDefaults:
    def test_resolved_color_type(self):
        assert ResolvedColor().type == "color"
    def test_resolved_dimension_type(self):
        assert ResolvedDimension().type == "dimension"
    def test_design_system_state_defaults(self):
        state = DesignSystemState()
        assert len(state.colors) == 0
