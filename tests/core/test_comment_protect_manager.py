"""
test_comment_protect_manager.py — 注释保护管理器测试。
"""

from foxcode.core.comment_protect_manager import (
    CommentProtectManager,
    ProtectionStats,
    get_manager,
)


class TestManager:
    """管理器测试"""

    def test_default_enabled(self):
        manager = CommentProtectManager.get_instance()
        manager.reset_stats()
        assert manager.is_enabled() is True

    def test_disable(self):
        manager = CommentProtectManager.get_instance()
        manager.disable()
        assert manager.is_enabled() is False
        # 重新启用
        manager.enable()
        assert manager.is_enabled() is True

    def test_get_instance_singleton(self):
        m1 = CommentProtectManager.get_instance()
        m2 = CommentProtectManager.get_instance()
        assert m1 is m2

    def test_get_manager_helper(self):
        m1 = get_manager()
        m2 = get_manager()
        assert m1 is m2

    def test_reset_instance(self):
        CommentProtectManager.reset_instance()
        m1 = CommentProtectManager.get_instance()
        CommentProtectManager.reset_instance()
        m2 = CommentProtectManager.get_instance()
        assert m1 is not m2


class TestProtectFile:
    """protect_file 接口测试"""

    def test_protect_when_disabled(self):
        manager = CommentProtectManager.get_instance()
        manager.disable()
        result, prot = manager.protect_file("test.py", "import os\n", "# header\nimport os\n")
        # 禁用时直接返回原内容
        assert result == "import os\n"
        assert prot.restored_count == 0

    def test_protect_when_enabled(self):
        manager = CommentProtectManager.get_instance()
        manager.enable()
        manager.reset_stats()
        result, prot = manager.protect_file("test.py", "import os\n", "# header\nimport os\n")
        assert prot.restored_count == 1
        assert "# header" in result

    def test_protect_unsupported_file(self):
        manager = CommentProtectManager.get_instance()
        manager.enable()
        result, prot = manager.protect_file("test.exe", "binary", "binary")
        # 不支持的文件应跳过
        assert result == "binary"
        assert prot.restored_count == 0

    def test_protect_no_original(self):
        manager = CommentProtectManager.get_instance()
        manager.enable()
        result, prot = manager.protect_file("test.py", "import os\n", None)
        # 没有原始内容不保护
        assert result == "import os\n"
        assert prot.restored_count == 0


class TestStats:
    """统计信息测试"""

    def test_stats_updated(self):
        manager = CommentProtectManager.get_instance()
        manager.enable()
        manager.reset_stats()
        manager.protect_file("test.py", "import os\n", "# header\nimport os\n")
        stats = manager.get_stats()
        assert stats.files_protected == 1
        assert stats.comments_restored == 1

    def test_stats_reset(self):
        manager = CommentProtectManager.get_instance()
        manager.reset_stats()
        manager.protect_file("test.py", "import os\n", "# header\nimport os\n")
        assert manager.get_stats().files_protected >= 1
        manager.reset_stats()
        assert manager.get_stats().files_protected == 0

    def test_stats_summary(self):
        stats = ProtectionStats(files_protected=5, comments_restored=10)
        summary = stats.summary()
        assert "5" in summary
        assert "10" in summary
