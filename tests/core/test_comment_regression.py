"""
test_comment_regression.py — 注释保护常规测试与边界条件测试。

覆盖：
- 边界条件（空文件、单字符、无换行符末尾等）
- Unicode、emoji、中文注释
- 多语言边缘情况（PHP 双标记、CSS 纯块注释、INI 多标记）
- 字符串与注释的复杂交错
- 连续注释、多行块注释内部换行
"""

import pytest

from foxcode.core.comment_parser import CommentParser, CommentType
from foxcode.core.comment_protector import CommentProtector


class TestBoundaryConditions:
    """边界条件测试"""

    def test_empty_content(self):
        parser = CommentParser("test.py")
        assert parser.parse("") == []

    def test_only_comments(self):
        parser = CommentParser("test.py")
        comments = parser.parse("# only comment")
        assert len(comments) == 1
        assert comments[0].standalone is True

    def test_only_code_no_newline(self):
        parser = CommentParser("test.py")
        assert parser.parse("x = 1") == []

    def test_newline_only(self):
        parser = CommentParser("test.py")
        assert parser.parse("\n\n\n") == []

    def test_comment_at_eof_no_newline(self):
        parser = CommentParser("test.py")
        comments = parser.parse("x = 1\n# eof comment")
        assert len(comments) == 1
        assert comments[0].text == "# eof comment"

    def test_whitespace_only_lines(self):
        parser = CommentParser("test.py")
        code = "   \n\t\n# comment\n   \n"
        comments = parser.parse(code)
        assert len(comments) == 1
        # 注释在空白包围的文件中，找不到锚点返回 None
        assert comments[0].anchor_line is None

    def test_very_long_line(self):
        parser = CommentParser("test.py")
        long_body = "x" * 10000
        code = f"# {long_body}\n"
        comments = parser.parse(code)
        assert len(comments) == 1
        # body 包含前面的空格，所以是 10001
        assert len(comments[0].body) == 10001

    def test_single_character_file(self):
        parser = CommentParser("test.py")
        comments = parser.parse("#")
        assert len(comments) == 1
        assert comments[0].body == ""


class TestUnicodeAndSpecialChars:
    """Unicode 与特殊字符测试"""

    def test_chinese_comment(self):
        parser = CommentParser("test.py")
        code = "# 这是一个中文注释\nimport os\n"
        comments = parser.parse(code)
        assert len(comments) == 1
        assert "中文" in comments[0].body

    def test_emoji_comment(self):
        parser = CommentParser("test.py")
        code = "# TODO: fix bug 🐛\n"
        comments = parser.parse(code)
        assert comments[0].body == " TODO: fix bug 🐛"

    def test_unicode_in_string_no_false_positive(self):
        parser = CommentParser("test.py")
        code = 's = "你好 # 不是注释 🎉"\n'
        assert parser.parse(code) == []

    def test_mixed_cjk_and_code(self):
        parser = CommentParser("test.py")
        code = 'x = "中文"  # 行尾中文注释\n'
        comments = parser.parse(code)
        assert len(comments) == 1
        assert comments[0].standalone is False
        assert "行尾中文注释" in comments[0].body


class TestEdgeCaseLanguages:
    """多语言边缘情况"""

    def test_php_double_line_markers(self):
        parser = CommentParser("test.php")
        code = "<?php\n// comment 1\n# comment 2\n$x = 1;\n"
        comments = parser.parse(code)
        assert len(comments) == 2
        assert comments[0].text == "// comment 1"
        assert comments[1].text == "# comment 2"

    def test_php_block(self):
        parser = CommentParser("test.php")
        code = "<?php\n/* block\ncomment */\n$x = 1;\n"
        comments = parser.parse(code)
        assert len(comments) == 1
        assert comments[0].comment_type == CommentType.BLOCK

    def test_css_only_block(self):
        parser = CommentParser("test.css")
        code = "/* header */\nbody { color: red; }\n"
        comments = parser.parse(code)
        assert len(comments) == 1
        assert comments[0].comment_type == CommentType.BLOCK
        assert comments[0].text == "/* header */"

    def test_ini_multiple_markers(self):
        parser = CommentParser("test.ini")
        code = "; comment 1\n# comment 2\nkey=value\n"
        comments = parser.parse(code)
        assert len(comments) == 2
        bodies = [c.body.strip() for c in comments]
        assert "comment 1" in bodies
        assert "comment 2" in bodies

    def test_lua_long_comment_not_line(self):
        parser = CommentParser("test.lua")
        code = "--[[ long comment ]]\nlocal x = 1\n"
        comments = parser.parse(code)
        assert len(comments) == 1
        assert comments[0].comment_type == CommentType.BLOCK
        assert "long comment" in comments[0].body

    def test_ruby_begin_not_inline(self):
        parser = CommentParser("test.rb")
        code = "x = 1 =begin no\n"
        comments = parser.parse(code)
        # =begin 不在行首，不算块注释
        assert len(comments) == 0

    def test_ruby_begin_at_line_start(self):
        parser = CommentParser("test.rb")
        code = "=begin\nhello\n=end\nx = 1\n"
        comments = parser.parse(code)
        assert len(comments) == 1
        assert comments[0].comment_type == CommentType.BLOCK


class TestStringAndCommentInterleaving:
    """字符串与注释交错测试"""

    def test_comment_after_multiline_string(self):
        parser = CommentParser("test.py")
        code = 'x = """hello\nworld"""  # after string\n'
        comments = parser.parse(code)
        assert len(comments) == 1
        assert comments[0].text == "# after string"

    def test_single_quote_triple_not_docstring(self):
        parser = CommentParser("test.py")
        code = "x = '''hello\nworld'''  # after\n"
        comments = parser.parse(code)
        assert len(comments) == 1
        assert comments[0].text == "# after"

    def test_hash_in_single_quotes(self):
        parser = CommentParser("test.py")
        code = "x = '# not comment'\n"
        assert parser.parse(code) == []

    def test_escaped_newline_in_string(self):
        parser = CommentParser("test.py")
        code = 's = "hello \\\n world"  # real comment\n'
        comments = parser.parse(code)
        assert len(comments) == 1
        assert comments[0].body.strip() == "real comment"

    def test_backtick_string_js(self):
        parser = CommentParser("test.js")
        code = "const s = `template ${x // not comment} string`;\n"
        comments = parser.parse(code)
        # 模板字符串内的 // 不应被识别为注释
        assert len(comments) == 0

    def test_url_in_code_no_comment(self):
        parser = CommentParser("test.js")
        code = "const url = 'https://example.com/path?q=1';\n"
        assert parser.parse(code) == []

    def test_nested_quotes(self):
        parser = CommentParser("test.py")
        code = "s = \"he said 'hello' to me\"  # real comment\n"
        comments = parser.parse(code)
        assert len(comments) == 1
        assert comments[0].body.strip() == "real comment"


class TestConsecutiveComments:
    """连续注释测试"""

    def test_multiple_consecutive_lines(self):
        parser = CommentParser("test.py")
        code = "# a\n# b\n# c\nimport os\n"
        comments = parser.parse(code)
        assert len(comments) == 3
        assert [c.body.strip() for c in comments] == ["a", "b", "c"]

    def test_consecutive_block_comments(self):
        parser = CommentParser("test.c")
        code = "/* a */\n/* b */\n/* c */\nint x;\n"
        comments = parser.parse(code)
        assert len(comments) == 3

    def test_mixed_standalone_and_inline(self):
        parser = CommentParser("test.py")
        code = "# standalone\nx = 1  # inline\n# another\n"
        comments = parser.parse(code)
        standalones = [c for c in comments if c.standalone]
        inlines = [c for c in comments if not c.standalone]
        assert len(standalones) == 2
        assert len(inlines) == 1


class TestProtectorEdgeCases:
    """保护器边界条件"""

    def test_restore_all_comments_lost(self):
        protector = CommentProtector()
        original = "# old\nabc()\n"
        new = "xyz_123_999()\n"
        result = protector.restore_comments(original, new, "test.py")
        assert result.lost_count == 1
        assert result.restored_count == 0

    def test_restore_comment_to_beginning(self):
        protector = CommentProtector()
        original = "# header\nimport os\n"
        new = "import os\n"
        result = protector.restore_comments(original, new, "test.py")
        assert result.restored_count == 1
        lines = result.protected_content.splitlines()
        assert lines[0] == "# header"

    def test_restore_file_with_no_trailing_newline(self):
        protector = CommentProtector()
        original = "x = 1  # inline"
        new = "x = 1"
        result = protector.restore_comments(original, new, "test.py")
        assert result.restored_count == 1
        assert "# inline" in result.protected_content

    def test_restore_multiple_inlines(self):
        protector = CommentProtector()
        original = "a = 1  # a\nb = 2  # b\nc = 3  # c\n"
        new = "a = 1\nb = 2\nc = 3\n"
        result = protector.restore_comments(original, new, "test.py")
        assert result.restored_count == 3
        lines = result.protected_content.splitlines()
        assert "# a" in lines[0]
        assert "# b" in lines[1]
        assert "# c" in lines[2]

    def test_restore_comment_after_deleted_function(self):
        protector = CommentProtector()
        original = "def old():\n    # inside\n    pass\n"
        new = ""
        result = protector.restore_comments(original, new, "test.py")
        assert result.lost_count == 1

    def test_restore_around_refactored_code(self):
        protector = CommentProtector()
        original = "# compute result\nresult = a + b\n"
        new = "result = add(a, b)\n"
        result = protector.restore_comments(original, new, "test.py")
        assert result.restored_count == 1
        assert "# compute result" in result.protected_content

    def test_protector_with_path_object(self):
        from pathlib import Path

        protector = CommentProtector()
        original = "# header\nimport os\n"
        new = "import os\n"
        result = protector.restore_comments(original, new, Path("test.py"))
        assert result.restored_count == 1


class TestStripCommentsEdgeCases:
    """strip_comments 边界测试"""

    def test_strip_preserves_line_count(self):
        parser = CommentParser("test.py")
        code = "# a\n# b\n# c\ncode\n"
        result = parser.strip_comments(code)
        assert result.count("\n") == code.count("\n")

    def test_strip_empty_file(self):
        parser = CommentParser("test.py")
        assert parser.strip_comments("") == ""

    def test_strip_no_comments(self):
        parser = CommentParser("test.py")
        code = "import os\nimport sys\n"
        assert parser.strip_comments(code) == code

    def test_inline_strip_keeps_code_indent(self):
        parser = CommentParser("test.py")
        code = "    x = 1  # comment\n"
        result = parser.strip_comments(code)
        assert result == "    x = 1\n"

    def test_standalone_strip_keeps_indent(self):
        parser = CommentParser("test.py")
        code = "    # comment\n"
        result = parser.strip_comments(code)
        assert result == "    \n"
