"""
test_handler.py — 解析器处理器测试。
"""

import pytest
from foxcode.design_md.parser.handler import ParserHandler
from foxcode.design_md.parser.spec import ParserInput


@pytest.fixture
def parser():
    return ParserHandler()


class TestFrontmatterExtraction:
    def test_extract_frontmatter(self, parser):
        content = "---\ncolors:\n  primary: '#1A1C1E'\n---\n\n## Overview"
        result = parser.execute(ParserInput(content=content))
        assert result.success is True
        assert result.data.colors == {"primary": "#1A1C1E"}

    def test_extract_frontmatter_with_name(self, parser):
        content = "---\nname: Test\ndescription: A test\n---\n"
        result = parser.execute(ParserInput(content=content))
        assert result.success is True
        assert result.data.name == "Test"


class TestCodeBlockExtraction:
    def test_extract_yaml_code_block(self, parser):
        content = "## Colors\n\n```yaml\ncolors:\n  primary: '#FF0000'\n```\n"
        result = parser.execute(ParserInput(content=content))
        assert result.success is True
        assert result.data.colors == {"primary": "#FF0000"}


class TestMultipleBlocks:
    def test_merge_frontmatter_and_code_block(self, parser):
        content = "---\ncolors:\n  primary: '#1A1C1E'\n---\n\n## Typography\n\n```yaml\ntypography:\n  h1:\n    fontFamily: Sans\n```\n"
        result = parser.execute(ParserInput(content=content))
        assert result.success is True
        assert result.data.colors == {"primary": "#1A1C1E"}
        assert result.data.typography == {"h1": {"fontFamily": "Sans"}}


class TestDuplicateDetection:
    def test_duplicate_section_error(self, parser):
        content = "---\ncolors:\n  primary: '#1A1C1E'\n---\n\n```yaml\ncolors:\n  secondary: '#6C7278'\n```\n"
        result = parser.execute(ParserInput(content=content))
        assert result.success is False
        assert result.error.code == "DUPLICATE_SECTION"


class TestErrorHandling:
    def test_empty_content(self, parser):
        result = parser.execute(ParserInput(content=""))
        assert result.success is False
        assert result.error.code == "EMPTY_CONTENT"

    def test_no_yaml_found(self, parser):
        result = parser.execute(ParserInput(content="# Just a heading\n\nSome text."))
        assert result.success is False
        assert result.error.code == "NO_YAML_FOUND"

    def test_malformed_yaml(self, parser):
        content = "---\ncolors: [invalid: yaml\n---\n"
        result = parser.execute(ParserInput(content=content))
        assert result.success is False
        assert result.error.code == "YAML_PARSE_ERROR"


class TestSectionExtraction:
    def test_extract_h2_headings(self, parser):
        content = "---\ncolors:\n  primary: '#1A1C1E'\n---\n\n## Overview\n\n## Colors\n\n## Typography\n"
        result = parser.execute(ParserInput(content=content))
        assert result.success is True
        assert "Overview" in result.data.sections
