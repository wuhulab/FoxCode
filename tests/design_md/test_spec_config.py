"""
test_spec_config.py — 规范配置加载器测试。
"""

import pytest
from pathlib import Path

from foxcode.design_md.spec_config import (
    get_spec_config, load_spec_config, resolve_alias,
    SPEC_VERSION, STANDARD_UNITS, SECTIONS, CANONICAL_ORDER,
    SECTION_ALIASES, VALID_TYPOGRAPHY_PROPS, VALID_COMPONENT_SUB_TOKENS,
    COLOR_ROLES, RECOMMENDED_COLOR_TOKENS, RECOMMENDED_TYPOGRAPHY_TOKENS,
    RECOMMENDED_ROUNDED_TOKENS,
)


class TestLoadSpecConfig:
    def test_load_from_default_path(self):
        config = load_spec_config()
        assert config.version == "alpha"
        assert len(config.sections) > 0

    def test_load_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_spec_config("/nonexistent/path.yaml")


class TestGetSpecConfig:
    def test_returns_same_instance(self):
        config1 = get_spec_config()
        config2 = get_spec_config()
        assert config1 is config2


class TestDerivedConstants:
    def test_spec_version(self):
        assert SPEC_VERSION == "alpha"

    def test_standard_units(self):
        assert "px" in STANDARD_UNITS
        assert "em" in STANDARD_UNITS
        assert "rem" in STANDARD_UNITS

    def test_sections_order(self):
        assert SECTIONS[0] == "Overview"
        assert "Colors" in SECTIONS

    def test_canonical_order_equals_sections(self):
        assert CANONICAL_ORDER == SECTIONS

    def test_section_aliases(self):
        assert SECTION_ALIASES["Brand & Style"] == "Overview"

    def test_valid_typography_props(self):
        assert "fontFamily" in VALID_TYPOGRAPHY_PROPS

    def test_valid_component_sub_tokens(self):
        assert "backgroundColor" in VALID_COMPONENT_SUB_TOKENS

    def test_color_roles(self):
        assert "primary" in COLOR_ROLES

    def test_recommended_tokens(self):
        assert "primary" in RECOMMENDED_COLOR_TOKENS


class TestResolveAlias:
    def test_resolve_known_alias(self):
        assert resolve_alias("Brand & Style") == "Overview"

    def test_resolve_canonical_name_unchanged(self):
        assert resolve_alias("Overview") == "Overview"

    def test_resolve_unknown_name_unchanged(self):
        assert resolve_alias("Custom Section") == "Custom Section"
