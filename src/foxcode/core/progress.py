"""
FoxCode 进度追踪模块

提供持久化的进度追踪功能，记录代理的工作历史和当前状态。
支持跨会话的上下文传递，帮助长时间运行的任务保持连续性。
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ProgressStatus(Enum):
    """
    进度状态枚举
    
    定义任务和工作的各种状态
    """
    PENDING = "pending"           # 待处理
    IN_PROGRESS = "in_progress"   # 进行中
    COMPLETED = "completed"       # 已完成
    BLOCKED = "blocked"           # 已阻塞
    CANCELLED = "cancelled"       # 已取消


@dataclass
class ProgressEntry:
    """
    单条进度记录
    
    记录单个任务或工作的进度信息
    """
    content: str                           # 任务内容描述
    status: ProgressStatus = ProgressStatus.PENDING  # 任务状态
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())  # 创建时间
    completed_at: str | None = None        # 完成时间
    priority: str = "medium"               # 优先级: high, medium, low
    notes: str = ""                        # 备注信息
    
    def mark_completed(self) -> None:
        """标记任务为已完成"""
        self.status = ProgressStatus.COMPLETED
        self.completed_at = datetime.now().isoformat()
    
    def mark_in_progress(self) -> None:
        """标记任务为进行中"""
        self.status = ProgressStatus.IN_PROGRESS
    
    def to_markdown(self) -> str:
        """
        转换为 Markdown 格式
        
        Returns:
            Markdown 格式的字符串
        """
        checkbox = "[x]" if self.status == ProgressStatus.COMPLETED else "[ ]"
        return f"- {checkbox} {self.content}"
    
    @classmethod
    def from_markdown(cls, line: str) -> "ProgressEntry | None":
        """
        从 Markdown 行解析进度条目
        
        Args:
            line: Markdown 格式的行
            
        Returns:
            解析后的 ProgressEntry，如果解析失败则返回 None
        """
        # 匹配 "- [x] 内容" 或 "- [ ] 内容"
        match = re.match(r"- \[([ x])\] (.+)", line.strip())
        if not match:
            return None
        
        status = ProgressStatus.COMPLETED if match.group(1) == "x" else ProgressStatus.PENDING
        content = match.group(2)
        
        return cls(content=content, status=status)


@dataclass
class WorkRecord:
    """
    工作记录
    
    记录一个会话中完成的工作
    """
    session_id: str                         # 会话 ID
    date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))  # 日期
    tasks: list[ProgressEntry] = field(default_factory=list)  # 完成的任务列表
    summary: str = ""                       # 工作摘要
    
    def add_task(self, content: str, status: ProgressStatus = ProgressStatus.COMPLETED) -> None:
        """
        添加任务
        
        Args:
            content: 任务内容
            status: 任务状态
        """
        task = ProgressEntry(content=content, status=status)
        self.tasks.append(task)
    
    def to_markdown(self) -> str:
        """
        转换为 Markdown 格式
        
        Returns:
            Markdown 格式的字符串
        """
        lines = [
            f"### {self.date} 会话 {self.session_id}",
        ]
        
        for task in self.tasks:
            lines.append(task.to_markdown())
        
        if self.summary:
            lines.append(f"\n**摘要**: {self.summary}")
        
        lines.append("")  # 添加空行
        return "\n".join(lines)


@dataclass
class ProgressData:
    """
    进度数据结构
    
    包含完整的进度信息
    """
    project_description: str = ""           # 项目概述
    current_task: str = ""                  # 当前任务
    start_time: str = ""                    # 开始时间
    estimated_remaining: str = ""           # 预计剩余时间
    completed_work: list[WorkRecord] = field(default_factory=list)  # 已完成工作
    todos: list[ProgressEntry] = field(default_factory=list)        # 待办事项
    issues: list[str] = field(default_factory=list)                 # 问题记录
    next_steps: list[str] = field(default_factory=list)             # 下一步计划
    
    def to_markdown(self) -> str:
        """
        转换为完整的 Markdown 格式
        
        Returns:
            Markdown 格式的进度文件内容
        """
        lines = [
            "# FoxCode 工作进度",
            "",
            "## 项目概述",
            self.project_description or "暂无项目描述",
            "",
            "## 当前状态",
            f"- 当前任务: {self.current_task or '无'}",
            f"- 开始时间: {self.start_time or '未设置'}",
            f"- 预计剩余: {self.estimated_remaining or '未知'}",
            "",
            "## 已完成工作",
        ]
        
        if self.completed_work:
            for record in self.completed_work:
                lines.append(record.to_markdown())
        else:
            lines.append("暂无已完成的工作")
        
        lines.append("## 待办事项")
        
        if self.todos:
            for todo in self.todos:
                lines.append(todo.to_markdown())
        else:
            lines.append("- 暂无待办事项")
        
        lines.append("")
        lines.append("## 问题记录")
        
        if self.issues:
            for issue in self.issues:
                lines.append(f"- {issue}")
        else:
            lines.append("- 暂无问题记录")
        
        lines.append("")
        lines.append("## 下一步计划")
        
        if self.next_steps:
            for i, step in enumerate(self.next_steps, 1):
                lines.append(f"{i}. {step}")
        else:
            lines.append("1. 暂无下一步计划")
        
        lines.append("")
        return "\n".join(lines)


class ProgressManager:
    """
    进度管理器
    
    负责进度文件的创建、读取、更新和管理。
    支持同步和异步操作。
    """
    
    DEFAULT_PROGRESS_FILE = ".foxcode/progress.md"
    
    def __init__(self, working_dir: Path, progress_file: str | None = None):
        """
        初始化进度管理器
        
        Args:
            working_dir: 工作目录
            progress_file: 进度文件路径（相对于工作目录），默认为 .foxcode/progress.md
        """
        self.working_dir = Path(working_dir)
        self.progress_file = self.working_dir / (progress_file or self.DEFAULT_PROGRESS_FILE)
        self._data: ProgressData | None = None
        
        # 确保目录存在
        self._ensure_directory()
    
    def _ensure_directory(self) -> None:
        """确保进度文件目录存在"""
        try:
            self.progress_file.parent.mkdir(parents=True, exist_ok=True)
            logger.debug(f"进度文件目录已确保存在: {self.progress_file.parent}")
        except Exception as e:
            logger.error(f"创建进度文件目录失败: {e}")
            raise
    
    @property
    def data(self) -> ProgressData:
        """获取进度数据，如果未加载则自动加载"""
        if self._data is None:
            self._data = self.load()
        return self._data
    
    def exists(self) -> bool:
        """
        检查进度文件是否存在
        
        Returns:
            文件是否存在
        """
        return self.progress_file.exists()
    
    def create(
        self,
        project_description: str = "",
        initial_todos: list[str] | None = None,
    ) -> ProgressData:
        """
        创建新的进度文件
        
        Args:
            project_description: 项目描述
            initial_todos: 初始待办事项列表
            
        Returns:
            创建的进度数据
        """
        try:
            self._data = ProgressData(
                project_description=project_description,
                start_time=datetime.now().isoformat(),
            )
            
            # 添加初始待办事项
            if initial_todos:
                for todo in initial_todos:
                    self._data.todos.append(ProgressEntry(content=todo))
            
            self._save()
            logger.info(f"进度文件已创建: {self.progress_file}")
            return self._data
            
        except Exception as e:
            logger.error(f"创建进度文件失败: {e}")
            raise
    
    def load(self) -> ProgressData:
        """
        加载现有进度文件
        
        Returns:
            加载的进度数据
        """
        if not self.exists():
            logger.info("进度文件不存在，创建新的进度数据")
            return ProgressData()
        
        try:
            content = self.progress_file.read_text(encoding="utf-8")
            self._data = self._parse_markdown(content)
            logger.info(f"进度文件已加载: {self.progress_file}")
            return self._data
            
        except Exception as e:
            logger.error(f"加载进度文件失败: {e}")
            raise
    
    def _parse_markdown(self, content: str) -> ProgressData:
        """
        解析 Markdown 格式的进度文件
        
        Args:
            content: Markdown 内容
            
        Returns:
            解析后的进度数据
        """
        data = ProgressData()
        lines = content.split("\n")
        
        current_section = ""
        current_work_record: WorkRecord | None = None
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # 识别章节标题
            if line.startswith("## "):
                current_section = line[3:].strip().lower()
                i += 1
                continue
            
            # 处理各章节内容
            if current_section == "项目概述":
                if line.strip() and not line.startswith("#"):
                    data.project_description += line + "\n"
                    
            elif current_section == "当前状态":
                if line.startswith("- 当前任务:"):
                    data.current_task = line.split(":", 1)[1].strip()
                elif line.startswith("- 开始时间:"):
                    data.start_time = line.split(":", 1)[1].strip()
                elif line.startswith("- 预计剩余:"):
                    data.estimated_remaining = line.split(":", 1)[1].strip()
                    
            elif current_section == "已完成工作":
                # 识别会话记录标题
                if line.startswith("### "):
                    # 保存之前的记录
                    if current_work_record:
                        data.completed_work.append(current_work_record)
                    
                    # 解析会话信息
                    match = re.match(r"### (\d{4}-\d{2}-\d{2}) 会话 (.+)", line)
                    if match:
                        current_work_record = WorkRecord(
                            session_id=match.group(2),
                            date=match.group(1),
                        )
                    else:
                        current_work_record = None
                elif current_work_record:
                    # 解析任务
                    entry = ProgressEntry.from_markdown(line)
                    if entry:
                        current_work_record.tasks.append(entry)
                        
            elif current_section == "待办事项":
                entry = ProgressEntry.from_markdown(line)
                if entry:
                    data.todos.append(entry)
                    
            elif current_section == "问题记录":
                if line.startswith("- ") and len(line) > 2:
                    data.issues.append(line[2:].strip())
                    
            elif current_section == "下一步计划":
                match = re.match(r"\d+\. (.+)", line)
                if match:
                    data.next_steps.append(match.group(1).strip())
            
            i += 1
        
        # 保存最后一个工作记录
        if current_work_record:
            data.completed_work.append(current_work_record)
        
        # 清理项目描述末尾的空白
        data.project_description = data.project_description.strip()
        
        return data
    
    def _save(self) -> None:
        """保存进度数据到文件"""
        try:
            content = self.data.to_markdown()
            self.progress_file.write_text(content, encoding="utf-8")
            logger.debug(f"进度文件已保存: {self.progress_file}")
        except Exception as e:
            logger.error(f"保存进度文件失败: {e}")
            raise
    
    def update_status(
        self,
        current_task: str | None = None,
        estimated_remaining: str | None = None,
    ) -> None:
        """
        更新当前状态
        
        Args:
            current_task: 当前任务描述
            estimated_remaining: 预计剩余时间
        """
        try:
            if current_task is not None:
                self.data.current_task = current_task
            if estimated_remaining is not None:
                self.data.estimated_remaining = estimated_remaining
            
            self._save()
            logger.info(f"进度状态已更新: 当前任务={current_task}")
            
        except Exception as e:
            logger.error(f"更新进度状态失败: {e}")
            raise
    
    def add_work_record(
        self,
        session_id: str,
        tasks: list[str],
        summary: str = "",
    ) -> None:
        """
        添加工作记录
        
        Args:
            session_id: 会话 ID
            tasks: 完成的任务列表
            summary: 工作摘要
        """
        try:
            record = WorkRecord(
                session_id=session_id,
                summary=summary,
            )
            
            for task in tasks:
                record.add_task(task)
            
            self.data.completed_work.append(record)
            self._save()
            logger.info(f"工作记录已添加: 会话 {session_id}, {len(tasks)} 个任务")
            
        except Exception as e:
            logger.error(f"添加工作记录失败: {e}")
            raise
    
    def add_todo(
        self,
        content: str,
        priority: str = "medium",
    ) -> None:
        """
        添加待办事项
        
        Args:
            content: 待办事项内容
            priority: 优先级 (high, medium, low)
        """
        try:
            todo = ProgressEntry(content=content, priority=priority)
            self.data.todos.append(todo)
            self._save()
            logger.info(f"待办事项已添加: {content}")
            
        except Exception as e:
            logger.error(f"添加待办事项失败: {e}")
            raise
    
    def complete_todo(self, content: str) -> bool:
        """
        完成待办事项
        
        Args:
            content: 待办事项内容（支持部分匹配）
            
        Returns:
            是否找到并完成该待办事项
        """
        try:
            for todo in self.data.todos:
                if content in todo.content and todo.status != ProgressStatus.COMPLETED:
                    todo.mark_completed()
                    self._save()
                    logger.info(f"待办事项已完成: {todo.content}")
                    return True
            
            logger.warning(f"未找到待办事项: {content}")
            return False
            
        except Exception as e:
            logger.error(f"完成待办事项失败: {e}")
            raise
    
    def remove_todo(self, content: str) -> bool:
        """
        移除待办事项
        
        Args:
            content: 待办事项内容（支持部分匹配）
            
        Returns:
            是否找到并移除该待办事项
        """
        try:
            for i, todo in enumerate(self.data.todos):
                if content in todo.content:
                    removed = self.data.todos.pop(i)
                    self._save()
                    logger.info(f"待办事项已移除: {removed.content}")
                    return True
            
            logger.warning(f"未找到待办事项: {content}")
            return False
            
        except Exception as e:
            logger.error(f"移除待办事项失败: {e}")
            raise
    
    def add_issue(self, description: str, solution: str = "") -> None:
        """
        添加问题记录
        
        Args:
            description: 问题描述
            solution: 解决方案
        """
        try:
            issue_text = description
            if solution:
                issue_text += f" → 解决方案: {solution}"
            
            self.data.issues.append(issue_text)
            self._save()
            logger.info(f"问题记录已添加: {description}")
            
        except Exception as e:
            logger.error(f"添加问题记录失败: {e}")
            raise
    
    def add_next_step(self, step: str) -> None:
        """
        添加下一步计划
        
        Args:
            step: 下一步计划内容
        """
        try:
            self.data.next_steps.append(step)
            self._save()
            logger.info(f"下一步计划已添加: {step}")
            
        except Exception as e:
            logger.error(f"添加下一步计划失败: {e}")
            raise
    
    def clear_next_steps(self) -> None:
        """清空下一步计划"""
        try:
            self.data.next_steps.clear()
            self._save()
            logger.info("下一步计划已清空")
            
        except Exception as e:
            logger.error(f"清空下一步计划失败: {e}")
            raise
    
    def get_summary(self, max_length: int = 2000) -> str:
        """
        获取进度摘要（用于注入系统提示词）
        
        Args:
            max_length: 最大长度限制
            
        Returns:
            进度摘要文本
        """
        try:
            lines = []
            
            # 项目概述
            if self.data.project_description:
                lines.append(f"项目概述: {self.data.project_description[:200]}")
            
            # 当前状态
            if self.data.current_task:
                lines.append(f"当前任务: {self.data.current_task}")
            
            # 待办事项（未完成的）
            pending_todos = [t for t in self.data.todos if t.status != ProgressStatus.COMPLETED]
            if pending_todos:
                lines.append(f"待办事项 ({len(pending_todos)} 项):")
                for todo in pending_todos[:5]:  # 最多显示 5 个
                    lines.append(f"  - {todo.content}")
            
            # 最近完成的工作
            if self.data.completed_work:
                recent = self.data.completed_work[-1]
                lines.append(f"最近会话 ({recent.session_id}) 完成:")
                for task in recent.tasks[:3]:  # 最多显示 3 个
                    lines.append(f"  - {task.content}")
            
            # 下一步计划
            if self.data.next_steps:
                lines.append("下一步计划:")
                for step in self.data.next_steps[:3]:  # 最多显示 3 个
                    lines.append(f"  - {step}")
            
            # 问题记录
            if self.data.issues:
                lines.append(f"问题记录 ({len(self.data.issues)} 个)")
            
            summary = "\n".join(lines)
            
            # 截断到最大长度
            if len(summary) > max_length:
                summary = summary[:max_length] + "\n... (已截断)"
            
            return summary
            
        except Exception as e:
            logger.error(f"获取进度摘要失败: {e}")
            return f"获取进度摘要失败: {e}"
    
    def get_pending_todos(self) -> list[ProgressEntry]:
        """
        获取未完成的待办事项
        
        Returns:
            未完成的待办事项列表
        """
        return [t for t in self.data.todos if t.status != ProgressStatus.COMPLETED]
    
    def get_completed_todos(self) -> list[ProgressEntry]:
        """
        获取已完成的待办事项
        
        Returns:
            已完成的待办事项列表
        """
        return [t for t in self.data.todos if t.status == ProgressStatus.COMPLETED]
    
    # ==================== 异步方法 ====================
    
    async def async_create(
        self,
        project_description: str = "",
        initial_todos: list[str] | None = None,
    ) -> ProgressData:
        """
        异步创建新的进度文件
        
        Args:
            project_description: 项目描述
            initial_todos: 初始待办事项列表
            
        Returns:
            创建的进度数据
        """
        return await asyncio.to_thread(
            self.create,
            project_description=project_description,
            initial_todos=initial_todos,
        )
    
    async def async_load(self) -> ProgressData:
        """
        异步加载现有进度文件
        
        Returns:
            加载的进度数据
        """
        return await asyncio.to_thread(self.load)
    
    async def async_save(self) -> None:
        """异步保存进度数据到文件"""
        await asyncio.to_thread(self._save)
    
    async def async_update_status(
        self,
        current_task: str | None = None,
        estimated_remaining: str | None = None,
    ) -> None:
        """
        异步更新当前状态
        
        Args:
            current_task: 当前任务描述
            estimated_remaining: 预计剩余时间
        """
        await asyncio.to_thread(
            self.update_status,
            current_task=current_task,
            estimated_remaining=estimated_remaining,
        )
    
    async def async_add_work_record(
        self,
        session_id: str,
        tasks: list[str],
        summary: str = "",
    ) -> None:
        """
        异步添加工作记录
        
        Args:
            session_id: 会话 ID
            tasks: 完成的任务列表
            summary: 工作摘要
        """
        await asyncio.to_thread(
            self.add_work_record,
            session_id=session_id,
            tasks=tasks,
            summary=summary,
        )
    
    async def async_add_todo(
        self,
        content: str,
        priority: str = "medium",
    ) -> None:
        """
        异步添加待办事项
        
        Args:
            content: 待办事项内容
            priority: 优先级
        """
        await asyncio.to_thread(
            self.add_todo,
            content=content,
            priority=priority,
        )
    
    async def async_complete_todo(self, content: str) -> bool:
        """
        异步完成待办事项
        
        Args:
            content: 待办事项内容
            
        Returns:
            是否找到并完成该待办事项
        """
        return await asyncio.to_thread(self.complete_todo, content)
    
    async def async_add_issue(self, description: str, solution: str = "") -> None:
        """
        异步添加问题记录
        
        Args:
            description: 问题描述
            solution: 解决方案
        """
        await asyncio.to_thread(
            self.add_issue,
            description=description,
            solution=solution,
        )
    
    async def async_get_summary(self, max_length: int = 2000) -> str:
        """
        异步获取进度摘要
        
        Args:
            max_length: 最大长度限制
            
        Returns:
            进度摘要文本
        """
        return await asyncio.to_thread(self.get_summary, max_length=max_length)
    
    # ==================== 上下文管理器支持 ====================
    
    def __enter__(self) -> "ProgressManager":
        """进入上下文管理器"""
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """退出上下文管理器，自动保存"""
        if self._data is not None:
            try:
                self._save()
            except Exception as e:
                logger.warning(f"上下文退出时保存进度失败: {e}")


# ==================== 便捷函数 ====================

def create_progress_manager(
    working_dir: Path | str,
    progress_file: str | None = None,
) -> ProgressManager:
    """
    创建进度管理器的便捷函数
    
    Args:
        working_dir: 工作目录
        progress_file: 进度文件路径（可选）
        
    Returns:
        进度管理器实例
    """
    return ProgressManager(
        working_dir=Path(working_dir),
        progress_file=progress_file,
    )


def get_progress_summary(working_dir: Path | str) -> str:
    """
    获取进度摘要的便捷函数
    
    Args:
        working_dir: 工作目录
        
    Returns:
        进度摘要文本
    """
    manager = ProgressManager(working_dir=Path(working_dir))
    return manager.get_summary()
