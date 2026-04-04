"""
FoxCode 会话切换产物模块

实现 HandoffArtifact 数据结构，用于在上下文重置或会话切换时传递状态。
支持完整的序列化和反序列化，以及生成可注入系统提示词的上下文。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from foxcode.core.config import AgentRole

logger = logging.getLogger(__name__)


@dataclass
class TaskItem:
    """
    任务项数据结构
    
    用于表示单个任务的信息，包括任务的基本属性、状态和依赖关系。
    
    Attributes:
        id: 任务唯一标识符
        title: 任务标题
        description: 任务详细描述
        status: 任务状态 (pending, in_progress, completed, blocked)
        priority: 优先级 (high, medium, low)
        dependencies: 依赖的任务 ID 列表
        verification_criteria: 验证标准
        artifacts: 产物文件列表
        notes: 备注信息
    """
    id: str
    title: str
    description: str = ""
    status: str = "pending"
    priority: str = "medium"
    dependencies: list[str] = field(default_factory=list)
    verification_criteria: str = ""
    artifacts: list[str] = field(default_factory=list)
    notes: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """
        将任务项转换为字典格式
        
        Returns:
            包含所有任务属性的字典
        """
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "dependencies": self.dependencies,
            "verification_criteria": self.verification_criteria,
            "artifacts": self.artifacts,
            "notes": self.notes,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskItem":
        """
        从字典创建任务项实例
        
        Args:
            data: 包含任务属性的字典
            
        Returns:
            创建的 TaskItem 实例
            
        Raises:
            KeyError: 当缺少必需字段时
        """
        try:
            return cls(
                id=data["id"],
                title=data["title"],
                description=data.get("description", ""),
                status=data.get("status", "pending"),
                priority=data.get("priority", "medium"),
                dependencies=data.get("dependencies", []),
                verification_criteria=data.get("verification_criteria", ""),
                artifacts=data.get("artifacts", []),
                notes=data.get("notes", ""),
            )
        except KeyError as e:
            logger.error(f"创建 TaskItem 时缺少必需字段: {e}")
            raise


@dataclass
class HandoffArtifact:
    """
    会话切换产物
    
    在上下文重置或会话切换时传递完整状态，确保代理能够无缝继续工作。
    该数据结构记录了会话的完整状态信息，包括已完成的工作、待处理的任务、
    关键决策等，支持序列化和反序列化操作。
    
    Attributes:
        session_id: 源会话 ID
        timestamp: 创建时间戳
        agent_role: 当前代理角色
        completed_work: 已完成的工作描述列表
        incomplete_work: 未完成的工作描述列表
        current_task: 当前正在执行的任务
        pending_tasks: 待处理任务列表
        completed_tasks: 已完成任务列表
        key_decisions: 关键决策列表
        file_changes: 文件变更列表
        next_steps: 下一步计划列表
        issues: 遇到的问题列表
        blockers: 阻塞项列表
        context_summary: 上下文摘要
        working_directory: 工作目录
        branch_name: 当前分支名称
        metadata: 额外元数据
    """
    session_id: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    agent_role: AgentRole = AgentRole.GENERATOR
    
    completed_work: list[str] = field(default_factory=list)
    incomplete_work: list[str] = field(default_factory=list)
    
    current_task: Optional[TaskItem] = None
    pending_tasks: list[TaskItem] = field(default_factory=list)
    completed_tasks: list[TaskItem] = field(default_factory=list)
    
    key_decisions: list[str] = field(default_factory=list)
    file_changes: list[str] = field(default_factory=list)
    
    next_steps: list[str] = field(default_factory=list)
    
    issues: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    
    context_summary: str = ""
    working_directory: str = ""
    branch_name: str = ""
    
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """
        将 HandoffArtifact 转换为字典格式
        
        Returns:
            包含所有属性的字典，可用于 JSON 序列化
        """
        return {
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "agent_role": self.agent_role.value,
            "completed_work": self.completed_work,
            "incomplete_work": self.incomplete_work,
            "current_task": self.current_task.to_dict() if self.current_task else None,
            "pending_tasks": [t.to_dict() for t in self.pending_tasks],
            "completed_tasks": [t.to_dict() for t in self.completed_tasks],
            "key_decisions": self.key_decisions,
            "file_changes": self.file_changes,
            "next_steps": self.next_steps,
            "issues": self.issues,
            "blockers": self.blockers,
            "context_summary": self.context_summary,
            "working_directory": self.working_directory,
            "branch_name": self.branch_name,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HandoffArtifact":
        """
        从字典创建 HandoffArtifact 实例
        
        Args:
            data: 包含 HandoffArtifact 属性的字典
            
        Returns:
            创建的 HandoffArtifact 实例
            
        Raises:
            KeyError: 当缺少必需字段时
            ValueError: 当 agent_role 值无效时
        """
        try:
            current_task = None
            if data.get("current_task"):
                current_task = TaskItem.from_dict(data["current_task"])
            
            return cls(
                session_id=data["session_id"],
                timestamp=data.get("timestamp", datetime.now().isoformat()),
                agent_role=AgentRole(data.get("agent_role", "generator")),
                completed_work=data.get("completed_work", []),
                incomplete_work=data.get("incomplete_work", []),
                current_task=current_task,
                pending_tasks=[TaskItem.from_dict(t) for t in data.get("pending_tasks", [])],
                completed_tasks=[TaskItem.from_dict(t) for t in data.get("completed_tasks", [])],
                key_decisions=data.get("key_decisions", []),
                file_changes=data.get("file_changes", []),
                next_steps=data.get("next_steps", []),
                issues=data.get("issues", []),
                blockers=data.get("blockers", []),
                context_summary=data.get("context_summary", ""),
                working_directory=data.get("working_directory", ""),
                branch_name=data.get("branch_name", ""),
                metadata=data.get("metadata", {}),
            )
        except KeyError as e:
            logger.error(f"创建 HandoffArtifact 时缺少必需字段: {e}")
            raise
        except ValueError as e:
            logger.error(f"无效的 agent_role 值: {e}")
            raise
    
    def to_prompt_context(self) -> str:
        """
        生成可注入系统提示词的上下文
        
        将 HandoffArtifact 的关键信息格式化为可读的 Markdown 文本，
        用于在会话恢复时注入到系统提示词中。
        
        Returns:
            格式化的上下文文本，包含会话恢复所需的关键信息
        """
        lines = [
            "## 会话恢复上下文",
            "",
            f"**源会话**: {self.session_id}",
            f"**切换时间**: {self.timestamp}",
            f"**代理角色**: {self.agent_role.value}",
            "",
        ]
        
        if self.current_task:
            lines.append("### 当前任务")
            lines.append(f"- **ID**: {self.current_task.id}")
            lines.append(f"- **标题**: {self.current_task.title}")
            lines.append(f"- **状态**: {self.current_task.status}")
            if self.current_task.description:
                lines.append(f"- **描述**: {self.current_task.description}")
            lines.append("")
        
        if self.completed_work:
            lines.append("### 已完成工作")
            for work in self.completed_work[:5]:
                lines.append(f"- {work}")
            if len(self.completed_work) > 5:
                lines.append(f"- ... 共 {len(self.completed_work)} 项")
            lines.append("")
        
        if self.pending_tasks:
            lines.append("### 待处理任务")
            status_icons = {"pending": "⏳", "in_progress": "🔄", "completed": "✅", "blocked": "🚫"}
            for task in self.pending_tasks[:5]:
                status_icon = status_icons.get(task.status, "❓")
                lines.append(f"- {status_icon} [{task.id}] {task.title}")
            if len(self.pending_tasks) > 5:
                lines.append(f"- ... 共 {len(self.pending_tasks)} 项")
            lines.append("")
        
        if self.next_steps:
            lines.append("### 下一步计划")
            for i, step in enumerate(self.next_steps[:5], 1):
                lines.append(f"{i}. {step}")
            lines.append("")
        
        if self.key_decisions:
            lines.append("### 关键决策")
            for decision in self.key_decisions[:3]:
                lines.append(f"- {decision}")
            lines.append("")
        
        if self.issues or self.blockers:
            lines.append("### 问题追踪")
            for issue in self.issues[:3]:
                lines.append(f"- ⚠️ {issue}")
            for blocker in self.blockers[:3]:
                lines.append(f"- 🚫 {blocker}")
            lines.append("")
        
        if self.file_changes:
            lines.append("### 文件变更")
            for change in self.file_changes[:5]:
                lines.append(f"- {change}")
            lines.append("")
        
        if self.context_summary:
            lines.append("### 上下文摘要")
            truncated_summary = self.context_summary[:500]
            lines.append(truncated_summary)
            if len(self.context_summary) > 500:
                lines.append("... (已截断)")
            lines.append("")
        
        return "\n".join(lines)
    
    def to_json(self) -> str:
        """
        将 HandoffArtifact 转换为 JSON 字符串
        
        Returns:
            格式化的 JSON 字符串
        """
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "HandoffArtifact":
        """
        从 JSON 字符串创建 HandoffArtifact 实例
        
        Args:
            json_str: JSON 格式的字符串
            
        Returns:
            创建的 HandoffArtifact 实例
            
        Raises:
            json.JSONDecodeError: 当 JSON 格式无效时
            KeyError: 当缺少必需字段时
        """
        try:
            data = json.loads(json_str)
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            raise
    
    def save(self, file_path: Path | str) -> None:
        """
        将 HandoffArtifact 保存到文件
        
        Args:
            file_path: 目标文件路径
            
        Raises:
            OSError: 当文件写入失败时
        """
        file_path = Path(file_path)
        
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
            
            logger.info(f"HandoffArtifact 已保存: {file_path}")
        except OSError as e:
            logger.error(f"保存 HandoffArtifact 失败: {e}")
            raise
    
    @classmethod
    def load(cls, file_path: Path | str) -> "HandoffArtifact":
        """
        从文件加载 HandoffArtifact
        
        Args:
            file_path: 源文件路径
            
        Returns:
            加载的 HandoffArtifact 实例
            
        Raises:
            FileNotFoundError: 当文件不存在时
            json.JSONDecodeError: 当文件内容 JSON 格式无效时
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            error_msg = f"HandoffArtifact 文件不存在: {file_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            logger.info(f"HandoffArtifact 已加载: {file_path}")
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {file_path}, 错误: {e}")
            raise
        except OSError as e:
            logger.error(f"读取文件失败: {file_path}, 错误: {e}")
            raise
    
    def get_progress_summary(self) -> str:
        """
        获取进度摘要
        
        生成简短的进度描述，包括任务完成情况和当前状态。
        
        Returns:
            简短的进度摘要文本
        """
        completed = len(self.completed_tasks)
        pending = len(self.pending_tasks)
        total = completed + pending
        
        if total == 0:
            return "无任务记录"
        
        progress = (completed / total) * 100 if total > 0 else 0
        
        summary = f"进度: {completed}/{total} ({progress:.0f}%)"
        
        if self.current_task:
            summary += f" | 当前: {self.current_task.title}"
        
        if self.blockers:
            summary += f" | 阻塞: {len(self.blockers)} 项"
        
        return summary


def create_handoff_from_session(
    session_id: str,
    agent_role: AgentRole,
    completed_work: list[str] | None = None,
    incomplete_work: list[str] | None = None,
    current_task: TaskItem | None = None,
    pending_tasks: list[TaskItem] | None = None,
    completed_tasks: list[TaskItem] | None = None,
    key_decisions: list[str] | None = None,
    file_changes: list[str] | None = None,
    next_steps: list[str] | None = None,
    issues: list[str] | None = None,
    blockers: list[str] | None = None,
    context_summary: str = "",
    working_directory: str = "",
    branch_name: str = "",
    metadata: dict[str, Any] | None = None,
) -> HandoffArtifact:
    """
    从会话创建 HandoffArtifact 的便捷函数
    
    提供一种简洁的方式来创建 HandoffArtifact 实例，
    所有可选参数都有合理的默认值。
    
    Args:
        session_id: 会话 ID
        agent_role: 代理角色
        completed_work: 已完成工作列表
        incomplete_work: 未完成工作列表
        current_task: 当前任务
        pending_tasks: 待处理任务列表
        completed_tasks: 已完成任务列表
        key_decisions: 关键决策列表
        file_changes: 文件变更列表
        next_steps: 下一步计划
        issues: 问题列表
        blockers: 阻塞项列表
        context_summary: 上下文摘要
        working_directory: 工作目录
        branch_name: 分支名称
        metadata: 元数据
        
    Returns:
        创建的 HandoffArtifact 实例
    """
    return HandoffArtifact(
        session_id=session_id,
        agent_role=agent_role,
        completed_work=completed_work or [],
        incomplete_work=incomplete_work or [],
        current_task=current_task,
        pending_tasks=pending_tasks or [],
        completed_tasks=completed_tasks or [],
        key_decisions=key_decisions or [],
        file_changes=file_changes or [],
        next_steps=next_steps or [],
        issues=issues or [],
        blockers=blockers or [],
        context_summary=context_summary,
        working_directory=working_directory,
        branch_name=branch_name,
        metadata=metadata or {},
    )
