"""
FoxCode 注释保护管理器 - 全局状态管理和工具入口

这个模块管理注释保护功能的全局状态：
- 是否启用（默认启用）
- 保护统计信息
- 与文件操作工具的集成接口

设计理念：
- 默认启用 - 保护功能是默认行为，符合"保护可维护性"的目标
- 通过 /cp on|off 切换
- 提供保护文件内容的统一接口
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from foxcode.core.comment_protector import (
    CommentProtector,
    ProtectedComment,
    ProtectionResult,
)

logger = logging.getLogger(__name__)


@dataclass
class ProtectionStats:
    """注释保护全局统计"""

    files_protected: int = 0  # 被保护的文件数
    comments_restored: int = 0  # 恢复的注释数
    comments_kept: int = 0  # 保留的注释数
    comments_lost: int = 0  # 丢失的注释数
    new_comments_added: int = 0  # AI 新增的注释数
    files_skipped: int = 0  # 跳过的文件数（不支持或异常）
    last_protected_file: str = ""  # 最近保护的文件
    last_result: ProtectionResult | None = None

    def summary(self) -> str:
        return (
            f"已保护 {self.files_protected} 个文件, "
            f"恢复 {self.comments_restored} 个原始注释, "
            f"保留 {self.comments_kept} 个, "
            f"丢失 {self.comments_lost} 个, "
            f"AI 新增 {self.new_comments_added} 个"
        )


class CommentProtectManager:
    """
    注释保护管理器（单例）

    管理注释保护功能的状态、配置、统计和对外接口。

    使用：
        manager = CommentProtectManager.get_instance()
        if manager.is_enabled():
            result = manager.protect_file(file_path, new_content, original_content)
    """

    _instance: ClassVar[CommentProtectManager | None] = None

    def __init__(self):
        self._enabled = True
        self._stats = ProtectionStats()
        self._protector = CommentProtector()

    @classmethod
    def get_instance(cls) -> CommentProtectManager:
        """获取全局单例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例（主要用于测试）"""
        cls._instance = None

    def is_enabled(self) -> bool:
        return self._enabled

    def enable(self) -> str:
        self._enabled = True
        return "注释保护已启用。AI 编辑文件后会自动恢复原始注释。"

    def disable(self) -> str:
        self._enabled = False
        return "注释保护已禁用。AI 编辑文件后将保留其注释改动。"

    def get_status(self) -> dict:
        return {
            "enabled": self._enabled,
            "stats": self._stats,
        }

    def get_stats(self) -> ProtectionStats:
        return self._stats

    def reset_stats(self) -> None:
        self._stats = ProtectionStats()

    def protect_file(
        self,
        file_path: str | Path,
        new_content: str,
        original_content: str | None = None,
        protected: list[ProtectedComment] | None = None,
    ) -> tuple[str, ProtectionResult]:
        """
        对文件内容应用注释保护

        Args:
            file_path: 文件路径
            new_content: AI 写入的新内容
            original_content: 文件原始内容（如果为 None 则跳过保护）
            protected: 预先提取的受保护注释

        Returns:
            (保护后的内容, ProtectionResult)
        """
        result = ProtectionResult(protected_content=new_content)

        if not self._enabled:
            return new_content, result

        if not self._protector.is_supported(file_path):
            self._stats.files_skipped += 1
            return new_content, result

        if original_content is None:
            return new_content, result

        try:
            result = self._protector.restore_comments(
                original_content, new_content, file_path, protected
            )
            self._stats.files_protected += 1
            self._stats.comments_restored += result.restored_count
            self._stats.comments_kept += result.kept_count
            self._stats.comments_lost += result.lost_count
            self._stats.new_comments_added += result.new_comments_count
            self._stats.last_protected_file = str(file_path)
            self._stats.last_result = result
            return result.protected_content, result
        except Exception as e:
            logger.error(f"注释保护失败 {file_path}: {e}")
            self._stats.files_skipped += 1
            return new_content, result

    def extract_protected(
        self,
        file_path: str | Path,
        content: str,
    ) -> list[ProtectedComment]:
        """从内容中提取受保护的注释"""
        if not self._protector.is_supported(file_path):
            return []
        return self._protector.extract_protected_comments(content, file_path)


# 全局单例便捷访问
def get_manager() -> CommentProtectManager:
    return CommentProtectManager.get_instance()
