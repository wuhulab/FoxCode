"""
FoxCode OpenSpace 模块

实现 AI 经验知识存储系统，用于记录 AI 踩过的坑和注意事项。
参考 HKUDS OpenSpace 项目的设计理念。

功能特点：
1. 存储经验教训（每个文件不超过 500 字）
2. 每次启动 foxcode 时自动加载到上下文
3. 支持启用/禁用控制
4. 会话跟踪：记录 AI 在会话中踩过的坑
5. 自动总结：在会话结束时自动生成经验记录
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MAX_EXPERIENCE_CHARS = 500
MAX_SESSION_TRACKER_ITEMS = 50


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
    SHORTCUT = "shortcut"


@dataclass
class TrackedEvent:
    """
    跟踪事件
    
    记录 AI 在会话中遇到的错误、坑或可优化的路径
    """
    event_type: str  # error, pitfall, shortcut, retry
    tool_name: str
    description: str
    context: str = ""  # 相关上下文
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    resolved: bool = False  # 是否已解决
    resolution: str = ""  # 解决方案

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "tool_name": self.tool_name,
            "description": self.description,
            "context": self.context,
            "timestamp": self.timestamp,
            "resolved": self.resolved,
            "resolution": self.resolution,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrackedEvent:
        return cls(
            event_type=data.get("event_type", ""),
            tool_name=data.get("tool_name", ""),
            description=data.get("description", ""),
            context=data.get("context", ""),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            resolved=data.get("resolved", False),
            resolution=data.get("resolution", ""),
        )


class SessionTracker:
    """
    会话跟踪器
    
    跟踪 AI 在当前会话中的行为，记录：
    - 工具调用失败
    - 重复尝试
    - 发现的坑
    - 可优化的路径（shortcut）
    """

    def __init__(self):
        self._events: list[TrackedEvent] = []
        self._tool_call_counts: Counter = Counter()
        self._error_counts: Counter = Counter()
        self._start_time = datetime.now()
        self._logger = logging.getLogger("foxcode.session_tracker")

    def track_tool_call(self, tool_name: str, success: bool, error: str = "") -> None:
        """
        跟踪工具调用
        
        Args:
            tool_name: 工具名称
            success: 是否成功
            error: 错误信息（如果失败）
        """
        self._tool_call_counts[tool_name] += 1

        if not success and error:
            self._error_counts[tool_name] += 1
            event = TrackedEvent(
                event_type="error",
                tool_name=tool_name,
                description=error[:200],  # 限制长度
            )
            self._events.append(event)
            self._logger.debug(f"跟踪工具错误: {tool_name} - {error[:50]}")

    def track_retry(self, tool_name: str, attempt: int, reason: str = "") -> None:
        """
        跟踪重试行为
        
        Args:
            tool_name: 工具名称
            attempt: 尝试次数
            reason: 重试原因
        """
        if attempt > 1:
            event = TrackedEvent(
                event_type="retry",
                tool_name=tool_name,
                description=f"重试 {attempt} 次: {reason[:100]}",
            )
            self._events.append(event)
            self._logger.debug(f"跟踪重试: {tool_name} - 第 {attempt} 次")

    def track_pitfall(
        self,
        description: str,
        context: str = "",
        resolution: str = "",
    ) -> None:
        """
        跟踪踩坑事件
        
        Args:
            description: 坑的描述
            context: 相关上下文
            resolution: 解决方案
        """
        event = TrackedEvent(
            event_type="pitfall",
            tool_name="",
            description=description[:200],
            context=context[:300],
            resolved=bool(resolution),
            resolution=resolution[:200],
        )
        self._events.append(event)
        self._logger.info(f"跟踪踩坑: {description[:50]}")

    def track_shortcut(
        self,
        description: str,
        original_approach: str = "",
        better_approach: str = "",
    ) -> None:
        """
        跟踪可优化的路径（远路）
        
        Args:
            description: 描述
            original_approach: 原来的方法
            better_approach: 更好的方法
        """
        event = TrackedEvent(
            event_type="shortcut",
            tool_name="",
            description=description[:200],
            context=f"原方法: {original_approach[:100]}\n更好: {better_approach[:100]}",
        )
        self._events.append(event)
        self._logger.info(f"跟踪远路: {description[:50]}")

    def get_summary(self) -> dict[str, Any]:
        """
        获取会话跟踪摘要
        
        Returns:
            摘要信息字典
        """
        duration = (datetime.now() - self._start_time).total_seconds()

        errors = [e for e in self._events if e.event_type == "error"]
        pitfalls = [e for e in self._events if e.event_type == "pitfall"]
        shortcuts = [e for e in self._events if e.event_type == "shortcut"]
        retries = [e for e in self._events if e.event_type == "retry"]

        return {
            "duration_seconds": duration,
            "total_events": len(self._events),
            "tool_call_counts": dict(self._tool_call_counts),
            "error_counts": dict(self._error_counts),
            "errors": [e.to_dict() for e in errors],
            "pitfalls": [e.to_dict() for e in pitfalls],
            "shortcuts": [e.to_dict() for e in shortcuts],
            "retries": [e.to_dict() for e in retries],
            "most_used_tools": self._tool_call_counts.most_common(5),
            "most_error_tools": self._error_counts.most_common(5),
        }

    def get_experience_candidates(self) -> list[dict[str, Any]]:
        """
        获取可能值得记录为经验的事件
        
        Returns:
            候选经验列表
        """
        candidates = []

        # 分析错误模式
        for tool_name, count in self._error_counts.items():
            if count >= 2:
                errors = [e for e in self._events
                         if e.event_type == "error" and e.tool_name == tool_name]
                if errors:
                    error_desc = errors[0].description
                    candidates.append({
                        "type": "pitfall",
                        "title": f"{tool_name} 工具常见错误",
                        "content": f"使用 {tool_name} 时遇到错误: {error_desc[:150]}",
                        "category": ExperienceCategory.PITFALL,
                        "tags": [tool_name, "error"],
                    })

        # 分析踩坑事件
        for event in self._events:
            if event.event_type == "pitfall" and event.resolved:
                candidates.append({
                    "type": "pitfall",
                    "title": f"踩坑: {event.description[:30]}",
                    "content": f"{event.description}\n解决: {event.resolution}",
                    "category": ExperienceCategory.PITFALL,
                    "tags": ["pitfall", "resolved"],
                })

        # 分析远路
        for event in self._events:
            if event.event_type == "shortcut":
                candidates.append({
                    "type": "shortcut",
                    "title": f"优化: {event.description[:30]}",
                    "content": event.context[:400],
                    "category": ExperienceCategory.SHORTCUT,
                    "tags": ["optimization", "shortcut"],
                })

        return candidates

    def clear(self) -> None:
        """清空跟踪记录"""
        self._events.clear()
        self._tool_call_counts.clear()
        self._error_counts.clear()
        self._start_time = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "events": [e.to_dict() for e in self._events],
            "tool_call_counts": dict(self._tool_call_counts),
            "error_counts": dict(self._error_counts),
            "start_time": self._start_time.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionTracker:
        """从字典反序列化"""
        tracker = cls()
        tracker._events = [TrackedEvent.from_dict(e) for e in data.get("events", [])]
        tracker._tool_call_counts = Counter(data.get("tool_call_counts", {}))
        tracker._error_counts = Counter(data.get("error_counts", {}))
        if "start_time" in data:
            try:
                tracker._start_time = datetime.fromisoformat(data["start_time"])
            except Exception:
                pass
        return tracker


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
    def from_dict(cls, data: dict[str, Any]) -> Experience:
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
    支持会话跟踪和自动总结
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

        # 会话跟踪器
        self._session_tracker: SessionTracker | None = None

        self._ensure_directory()
        self._load_state()

    @property
    def session_tracker(self) -> SessionTracker:
        """获取当前会话跟踪器（延迟初始化）"""
        if self._session_tracker is None:
            self._session_tracker = SessionTracker()
        return self._session_tracker

    def reset_session_tracker(self) -> None:
        """重置会话跟踪器"""
        if self._session_tracker:
            self._session_tracker.clear()
        self._session_tracker = SessionTracker()

    def _ensure_directory(self) -> None:
        """确保目录存在"""
        self.space_dir.mkdir(parents=True, exist_ok=True)
        self._logger.debug(f"OpenSpace 目录: {self.space_dir}")

    def _load_state(self) -> None:
        """加载状态（启用/禁用/AI自动总结）"""
        if self._state_file.exists():
            try:
                with open(self._state_file, encoding="utf-8") as f:
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
                with open(exp_file, encoding="utf-8") as f:
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

    def _compute_content_hash(self, content: str) -> str:
        """
        计算内容哈希值（用于去重）
        
        Args:
            content: 经验内容
            
        Returns:
            内容哈希值
        """
        # 标准化内容：去除空白、转小写
        normalized = "".join(content.lower().split())
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def find_similar_experience(
        self,
        content: str,
        threshold: float = 0.7,
    ) -> Experience | None:
        """
        查找相似的经验
        
        Args:
            content: 要比较的内容
            threshold: 相似度阈值 (0-1)
            
        Returns:
            相似的经验，如果没有则返回 None
        """
        if not self._experiences:
            return None

        # 简单的关键词匹配
        content_words = set(content.lower().split())

        best_match: Experience | None = None
        best_score = 0.0

        for exp in self._experiences.values():
            exp_words = set(exp.content.lower().split())

            # 计算 Jaccard 相似度
            if content_words and exp_words:
                intersection = len(content_words & exp_words)
                union = len(content_words | exp_words)
                score = intersection / union if union > 0 else 0

                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = exp

        return best_match

    def is_duplicate(self, content: str) -> bool:
        """
        检查是否为重复经验
        
        Args:
            content: 经验内容
            
        Returns:
            是否重复
        """
        # 检查内容哈希
        content_hash = self._compute_content_hash(content)

        for exp in self._experiences.values():
            exp_hash = self._compute_content_hash(exp.content)
            if content_hash == exp_hash:
                return True

        # 检查相似度
        similar = self.find_similar_experience(content, threshold=0.8)
        return similar is not None

    def merge_experiences(
        self,
        exp1: Experience,
        exp2: Experience,
    ) -> Experience:
        """
        合并两个经验
        
        Args:
            exp1: 第一个经验
            exp2: 第二个经验
            
        Returns:
            合并后的经验
        """
        # 合并内容
        merged_content = f"{exp1.content}"
        if exp2.content and exp2.content not in exp1.content:
            merged_content += f"\n\n补充: {exp2.content}"

        # 截断到最大长度
        if len(merged_content) > MAX_EXPERIENCE_CHARS:
            merged_content = merged_content[:MAX_EXPERIENCE_CHARS]

        # 合并标签
        merged_tags = list(set(exp1.tags + exp2.tags))

        # 创建合并后的经验
        merged = self.create_experience(
            title=exp1.title,
            content=merged_content,
            category=exp1.category,
            tags=merged_tags,
            project=exp1.project or exp2.project,
        )

        return merged

    def generate_review_prompt(self) -> str:
        """
        生成 AI 审查提示
        
        在会话结束时，提示 AI 审查自己踩过的坑和可以跳过的远路
        
        Returns:
            审查提示文本
        """
        if not self._session_tracker:
            return ""

        summary = self._session_tracker.get_summary()
        candidates = self._session_tracker.get_experience_candidates()

        if not candidates and summary["total_events"] == 0:
            return ""

        lines = [
            "## 会话审查请求",
            "",
            "在结束本次会话前，请审查以下内容，并决定是否需要记录新的经验：",
            "",
        ]

        # 添加错误统计
        if summary["error_counts"]:
            lines.append("### 本次会话遇到的错误")
            for tool, count in summary["error_counts"].items():
                lines.append(f"- {tool}: {count} 次错误")
            lines.append("")

        # 添加候选经验
        if candidates:
            lines.append("### 建议记录的经验")
            for i, candidate in enumerate(candidates[:5], 1):
                lines.append(f"{i}. **{candidate['title']}**")
                lines.append(f"   类型: {candidate['type']}")
                lines.append(f"   内容: {candidate['content'][:100]}...")
                lines.append("")

        # 添加审查请求
        lines.extend([
            "### 请执行以下操作：",
            "",
            "1. 审查上述错误和候选经验",
            "2. 如果有值得记录的新经验，请使用以下格式回复：",
            "",
            "```",
            "OPENSPACE_ADD:",
            "标题: <经验标题>",
            "内容: <经验内容，不超过500字>",
            "分类: pitfall/shortcut/general",
            "标签: <逗号分隔的标签>",
            "```",
            "",
            "3. 如果有需要修改或删除的现有经验，请说明",
            "4. 如果没有需要记录的内容，可以忽略此提示",
            "",
            "**注意**: 只记录真正有价值的经验，避免记录临时性或特定场景的问题。",
        ])

        return "\n".join(lines)

    def parse_ai_response(self, response: str) -> list[dict[str, str]]:
        """
        解析 AI 响应中的经验添加请求
        
        Args:
            response: AI 响应文本
            
        Returns:
            解析出的经验列表
        """
        experiences = []

        # 查找 OPENSPACE_ADD 块
        import re

        pattern = r'OPENSPACE_ADD:\s*\n标题:\s*(.+?)\n内容:\s*(.+?)\n分类:\s*(\w+)\n标签:\s*(.+?)(?=\n```|\nOPENSPACE_ADD|$)'
        matches = re.findall(pattern, response, re.DOTALL)

        for match in matches:
            title = match[0].strip()
            content = match[1].strip()
            category_str = match[2].strip().lower()
            tags_str = match[3].strip()

            # 解析分类
            try:
                category = ExperienceCategory(category_str)
            except ValueError:
                category = ExperienceCategory.GENERAL

            # 解析标签
            tags = [t.strip() for t in tags_str.split(",") if t.strip()]

            experiences.append({
                "title": title,
                "content": content,
                "category": category,
                "tags": tags,
            })

        return experiences

    def save_from_ai_response(self, response: str) -> int:
        """
        从 AI 响应中保存经验
        
        Args:
            response: AI 响应文本
            
        Returns:
            成功保存的经验数量
        """
        experiences = self.parse_ai_response(response)
        saved = 0

        for exp_data in experiences:
            # 检查是否重复
            if self.is_duplicate(exp_data["content"]):
                self._logger.info(f"跳过重复经验: {exp_data['title']}")
                continue

            # 创建并保存经验
            exp = self.create_experience(
                title=exp_data["title"],
                content=exp_data["content"],
                category=exp_data["category"],
                tags=exp_data["tags"],
            )

            if self.save(exp):
                saved += 1
                self._logger.info(f"从 AI 响应保存经验: {exp.id} - {exp.title}")

        return saved

    def auto_save_session_experiences(self) -> int:
        """
        自动保存会话中的经验
        
        从会话跟踪器中提取候选经验并保存
        
        Returns:
            成功保存的经验数量
        """
        if not self._session_tracker:
            return 0

        candidates = self._session_tracker.get_experience_candidates()
        saved = 0

        for candidate in candidates:
            # 检查是否重复
            if self.is_duplicate(candidate["content"]):
                self._logger.debug(f"跳过重复经验: {candidate['title']}")
                continue

            # 创建并保存经验
            exp = self.create_experience(
                title=candidate["title"],
                content=candidate["content"],
                category=candidate["category"],
                tags=candidate["tags"],
            )

            if self.save(exp):
                saved += 1
                self._logger.info(f"自动保存经验: {exp.id} - {exp.title}")

        return saved


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
