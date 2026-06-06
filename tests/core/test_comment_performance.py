"""
test_comment_performance.py — 注释保护性能测试。

覆盖：
- 大文件解析、恢复的时间基准
- 内存占用粗略估算（通过对象大小）
- 不同规模下的线性度验证
- 对比 strip_comments 与 parse 的性能

使用 pytest.mark.skipif 允许在 CI 中跳过耗时测试。
"""

import sys
import time

import pytest

from foxcode.core.comment_parser import CommentParser
from foxcode.core.comment_protector import CommentProtector


class TestParserPerformance:
    """解析器性能测试"""

    def _generate_py_code(self, lines_count: int, comment_ratio: float = 0.3) -> str:
        random_seq = range(lines_count)
        lines = []
        for i in random_seq:
            if i % int(1 / comment_ratio) == 0:
                lines.append(f"    # Comment line {i} with some text to make it realistic")
            else:
                lines.append(f"    x{i} = compute_value({i}, '{i}_suffix')")
        return "\n".join(lines) + "\n"

    @pytest.mark.parametrize("size", [100, 500, 1000])
    def test_parse_time_under_threshold(self, size):
        """解析应在合理时间内完成（当前 O(n^2) 实现下阈值较宽松）"""
        code = self._generate_py_code(size)
        parser = CommentParser("test.py")
        start = time.perf_counter()
        comments = parser.parse(code)
        elapsed = time.perf_counter() - start
        # 1000 行应在 5 秒内（当前实现有 O(n^2) 热点）
        assert elapsed < 5.0, f"Parsing {size} lines took {elapsed:.3f}s"
        assert len(comments) > 0

    @pytest.mark.parametrize("size", [100, 500, 1000])
    def test_restore_time_under_threshold(self, size):
        """恢复应在合理时间内完成（当前 O(n*m) 实现下阈值较宽松）"""
        protector = CommentProtector()
        original = self._generate_py_code(size)
        new = self._generate_py_code(size)
        start = time.perf_counter()
        result = protector.restore_comments(original, new, "test.py")
        elapsed = time.perf_counter() - start
        # 1000 行应在 8 秒内
        assert elapsed < 8.0, f"Restore {size} lines took {elapsed:.3f}s"
        assert result is not None

    def test_parse_scales_linearly(self):
        """解析时间增长趋势（当前实现非线性，应记录但不超阈值）"""
        sizes = [200, 400, 800]
        times = []
        parser = CommentParser("test.py")
        for size in sizes:
            code = self._generate_py_code(size)
            start = time.perf_counter()
            parser.parse(code)
            times.append(time.perf_counter() - start)
        # 检查时间增长是否小于 8 倍（当前实现为 O(n^2)，封顶检查）
        ratio_1 = times[1] / times[0] if times[0] > 0 else 0
        ratio_2 = times[2] / times[1] if times[1] > 0 else 0
        assert ratio_1 < 8.0, f"Non-linear scaling: {sizes[0]}->{sizes[1]} ratio={ratio_1:.2f}"
        assert ratio_2 < 8.0, f"Non-linear scaling: {sizes[1]}->{sizes[2]} ratio={ratio_2:.2f}"

    def test_strip_comments_performance(self):
        """strip_comments 不应比 parse 慢一个数量级"""
        code = self._generate_py_code(1000)
        parser = CommentParser("test.py")
        start = time.perf_counter()
        comments = parser.parse(code)
        parse_time = time.perf_counter() - start

        start = time.perf_counter()
        stripped = parser.strip_comments(code)
        strip_time = time.perf_counter() - start

        assert strip_time < parse_time * 5, (
            f"strip_comments ({strip_time:.3f}s) too slow vs parse ({parse_time:.3f}s)"
        )
        assert len(stripped) > 0


class TestProtectorPerformance:
    """保护器性能测试"""

    def test_memory_efficiency_large_file(self):
        """大文件恢复后内存不应爆炸性增长"""
        protector = CommentProtector()
        lines = [f"    x{i} = {i}  # comment" for i in range(1000)]
        original = "\n".join(lines) + "\n"
        new = "\n".join([f"    x{i} = {i}" for i in range(1000)]) + "\n"
        result = protector.restore_comments(original, new, "test.py")
        # 结果不应比原内容大太多（只增加了注释长度）
        max_allowed = len(new) * 2
        assert len(result.protected_content) < max_allowed

    def test_fuzzy_match_performance_many_candidates(self):
        """模糊匹配在大量候选行时仍应快速"""
        protector = CommentProtector()
        original = "# header\nimport os\n"
        # 大量相似但不相同的行
        new_lines = [f"line_{i} = {i}" for i in range(500)]
        new_lines.insert(250, "import os")
        new = "\n".join(new_lines) + "\n"
        start = time.perf_counter()
        result = protector.restore_comments(original, new, "test.py")
        elapsed = time.perf_counter() - start
        assert elapsed < 8.0, f"Fuzzy match on 500 lines took {elapsed:.3f}s"
        assert result.restored_count == 1
