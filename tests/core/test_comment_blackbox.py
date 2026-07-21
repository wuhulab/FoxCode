"""
test_comment_blackbox.py — 注释保护黑盒测试。

设计理念：
- 完全不依赖内部类（如 CommentRegion、AnchorInfo）
- 只通过公开接口操作：CommentProtector.restore_comments / extract_protected_comments
- 只验证输入-输出行为，不关心实现方式
- 把被测系统视为黑箱，只知其功能规格
"""

import pytest

from foxcode.core.comment_protector import CommentProtector, ProtectionResult
from foxcode.core.comment_protect_manager import CommentProtectManager


class TestBlackBoxRestoreBehavior:
    """黑盒：恢复注释的行为验证"""

    def test_single_comment_output_contains_it(self):
        protector = CommentProtector()
        result = protector.restore_comments(
            original_content="# note\nfoo()\n",
            new_content="foo()\n",
            file_path="t.py",
        )
        assert isinstance(result, ProtectionResult)
        assert "# note" in result.protected_content

    def test_missing_code_means_comment_gone(self):
        protector = CommentProtector()
        result = protector.restore_comments(
            original_content="# old note\nabc()\n",
            new_content="xyz_999()\n",
            file_path="t.py",
        )
        assert "# old note" not in result.protected_content

    def test_no_change_means_same_output(self):
        protector = CommentProtector()
        code = "# note\nfoo()\n"
        result = protector.restore_comments(code, code, "t.py")
        assert result.protected_content == code

    def test_unsupported_format_passes_through(self):
        protector = CommentProtector()
        new_content = "binary gibberish"
        result = protector.restore_comments("old", new_content, "t.exe")
        assert result.protected_content == new_content

    def test_crlf_line_endings_preserved(self):
        protector = CommentProtector()
        result = protector.restore_comments(
            "# hdr\r\ncode\r\n",
            "code\r\n",
            "t.py",
        )
        assert "\r\n" in result.protected_content
        # 不应混入仅 \n
        assert result.protected_content.endswith("\r\n")

    def test_inline_comment_attaches_back(self):
        protector = CommentProtector()
        result = protector.restore_comments(
            "x = 1  # cfg\n",
            "x = 1\n",
            "t.py",
        )
        lines = result.protected_content.splitlines()
        assert any("# cfg" in line for line in lines)

    def test_docstring_preserved_as_comment(self):
        protector = CommentProtector()
        result = protector.restore_comments(
            'def f():\n    """docs"""\n    pass\n',
            "def f():\n    pass\n",
            "t.py",
        )
        assert '"""docs"""' in result.protected_content

    def test_multiple_comments_all_present(self):
        protector = CommentProtector()
        result = protector.restore_comments(
            "# a\na = 1\n# b\nb = 2\n# c\nc = 3\n",
            "a = 1\nb = 2\nc = 3\n",
            "t.py",
        )
        assert "# a" in result.protected_content
        assert "# b" in result.protected_content
        assert "# c" in result.protected_content


class TestBlackBoxErrorHandling:
    """黑盒：异常与边界输入处理"""

    def test_none_original_returns_unchanged(self):
        protector = CommentProtector()
        result = protector.restore_comments(None, "x = 1\n", "t.py")
        assert result.protected_content == "x = 1\n"

    def test_empty_original_no_crash(self):
        protector = CommentProtector()
        result = protector.restore_comments("", "x = 1\n", "t.py")
        assert result.protected_content == "x = 1\n"

    def test_empty_new_no_crash(self):
        protector = CommentProtector()
        result = protector.restore_comments(
            "# comment\n",
            "",
            "t.py",
        )
        assert result.protected_content == ""

    def test_both_empty_no_crash(self):
        protector = CommentProtector()
        result = protector.restore_comments("", "", "t.py")
        assert result.protected_content == ""

    def test_unicode_paths_accepted(self):
        protector = CommentProtector()
        result = protector.restore_comments(
            "# 注释\n代码\n",
            "代码\n",
            "测试.py",
        )
        assert "# 注释" in result.protected_content


class TestBlackBoxManagerInterface:
    """黑盒：仅通过 CommentProtectManager 的公开接口测试"""

    def setup_method(self):
        CommentProtectManager.reset_instance()
        self.manager = CommentProtectManager.get_instance()
        self.manager.enable()
        self.manager.reset_stats()

    def test_protect_file_returns_tuple(self):
        content, result = self.manager.protect_file(
            "t.py",
            "foo()\n",
            "# note\nfoo()\n",
        )
        assert isinstance(content, str)
        assert isinstance(result, ProtectionResult)
        assert "# note" in content

    def test_disable_skips_protection(self):
        self.manager.disable()
        content, result = self.manager.protect_file(
            "t.py",
            "foo()\n",
            "# note\nfoo()\n",
        )
        assert "# note" not in content
        assert result.restored_count == 0

    def test_stats_are_public(self):
        self.manager.protect_file(
            "t.py",
            "foo()\n",
            "# note\nfoo()\n",
        )
        stats = self.manager.get_stats()
        # 我们只关心存在性，不关心内部字段名是否变化
        assert hasattr(stats, "files_protected")
        assert hasattr(stats, "comments_restored")
        assert hasattr(stats, "summary")

    def test_extract_returns_list(self):
        comments = self.manager.extract_protected("t.py", "# a\n# b\ncode\n")
        assert isinstance(comments, list)
        assert len(comments) == 2

    def test_extract_unsupported_returns_empty(self):
        comments = self.manager.extract_protected("t.bin", "# a\ncode\n")
        assert comments == []


class TestBlackBoxCrossLanguage:
    """黑盒：跨语言只验证输入输出"""

    @pytest.mark.parametrize(
        "file_path,comment_syntax",
        [
            ("app.py", "#"),
            ("app.js", "//"),
            ("app.java", "//"),
            ("app.c", "//"),
            ("app.go", "//"),
            ("app.rs", "//"),
            ("app.sh", "#"),
            ("app.yaml", "#"),
            ("app.sql", "--"),
            ("app.lua", "--"),
        ],
    )
    def test_comment_preserved_across_languages(self, file_path, comment_syntax):
        protector = CommentProtector()
        original = f"{comment_syntax} important note\nprint('hello')\n"
        new = "print('hello')\n"
        result = protector.restore_comments(original, new, file_path)
        assert comment_syntax in result.protected_content
        assert "important note" in result.protected_content

    def test_html_comment_preserved(self):
        protector = CommentProtector()
        original = "<!-- important note -->\n<div></div>\n"
        new = "<div></div>\n"
        result = protector.restore_comments(original, new, "app.html")
        assert "<!-- important note -->" in result.protected_content

    def test_css_comment_preserved(self):
        protector = CommentProtector()
        original = "/* important note */\nbody { color: red; }\n"
        new = "body { color: red; }\n"
        result = protector.restore_comments(original, new, "app.css")
        assert "/* important note */" in result.protected_content

    def test_block_comment_preserved(self):
        protector = CommentProtector()
        original = "/* block note */\nconst x = 1;\n"
        new = "const x = 1;\n"
        result = protector.restore_comments(original, new, "app.js")
        assert "/* block note */" in result.protected_content

    def test_multiline_block_preserved(self):
        protector = CommentProtector()
        original = "/* line1\n * line2\n */\nint x;\n"
        new = "int x;\n"
        result = protector.restore_comments(original, new, "app.c")
        assert "line1" in result.protected_content
        assert "line2" in result.protected_content
