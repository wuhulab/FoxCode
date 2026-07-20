"""
FoxCode AINotRead 支持模块

提供类似 .gitignore 的文件过滤机制，但用于阻止 AI 读取特定文件。
项目各层级都可以放置 .ainotread 文件，规则从根目录到文件所在目录依次累积生效。
子目录规则可以通过 ``!`` 否定模式覆盖父目录规则。

语法与 .gitignore 完全一致：
- ``*.pyc`` — 忽略所有 .pyc 文件
- ``secrets/`` — 忽略整个 secrets 目录
- ``!important.pyc`` — 不忽略 important.pyc（覆盖前面的规则）
- ``/foo.txt`` — 只匹配当前目录的 foo.txt
- ``#`` 开头为注释

使用方式：
    from foxcode.utils.ainotread import is_ainotread

    if is_ainotread("path/to/file"):
        # AI 不可读取此文件
        pass
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pathspec

logger = logging.getLogger(__name__)


def _find_project_root(start_path: Path) -> Path:
    """
    从 start_path 向上查找项目根目录。

    优先匹配包含 .git 目录或 .ainotread 文件的目录，
    未找到则回退到当前工作目录。
    """
    current = start_path.resolve()
    if current.is_file():
        current = current.parent

    visited: set[str] = set()
    while str(current) not in visited:
        visited.add(str(current))
        if (current / ".git").exists() or (current / ".ainotread").exists():
            return current
        if current == current.parent:
            break
        current = current.parent

    return Path.cwd()


def _collect_ainotread_specs(
    root: Path,
    target_path: Path,
) -> list[tuple[Path, pathspec.GitIgnoreSpec]]:
    """
    从 root 到 target_path 所在目录，收集所有 .ainotread 规则。

    Returns:
        [(rule_directory, GitIgnoreSpec), ...] 按从根到叶的顺序
    """
    root = root.resolve()
    target_path = target_path.resolve()

    # 确定需要检查的目录层级：root -> ... -> target_path 的父目录
    check_dirs = [root]
    try:
        rel_target = target_path.relative_to(root)
        dir_parts = rel_target.parts[:-1] if target_path.is_file() else rel_target.parts
        for i in range(len(dir_parts)):
            check_dirs.append(root / Path(*dir_parts[: i + 1]))
    except ValueError:
        # target_path 不在 root 下，仅保留 root 自身
        pass

    specs: list[tuple[Path, pathspec.GitIgnoreSpec]] = []
    for d in check_dirs:
        ainotread_file = d / ".ainotread"
        if ainotread_file.exists() and ainotread_file.is_file():
            try:
                lines = ainotread_file.read_text(encoding="utf-8").splitlines()
                spec = pathspec.GitIgnoreSpec.from_lines(lines)
                specs.append((d, spec))
            except Exception as e:
                logger.warning(f"无法解析 .ainotread 文件 {ainotread_file}: {e}", exc_info=True)

    return specs


def is_ainotread(
    file_path: str | Path,
    root_path: str | Path | None = None,
) -> bool:
    """
    检查指定路径是否被 .ainotread 规则阻止（AI 不可读取）。

    规则按 gitignore 语义累积应用：
    从根目录到文件所在目录的 .ainotread 文件依次生效，
    子目录的规则可以通过 ``!`` 否定模式覆盖父目录规则。

    Args:
        file_path: 要检查的文件或目录路径
        root_path: 项目根目录，用于确定搜索范围。
            为 ``None`` 时自动向上查找 ``.git`` 或 ``.ainotread`` 所在目录作为根。

    Returns:
        ``True`` 表示该路径被阻止（AI 不可读取），否则 ``False``。
    """
    path = Path(file_path).resolve()

    if root_path is None:
        root_path = _find_project_root(path)
    root = Path(root_path).resolve()

    # 如果 path 是一个不存在的相对路径，基于 root 解析
    if not path.exists() and not path.is_absolute():
        path = (root / file_path).resolve()

    specs = _collect_ainotread_specs(root, path)
    if not specs:
        return False

    ignored: bool | None = None

    for rule_dir, spec in specs:
        try:
            rel_path = path.relative_to(rule_dir)
            rel_path_str = rel_path.as_posix()
            if path.is_dir():
                rel_path_str += "/"
            result = spec.check_file(rel_path_str)
            if result.include is True:
                ignored = True
            elif result.include is False:
                ignored = False
            # result.include is None -> 未提及，保持当前状态
        except ValueError:
            continue
        except Exception as e:
            logger.debug(f".ainotread 检查异常: {e}", exc_info=True)

    return ignored if ignored is not None else False


class AINotReadManager:
    """
    .ainotread 规则管理器，带缓存以提高频繁检查场景的性能。
    """

    def __init__(self) -> None:
        self._root: Path | None = None
        self._specs_cache: dict[str, list[tuple[Path, pathspec.GitIgnoreSpec]]] = {}
        self._result_cache: dict[str, bool] = {}

    def set_root(self, root_path: str | Path) -> None:
        """设置项目根目录并清空缓存。"""
        self._root = Path(root_path).resolve()
        self._specs_cache.clear()
        self._result_cache.clear()

    def is_ainotread(self, file_path: str | Path) -> bool:
        """检查路径是否被阻止（带缓存）。"""
        path = Path(file_path).resolve()
        cache_key = str(path)

        if cache_key in self._result_cache:
            return self._result_cache[cache_key]

        root = self._root or _find_project_root(path)
        root_key = str(root)

        specs = self._specs_cache.get(root_key)
        if specs is None:
            specs = _collect_ainotread_specs(root, path)
            self._specs_cache[root_key] = specs

        result = False
        if specs:
            ignored: bool | None = None
            for rule_dir, spec in specs:
                try:
                    rel_path = path.relative_to(rule_dir)
                    rel_path_str = rel_path.as_posix()
                    if path.is_dir():
                        rel_path_str += "/"
                    result_obj = spec.check_file(rel_path_str)
                    if result_obj.include is True:
                        ignored = True
                    elif result_obj.include is False:
                        ignored = False
                except ValueError:
                    continue
                except Exception as e:
                    logger.debug(f".ainotread 检查异常: {e}", exc_info=True)
            result = ignored if ignored is not None else False

        self._result_cache[cache_key] = result
        return result

    def clear_cache(self) -> None:
        """清空所有缓存。"""
        self._specs_cache.clear()
        self._result_cache.clear()


# 全局管理器实例
_manager: AINotReadManager | None = None


def get_manager() -> AINotReadManager:
    """获取全局 AINotReadManager 实例。"""
    global _manager
    if _manager is None:
        _manager = AINotReadManager()
    return _manager
