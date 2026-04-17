"""
FoxCode 任务管理模块

管理任务列表和规划系统
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskPriority(str, Enum):
    """任务优先级"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Task:
    """
    任务类
    
    表示一个可执行的任务
    """
    id: str
    content: str
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: str | None = None
    dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def start(self) -> None:
        """开始任务"""
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = datetime.now()

    def complete(self, result: str | None = None) -> None:
        """完成任务"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
        self.result = result

    def fail(self, error: str) -> None:
        """任务失败"""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now()
        self.result = error

    def skip(self, reason: str = "") -> None:
        """跳过任务"""
        self.status = TaskStatus.SKIPPED
        self.completed_at = datetime.now()
        self.result = reason

    def is_ready(self, completed_tasks: set[str]) -> bool:
        """检查任务是否可以开始"""
        if self.status != TaskStatus.PENDING:
            return False
        return all(dep in completed_tasks for dep in self.dependencies)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "content": self.content,
            "status": self.status.value,
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "dependencies": self.dependencies,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        """从字典创建"""
        return cls(
            id=data["id"],
            content=data["content"],
            status=TaskStatus(data["status"]),
            priority=TaskPriority(data.get("priority", "medium")),
            created_at=datetime.fromisoformat(data["created_at"]),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            result=data.get("result"),
            dependencies=data.get("dependencies", []),
            metadata=data.get("metadata", {}),
        )


class TaskList:
    """
    任务列表
    
    管理多个任务的状态和执行顺序
    """

    def __init__(self):
        self.tasks: dict[str, Task] = {}
        self._order: list[str] = []

    def add_task(
        self,
        content: str,
        priority: TaskPriority = TaskPriority.MEDIUM,
        dependencies: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        """
        添加任务
        
        Args:
            content: 任务内容
            priority: 优先级
            dependencies: 依赖的任务 ID 列表
            metadata: 元数据
            
        Returns:
            创建的任务
        """
        task_id = f"task_{len(self.tasks) + 1}"

        task = Task(
            id=task_id,
            content=content,
            priority=priority,
            dependencies=dependencies or [],
            metadata=metadata or {},
        )

        self.tasks[task_id] = task
        self._order.append(task_id)

        logger.debug(f"添加任务: {task_id} - {content}")
        return task

    def get_task(self, task_id: str) -> Task | None:
        """获取任务"""
        return self.tasks.get(task_id)

    def get_next_task(self) -> Task | None:
        """
        获取下一个可执行的任务
        
        Returns:
            下一个任务，如果没有则返回 None
        """
        completed = {
            tid for tid, task in self.tasks.items()
            if task.status == TaskStatus.COMPLETED
        }

        for task_id in self._order:
            task = self.tasks[task_id]
            if task.is_ready(completed):
                return task

        return None

    def get_all_tasks(self) -> list[Task]:
        """获取所有任务"""
        return [self.tasks[tid] for tid in self._order]

    def get_pending_tasks(self) -> list[Task]:
        """获取待处理任务"""
        return [
            self.tasks[tid] for tid in self._order
            if self.tasks[tid].status == TaskStatus.PENDING
        ]

    def get_in_progress_tasks(self) -> list[Task]:
        """获取进行中的任务"""
        return [
            self.tasks[tid] for tid in self._order
            if self.tasks[tid].status == TaskStatus.IN_PROGRESS
        ]

    def get_completed_tasks(self) -> list[Task]:
        """获取已完成任务"""
        return [
            self.tasks[tid] for tid in self._order
            if self.tasks[tid].status == TaskStatus.COMPLETED
        ]

    def get_failed_tasks(self) -> list[Task]:
        """获取失败任务"""
        return [
            self.tasks[tid] for tid in self._order
            if self.tasks[tid].status == TaskStatus.FAILED
        ]

    def get_progress(self) -> dict[str, int]:
        """获取进度统计"""
        status_counts = {status.value: 0 for status in TaskStatus}
        for task in self.tasks.values():
            status_counts[task.status.value] += 1

        return status_counts

    def is_complete(self) -> bool:
        """检查所有任务是否完成"""
        return all(
            task.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED)
            for task in self.tasks.values()
        )

    def clear(self) -> None:
        """清空任务列表"""
        self.tasks.clear()
        self._order.clear()

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "tasks": [self.tasks[tid].to_dict() for tid in self._order],
            "progress": self.get_progress(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskList:
        """从字典创建"""
        task_list = cls()
        for task_data in data.get("tasks", []):
            task = Task.from_dict(task_data)
            task_list.tasks[task.id] = task
            task_list._order.append(task.id)
        return task_list

    def to_json(self) -> str:
        """转换为 JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def format_summary(self) -> str:
        """格式化任务摘要"""
        lines = ["# 任务列表", ""]

        progress = self.get_progress()
        total = sum(progress.values())
        completed = progress.get("completed", 0)

        lines.append(f"进度: {completed}/{total} 完成")
        lines.append("")

        # 按状态分组显示
        status_icons = {
            "pending": "⏳",
            "in_progress": "🔄",
            "completed": "✅",
            "failed": "❌",
            "skipped": "⏭️",
        }

        for task in self.get_all_tasks():
            icon = status_icons.get(task.status.value, "❓")
            priority_mark = "!" if task.priority == TaskPriority.HIGH else ""
            lines.append(f"{icon} {priority_mark}{task.content}")

        return "\n".join(lines)


class PlanManager:
    """
    规划管理器
    
    管理任务规划和执行流程
    """

    def __init__(self):
        self.task_list = TaskList()
        self.current_plan: str | None = None
        self.plan_created_at: datetime | None = None

    def create_plan(self, description: str, tasks: list[dict[str, Any]]) -> None:
        """
        创建执行计划
        
        Args:
            description: 计划描述
            tasks: 任务列表
        """
        self.current_plan = description
        self.plan_created_at = datetime.now()
        self.task_list.clear()

        for i, task_data in enumerate(tasks):
            self.task_list.add_task(
                content=task_data.get("content", f"任务 {i + 1}"),
                priority=TaskPriority(task_data.get("priority", "medium")),
                dependencies=task_data.get("dependencies"),
                metadata=task_data.get("metadata"),
            )

        logger.info(f"创建计划: {description}, {len(tasks)} 个任务")

    def get_next_task(self) -> Task | None:
        """获取下一个任务"""
        return self.task_list.get_next_task()

    def start_task(self, task_id: str) -> bool:
        """
        开始任务
        
        Args:
            task_id: 任务 ID
            
        Returns:
            是否成功开始
        """
        task = self.task_list.get_task(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.start()
            logger.info(f"开始任务: {task_id}")
            return True
        return False

    def complete_task(self, task_id: str, result: str | None = None) -> bool:
        """
        完成任务
        
        Args:
            task_id: 任务 ID
            result: 执行结果
            
        Returns:
            是否成功完成
        """
        task = self.task_list.get_task(task_id)
        if task and task.status == TaskStatus.IN_PROGRESS:
            task.complete(result)
            logger.info(f"完成任务: {task_id}")
            return True
        return False

    def fail_task(self, task_id: str, error: str) -> bool:
        """
        标记任务失败
        
        Args:
            task_id: 任务 ID
            error: 错误信息
            
        Returns:
            是否成功标记
        """
        task = self.task_list.get_task(task_id)
        if task:
            task.fail(error)
            logger.error(f"任务失败: {task_id} - {error}")
            return True
        return False

    def get_status(self) -> dict[str, Any]:
        """获取计划状态"""
        return {
            "plan": self.current_plan,
            "created_at": self.plan_created_at.isoformat() if self.plan_created_at else None,
            "progress": self.task_list.get_progress(),
            "is_complete": self.task_list.is_complete(),
            "current_task": (
                self.task_list.get_next_task().id
                if self.task_list.get_next_task() else None
            ),
        }

    def format_plan(self) -> str:
        """格式化计划显示"""
        if not self.current_plan:
            return "暂无计划"

        lines = [
            "# 执行计划",
            "",
            f"**目标**: {self.current_plan}",
            "",
            self.task_list.format_summary(),
        ]

        return "\n".join(lines)
