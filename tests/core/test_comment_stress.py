"""
test_comment_stress.py — 注释保护压力测试。

覆盖：
- 超大文件解析（数万行代码与注释）
- 大量注释密集分布
- 快速连续调用保护器（高并发模拟）
- 极端长行、深层嵌套块注释
- 文件内容突变（AI 完全重写）
"""

import logging
import random
import string

import pytest

logger = logging.getLogger(__name__)

from foxcode.core.comment_parser import CommentParser
from foxcode.core.comment_protector import CommentProtector


class TestLargeFileParsing:
    """大文件解析压力测试"""

    def test_parse_1000_lines(self):
        lines = [f"x{i} = {i}  # comment {i}" for i in range(1000)]
        code = "\n".join(lines) + "\n"
        parser = CommentParser("test.py")
        comments = parser.parse(code)
        assert len(comments) == 1000

    def test_parse_10000_lines(self):
        lines = [f"x{i} = {i}  # c{i}" for i in range(10000)]
        code = "\n".join(lines) + "\n"
        parser = CommentParser("test.py")
        comments = parser.parse(code)
        assert len(comments) == 10000
        # 检查首尾
        assert comments[0].body.strip() == "c0"
        assert comments[-1].body.strip() == "c9999"

    def test_parse_dense_block_comments(self):
        blocks = []
        for i in range(500):
            blocks.append(f"/* block {i} */\ncode{i}();")
        code = "\n".join(blocks) + "\n"
        parser = CommentParser("test.c")
        comments = parser.parse(code)
        assert len(comments) == 500

    def test_parse_deeply_nested_looking_block(self):
        """块注释内部包含 /* 样式文本（不应提前结束）"""
        inner = "/* not a real nested block */"
        code = f"/* start\n{inner}\nend */\nint x;\n"
        parser = CommentParser("test.c")
        comments = parser.parse(code)
        assert len(comments) == 1
        assert "not a real nested block" in comments[0].body

    def test_parse_very_long_single_line(self):
        inner = "x" * 50000
        code = f"# {inner}\n"
        parser = CommentParser("test.py")
        comments = parser.parse(code)
        assert len(comments) == 1
        # body 包含 # 后的空格，所以是 50001
        assert len(comments[0].body) == 50001

    def test_parse_multiple_languages_batch(self):
        exts = ["py", "js", "c", "java", "go", "rs", "rb", "php", "lua", "sql", "sh", "html", "css"]
        for ext in exts:
            parser = CommentParser(f"test.{ext}")
            comments = parser.parse(f"code\n")
            assert isinstance(comments, list)


class TestRestoreStress:
    """注释恢复压力测试"""

    def test_restore_massive_comments(self):
        """恢复 500 个独立注释"""
        protector = CommentProtector()
        original_lines = [f"# comment {i}\ncode{i}()" for i in range(500)]
        original = "\n".join(original_lines) + "\n"
        new_lines = [f"code{i}()" for i in range(500)]
        new = "\n".join(new_lines) + "\n"
        result = protector.restore_comments(original, new, "test.py")
        assert result.restored_count == 500
        assert result.lost_count == 0

    def test_restore_after_massive_refactor(self):
        """AI 完全重排代码顺序后恢复注释"""
        protector = CommentProtector()
        original = "# a\na = 1\n# b\nb = 2\n# c\nc = 3\n"
        # AI 把顺序改了
        new = "b = 2\nc = 3\na = 1\n"
        result = protector.restore_comments(original, new, "test.py")
        # 模糊匹配应能全部恢复
        assert result.restored_count == 3
        assert result.lost_count == 0

    def test_restore_with_many_lost(self):
        """几乎所有代码都变了，大量注释丢失"""
        protector = CommentProtector()
        original = "\n".join([f"# c{i}\nabc_{i}()" for i in range(50)]) + "\n"
        new = "\n".join([f"xyz_{i}_completely_different()" for i in range(50)]) + "\n"
        result = protector.restore_comments(original, new, "test.py")
        assert result.lost_count == 50
        assert result.restored_count == 0

    def test_restore_sequential_calls_no_leak(self):
        """连续调用保护器不应有状态泄漏"""
        protector = CommentProtector()
        for i in range(100):
            original = f"# comment {i}\nfn_{i}()\n"
            new = f"fn_{i}()\n"
            result = protector.restore_comments(original, new, "test.py")
            assert result.restored_count == 1

    def test_restore_huge_file_with_few_comments(self):
        """大文件只有少量注释"""
        protector = CommentProtector()
        lines = [f"x{i} = {i}" for i in range(5000)]
        lines[1000] = "# important comment"
        lines[2000] = "# another one"
        original = "\n".join(lines) + "\n"
        new = "\n".join(lines) + "\n"
        result = protector.restore_comments(original, new, "test.py")
        assert result.kept_count == 2


class TestRandomizedContent:
    """随机内容压力测试"""

    def test_random_code_no_crash(self):
        """随机生成的代码不应导致解析器崩溃"""
        parser = CommentParser("test.py")
        random.seed(42)
        for _ in range(50):
            lines = []
            for _ in range(200):
                kind = random.choice(["code", "comment", "string", "mixed"])
                if kind == "code":
                    lines.append(f"x = '{random.randint(0, 999)}'")
                elif kind == "comment":
                    lines.append(f"# {random.choice(string.ascii_letters * 10)}")
                elif kind == "string":
                    safe = "".join(random.choices(string.ascii_letters + " ", k=20))
                    lines.append(f's = "{safe}"')
                else:
                    lines.append(f"x = 1  # {random.choice(string.ascii_letters * 10)}")
            code = "\n".join(lines) + "\n"
            comments = parser.parse(code)
            assert isinstance(comments, list)
            for c in comments:
                assert c.start_line >= 0
                assert c.end_line >= c.start_line

    def test_random_multilang_no_crash(self):
        """在多种语言上运行随机内容"""
        random.seed(123)
        exts = ["py", "js", "c", "java", "html", "css", "sql", "lua"]
        for ext in exts:
            parser = CommentParser(f"test.{ext}")
            for _ in range(10):
                chars = "".join(random.choices(string.printable, k=300))
                try:
                    parser.parse(chars)
                except Exception as e:
                    logger.warning(f"Parser crashed on {ext}: {e}", exc_info=True)
                    pytest.fail(f"Parser crashed on {ext}: {e}")
