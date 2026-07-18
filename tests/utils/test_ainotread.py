"""
test_ainotread.py — .ainotread 规则模块测试。

覆盖：
- 基本忽略模式（*.pyc, secrets/）
- 锚定规则（/foo.txt）
- 否定规则（!important.pyc）
- 层级覆盖（父目录规则被子目录否定规则覆盖）
- 空项目/无 .ainotread
- AINotReadManager 缓存
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from foxcode.utils.ainotread import (
    AINotReadManager,
    _collect_ainotread_specs,
    _find_project_root,
    is_ainotread,
)


class TestFindProjectRoot:
    """项目根目录探测测试"""

    def test_finds_git_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".git").mkdir()
            sub = root / "sub" / "deep"
            sub.mkdir(parents=True)
            assert _find_project_root(sub) == root

    def test_finds_ainotread_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".ainotread").write_text("*.pyc\n")
            sub = root / "sub"
            sub.mkdir()
            assert _find_project_root(sub) == root

    def test_fallback_to_cwd(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            isolated = Path(tmpdir) / "isolated"
            isolated.mkdir()
            result = _find_project_root(isolated)
            assert result == Path.cwd()


class TestBasicIgnore:
    """基本忽略规则测试"""

    def test_ignore_star_pattern(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".ainotread").write_text("*.pyc\n")

            (root / "foo.pyc").touch()
            (root / "bar.txt").touch()

            assert is_ainotread(root / "foo.pyc", root) is True
            assert is_ainotread(root / "bar.txt", root) is False

    def test_ignore_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".ainotread").write_text("secrets/\n")
            secrets = root / "secrets"
            secrets.mkdir()
            (secrets / "password.txt").touch()

            assert is_ainotread(secrets, root) is True
            assert is_ainotread(secrets / "password.txt", root) is True

    def test_anchored_pattern(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".ainotread").write_text("/foo.txt\n")

            (root / "foo.txt").touch()
            sub = root / "sub"
            sub.mkdir()
            (sub / "foo.txt").touch()

            assert is_ainotread(root / "foo.txt", root) is True
            assert is_ainotread(sub / "foo.txt", root) is False


class TestNegation:
    """否定规则测试"""

    def test_negation_overrides_ignore(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".ainotread").write_text("*.pyc\n!important.pyc\n")

            (root / "foo.pyc").touch()
            (root / "important.pyc").touch()

            assert is_ainotread(root / "foo.pyc", root) is True
            assert is_ainotread(root / "important.pyc", root) is False


class TestHierarchy:
    """层级规则测试"""

    def test_child_rule_overrides_parent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".ainotread").write_text("*.pyc\n")
            sub = root / "sub"
            sub.mkdir()
            (sub / ".ainotread").write_text("!important.pyc\n")

            (root / "foo.pyc").touch()
            (sub / "foo.pyc").touch()
            (sub / "important.pyc").touch()

            assert is_ainotread(root / "foo.pyc", root) is True
            assert is_ainotread(sub / "foo.pyc", root) is True
            assert is_ainotread(sub / "important.pyc", root) is False

    def test_deeply_nested_rules(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".ainotread").write_text("*.log\n")
            sub = root / "a" / "b"
            sub.mkdir(parents=True)
            (sub / ".ainotread").write_text("!debug.log\n")

            (sub / "info.log").touch()
            (sub / "debug.log").touch()

            assert is_ainotread(sub / "info.log", root) is True
            assert is_ainotread(sub / "debug.log", root) is False


class TestNoRules:
    """无规则场景测试"""

    def test_no_ainotread_returns_false(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "foo.txt").touch()
            assert is_ainotread(root / "foo.txt", root) is False


class TestManager:
    """AINotReadManager 缓存测试"""

    def test_caching(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".ainotread").write_text("*.secret\n")
            (root / "key.secret").touch()

            manager = AINotReadManager()
            manager.set_root(root)

            assert manager.is_ainotread(root / "key.secret") is True
            assert manager.is_ainotread(root / "key.secret") is True  # 命中缓存

            manager.clear_cache()
            assert manager.is_ainotread(root / "key.secret") is True

    def test_cache_invalidation_on_rule_change(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".ainotread").write_text("*.secret\n")
            (root / "key.secret").touch()

            manager = AINotReadManager()
            manager.set_root(root)
            assert manager.is_ainotread(root / "key.secret") is True

            # 修改规则后必须手动清缓存才能读到新规则
            (root / ".ainotread").write_text("\n")
            assert manager.is_ainotread(root / "key.secret") is True  # 仍是旧缓存
            manager.clear_cache()
            assert manager.is_ainotread(root / "key.secret") is False
