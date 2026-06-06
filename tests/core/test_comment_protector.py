"""
test_comment_protector.py — 注释保护器测试。

覆盖：
- 注释提取
- 注释恢复（diff 算法）
- 模糊匹配
- 行内注释和独立注释的不同处理
- 多语言文件保护
"""

import pytest

from foxcode.core.comment_protector import (
    CommentProtector,
    ProtectedComment,
    ProtectionResult,
)


class TestExtractProtected:
    """提取受保护注释测试"""

    def test_extract_python_comments(self):
        protector = CommentProtector()
        code = "# header\nimport os\nx = 1  # inline\n"
        protected = protector.extract_protected_comments(code, "test.py")
        assert len(protected) == 2
        assert all(isinstance(pc, ProtectedComment) for pc in protected)
        assert all(pc.anchor is not None for pc in protected)

    def test_extract_no_comments(self):
        protector = CommentProtector()
        code = "import os\nx = 1\n"
        protected = protector.extract_protected_comments(code, "test.py")
        assert len(protected) == 0

    def test_extract_unsupported_file(self):
        protector = CommentProtector()
        protected = protector.extract_protected_comments("binary stuff", "test.exe")
        assert len(protected) == 0


class TestRestoreBasic:
    """基本恢复测试"""

    def test_restore_simple_standalone_comment(self):
        protector = CommentProtector()
        original = "# header\nimport os\n"
        new = "import os\n"
        result = protector.restore_comments(original, new, "test.py")
        assert isinstance(result, ProtectionResult)
        assert result.restored_count == 1
        assert "# header" in result.protected_content

    def test_restore_inline_comment(self):
        protector = CommentProtector()
        original = "x = 1  # inline\n"
        new = "x = 1\n"
        result = protector.restore_comments(original, new, "test.py")
        assert result.restored_count == 1
        assert "x = 1  # inline" in result.protected_content

    def test_restore_docstring(self):
        protector = CommentProtector()
        original = 'def foo():\n    """Hello."""\n    return 1\n'
        new = "def foo():\n    return 1\n"
        result = protector.restore_comments(original, new, "test.py")
        assert result.restored_count == 1
        assert '"""Hello."""' in result.protected_content

    def test_restore_keeps_existing_comment(self):
        """如果新内容中已经有相同注释，应保留（计入 kept）"""
        protector = CommentProtector()
        original = "# header\nimport os\n"
        new = "# header\nimport os\n"
        result = protector.restore_comments(original, new, "test.py")
        assert result.kept_count == 1
        assert result.restored_count == 0

    def test_restore_no_original_no_protection(self):
        """没有原始内容时不做保护"""
        protector = CommentProtector()
        result = protector.restore_comments(
            None,
            "import os\n",
            "test.py",  # type: ignore
        )
        assert result.restored_count == 0


class TestRestoreFuzzy:
    """模糊匹配测试"""

    def test_fuzzy_match_similar_code(self):
        """AI 修改了部分代码后仍能匹配"""
        protector = CommentProtector()
        original = "# header\nresult = compute(x)\n"
        new = "result = compute(x, y)\n"
        result = protector.restore_comments(original, new, "test.py")
        assert result.restored_count == 1
        assert "# header" in result.protected_content

    def test_no_match_means_lost(self):
        """代码完全变了，找不到锚点 -> 丢失"""
        protector = CommentProtector()
        original = "# header\nresult = compute(x)\n"
        new = "totally_different_function()\n"
        result = protector.restore_comments(original, new, "test.py")
        assert result.lost_count == 1
        assert result.restored_count == 0

    def test_fuzzy_threshold_configurable(self):
        """fuzzy_threshold 可配置"""
        strict = CommentProtector(fuzzy_threshold=0.99)
        lenient = CommentProtector(fuzzy_threshold=0.3)
        original = "# header\nresult = compute_complex_expression(x, y, z)\n"
        new = "result = compute(x)\n"
        # 严格模式可能不匹配
        r_strict = strict.restore_comments(original, new, "test.py")
        # 宽松模式应该匹配
        r_lenient = lenient.restore_comments(original, new, "test.py")
        # 至少宽松应该恢复
        assert r_lenient.restored_count >= r_strict.restored_count


class TestRestoreOrdering:
    """插入顺序测试"""

    def test_multiple_standalone_comments_order(self):
        """多个独立注释按正确顺序恢复"""
        protector = CommentProtector()
        original = "# first\nimport os\n# second\nimport sys\n# third\nimport re\n"
        new = "import os\nimport sys\nimport re\n"
        result = protector.restore_comments(original, new, "test.py")
        protected = result.protected_content
        assert protected.index("# first") < protected.index("# second")
        assert protected.index("# second") < protected.index("# third")

    def test_inline_with_surrounding(self):
        """行内注释应紧贴其所在代码行"""
        protector = CommentProtector()
        original = "a = 1\nb = 2  # b comment\nc = 3\n"
        new = "a = 1\nb = 2\nc = 3\n"
        result = protector.restore_comments(original, new, "test.py")
        # # b comment 应紧跟在 b = 2 后
        lines = result.protected_content.splitlines()
        b_line = next(line for line in lines if line.startswith("b = 2"))
        assert "# b comment" in b_line


class TestRestoreCRLF:
    """CRLF 行尾测试"""

    def test_crlf_preserved(self):
        protector = CommentProtector()
        original = "# header\r\nimport os\r\n"
        new = "import os\r\n"
        result = protector.restore_comments(original, new, "test.py")
        # 输出的行尾应保持 CRLF
        assert "\r\n" in result.protected_content


class TestMultiLanguage:
    """多语言测试"""

    @pytest.mark.parametrize(
        "ext,marker",
        [
            ("test.py", "#"),
            ("test.js", "//"),
            ("test.go", "//"),
            ("test.rs", "//"),
            ("test.java", "//"),
            ("test.c", "//"),
            ("test.cpp", "//"),
            ("test.sh", "#"),
            ("test.yaml", "#"),
            ("test.toml", "#"),
            ("test.sql", "--"),
            ("test.lua", "--"),
        ],
    )
    def test_line_comment_languages(self, ext, marker):
        protector = CommentProtector()
        original = f"{marker} comment\ncode\n"
        new = "code\n"
        result = protector.restore_comments(original, new, ext)
        assert result.restored_count == 1
        assert marker in result.protected_content

    def test_javascript_block(self):
        protector = CommentProtector()
        original = "/* block */\nconst x = 1;\n"
        new = "const x = 1;\n"
        result = protector.restore_comments(original, new, "test.js")
        assert result.restored_count == 1
        assert "/* block */" in result.protected_content

    def test_html_comment(self):
        protector = CommentProtector()
        original = "<!-- header -->\n<div></div>\n"
        new = "<div></div>\n"
        result = protector.restore_comments(original, new, "test.html")
        assert result.restored_count == 1
        assert "<!-- header -->" in result.protected_content


class TestEmptyContent:
    """边界情况测试"""

    def test_empty_original(self):
        protector = CommentProtector()
        result = protector.restore_comments("", "new code\n", "test.py")
        assert result.restored_count == 0

    def test_empty_new(self):
        protector = CommentProtector()
        original = "# comment\n"
        new = ""
        result = protector.restore_comments(original, new, "test.py")
        # 锚点找不到，所有注释丢失
        assert result.lost_count == 1

    def test_identical_content(self):
        protector = CommentProtector()
        code = "# comment\nimport os\n"
        result = protector.restore_comments(code, code, "test.py")
        # 内容相同，所有注释都算 kept
        assert result.kept_count >= 1
        assert result.restored_count == 0
