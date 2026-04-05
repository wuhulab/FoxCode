"""
FoxCode OpenSpace 模块

实现 AI 经验知识存储系统，用于记录 AI 踩过的坑和注意事项。
参考 HKUDS OpenSpace 项目的设计理念。

功能特点：
1. 存储经验教训（每个文件不超过 500 字）
2. 每次启动 foxcode 时自动加载到上下文
3. 支持启用/禁用控制
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MAX_EXPERIENCE_CHARS = 500


class ExperienceCategory(str, Enum):
    """经验分类"""
    BUG_FIX = "bug_fix"
    BEST_PRACTICE = "best_practice"
    PITFALL = "pitfall"
    PERFORMANCE = "performance"
    SECURITY = "security"
    ARCHITECTURE = "architecture"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    GENERAL = "general"


@dataclass
class Experience:
    """
    经验条目
    
    记录 AI 在开发过程中踩过的坑和学到的教训
    """
    id: str
    title: str
    content: str
    category: ExperienceCategory = ExperienceCategory.GENERAL
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    author: str = "AI"
    project: str = ""
    enabled: bool = True
    
    def __post_init__(self):
        if len(self.content) > MAX_EXPERIENCE_CHARS:
            logger.warning(
                f"经验内容超过 {MAX_EXPERIENCE_CHARS} 字，将被截断: {self.id}"
            )
            self.content = self.content[:MAX_EXPERIENCE_CHARS]
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "category": self.category.value,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "author": self.author,
            "project": self.project,
            "enabled": self.enabled,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Experience":
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            content=data.get("content", ""),
            category=ExperienceCategory(data.get("category", "general")),
            tags=data.get("tags", []),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            author=data.get("author", "AI"),
            project=data.get("project", ""),
            enabled=data.get("enabled", True),
        )
    
    def to_prompt_context(self) -> str:
        """
        生成用于注入到系统提示的内容
        
        Returns:
            格式化的提示内容
        """
        return f"""### {self.title}
分类: {self.category.value} | 标签: {', '.join(self.tags) if self.tags else '无'}

{self.content}
"""


class OpenSpaceManager:
    """
    OpenSpace 管理器
    
    管理 AI 经验知识的存储、加载和上下文注入
    """
    
    def __init__(self, space_dir: Path | None = None):
        """
        初始化管理器
        
        Args:
            space_dir: 经验文件存储目录，默认为 ~/.foxcode/space/
        """
        if space_dir is None:
            space_dir = Path.home() / ".foxcode" / "space"
        
        self.space_dir = space_dir
        self._experiences: dict[str, Experience] = {}
        self._enabled: bool = True
        self._ai_auto_summarize: bool = False
        self._state_file = space_dir / "open_space_state.json"
        self._logger = logging.getLogger("foxcode.open_space")
        
        self._ensure_directory()
        self._load_state()
    
    def _ensure_directory(self) -> None:
        """确保目录存在"""
        self.space_dir.mkdir(parents=True, exist_ok=True)
        self._logger.debug(f"OpenSpace 目录: {self.space_dir}")
    
    def _load_state(self) -> None:
        """加载状态（启用/禁用/AI自动总结）"""
        if self._state_file.exists():
            try:
                with open(self._state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                    self._enabled = state.get("enabled", True)
                    self._ai_auto_summarize = state.get("ai_auto_summarize", False)
                    self._logger.info(f"OpenSpace 状态: {'启用' if self._enabled else '禁用'}, AI自动总结: {'启用' if self._ai_auto_summarize else '禁用'}")
            except Exception as e:
                self._logger.warning(f"加载状态文件失败: {e}")
                self._enabled = True
                self._ai_auto_summarize = False
    
    def _save_state(self) -> None:
        """保存状态"""
        try:
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump({
                    "enabled": self._enabled,
                    "ai_auto_summarize": self._ai_auto_summarize,
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._logger.error(f"保存状态文件失败: {e}")
    
    @property
    def enabled(self) -> bool:
        """是否启用"""
        return self._enabled
    
    @property
    def ai_auto_summarize(self) -> bool:
        """是否启用 AI 自动总结"""
        return self._ai_auto_summarize
    
    def enable(self) -> None:
        """启用 OpenSpace"""
        self._enabled = True
        self._save_state()
        self._logger.info("OpenSpace 已启用")
    
    def disable(self) -> None:
        """禁用 OpenSpace"""
        self._enabled = False
        self._save_state()
        self._logger.info("OpenSpace 已禁用")
    
    def enable_ai_summarize(self) -> None:
        """启用 AI 自动总结"""
        self._ai_auto_summarize = True
        self._save_state()
        self._logger.info("AI 自动总结已启用")
    
    def disable_ai_summarize(self) -> None:
        """禁用 AI 自动总结"""
        self._ai_auto_summarize = False
        self._save_state()
        self._logger.info("AI 自动总结已禁用")
    
    def toggle(self) -> bool:
        """
        切换启用状态
        
        Returns:
            切换后的状态
        """
        self._enabled = not self._enabled
        self._save_state()
        return self._enabled
    
    def load_all(self) -> int:
        """
        加载所有经验文件
        
        Returns:
            成功加载的经验数量
        """
        if not self.space_dir.exists():
            self._logger.warning(f"经验目录不存在: {self.space_dir}")
            return 0
        
        loaded = 0
        for exp_file in self.space_dir.glob("*.json"):
            if exp_file.name == "open_space_state.json":
                continue
            
            try:
                with open(exp_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    exp = Experience.from_dict(data)
                    self._experiences[exp.id] = exp
                    loaded += 1
            except Exception as e:
                self._logger.error(f"加载经验文件失败 {exp_file}: {e}")
        
        self._logger.info(f"加载了 {loaded} 条经验")
        return loaded
    
    def save(self, experience: Experience) -> bool:
        """
        保存经验到文件
        
        Args:
            experience: 经验对象
            
        Returns:
            是否保存成功
        """
        if not experience.id:
            self._logger.error("经验 ID 不能为空")
            return False
        
        exp_file = self.space_dir / f"{experience.id}.json"
        
        try:
            with open(exp_file, "w", encoding="utf-8") as f:
                json.dump(experience.to_dict(), f, ensure_ascii=False, indent=2)
            
            self._experiences[experience.id] = experience
            self._logger.info(f"保存经验: {experience.id}")
            return True
            
        except Exception as e:
            self._logger.error(f"保存经验失败: {e}")
            return False
    
    def delete(self, exp_id: str) -> bool:
        """
        删除经验
        
        Args:
            exp_id: 经验 ID
            
        Returns:
            是否删除成功
        """
        exp_file = self.space_dir / f"{exp_id}.json"
        
        try:
            if exp_file.exists():
                exp_file.unlink()
            
            if exp_id in self._experiences:
                del self._experiences[exp_id]
            
            self._logger.info(f"删除经验: {exp_id}")
            return True
            
        except Exception as e:
            self._logger.error(f"删除经验失败: {e}")
            return False
    
    def get(self, exp_id: str) -> Experience | None:
        """获取经验"""
        return self._experiences.get(exp_id)
    
    def list_all(self, enabled_only: bool = True) -> list[Experience]:
        """
        列出所有经验
        
        Args:
            enabled_only: 是否只列出启用的经验
            
        Returns:
            经验列表
        """
        experiences = list(self._experiences.values())
        
        if enabled_only:
            experiences = [e for e in experiences if e.enabled]
        
        return sorted(experiences, key=lambda e: e.created_at, reverse=True)
    
    def get_prompt_injection(self) -> str:
        """
        获取要注入到系统提示的内容
        
        Returns:
            格式化的提示内容
        """
        if not self._enabled:
            return ""
        
        experiences = self.list_all(enabled_only=True)
        
        if not experiences:
            return ""
        
        lines = [
            "## AI 经验知识库 (OpenSpace)",
            "",
            "以下是 AI 在开发过程中积累的经验和注意事项，请参考这些经验避免重复踩坑：",
            "",
        ]
        
        for exp in experiences:
            lines.append(exp.to_prompt_context())
            lines.append("---")
            lines.append("")
        
        return "\n".join(lines)
    
    def get_statistics(self) -> dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        all_exp = self.list_all(enabled_only=False)
        enabled_exp = [e for e in all_exp if e.enabled]
        
        categories = {}
        for exp in all_exp:
            cat = exp.category.value
            categories[cat] = categories.get(cat, 0) + 1
        
        return {
            "total": len(all_exp),
            "enabled": len(enabled_exp),
            "disabled": len(all_exp) - len(enabled_exp),
            "categories": categories,
            "is_enabled": self._enabled,
            "ai_auto_summarize": self._ai_auto_summarize,
        }
    
    def create_experience(
        self,
        title: str,
        content: str,
        category: ExperienceCategory = ExperienceCategory.GENERAL,
        tags: list[str] | None = None,
        project: str = "",
    ) -> Experience:
        """
        创建新经验
        
        Args:
            title: 标题
            content: 内容（不超过 500 字）
            category: 分类
            tags: 标签
            project: 项目名称
            
        Returns:
            创建的经验对象
        """
        import uuid
        
        exp_id = f"exp_{uuid.uuid4().hex[:8]}"
        
        if len(content) > MAX_EXPERIENCE_CHARS:
            content = content[:MAX_EXPERIENCE_CHARS]
        
        exp = Experience(
            id=exp_id,
            title=title,
            content=content,
            category=category,
            tags=tags or [],
            project=project,
        )
        
        return exp


open_space_manager: OpenSpaceManager | None = None


def get_open_space_manager(space_dir: Path | None = None, working_dir: Path | None = None) -> OpenSpaceManager:
    """
    获取全局 OpenSpace 管理器实例
    
    优先级：
    1. 显式指定的 space_dir
    2. 工作目录下的 .foxcode/space/
    3. 用户主目录下的 ~/.foxcode/space/
    
    Args:
        space_dir: 经验目录（显式指定）
        working_dir: 工作目录（用于查找项目级经验目录）
        
    Returns:
        OpenSpaceManager 实例
    """
    global open_space_manager
    
    if open_space_manager is None:
        # 确定经验目录
        if space_dir is None:
            # 优先使用项目目录下的 .foxcode/space/
            if working_dir is not None:
                project_space_dir = working_dir / ".foxcode" / "space"
                if project_space_dir.exists():
                    space_dir = project_space_dir
                    logger.info(f"使用项目经验目录: {space_dir}")
            
            # 如果项目目录不存在，使用用户主目录
            if space_dir is None:
                space_dir = Path.home() / ".foxcode" / "space"
        
        open_space_manager = OpenSpaceManager(space_dir)
        open_space_manager.load_all()
    
    return open_space_manager


def reset_open_space_manager() -> None:
    """
    重置全局 OpenSpace 管理器
    
    用于切换工作目录后重新加载经验
    """
    global open_space_manager
    open_space_manager = None
