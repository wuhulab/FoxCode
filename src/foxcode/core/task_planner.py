"""
FoxCode 智能任务规划器

提供复杂任务的自动分解、依赖分析和优先级排序功能。
支持任务进度追踪和工作量估算。

主要功能：
- 复杂任务自动分解
- 任务依赖关系分析
- 任务优先级排序
- 任务进度追踪和预估
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"          # 待处理
    READY = "ready"              # 准备就绪（依赖已满足）
    IN_PROGRESS = "in_progress"  # 进行中
    BLOCKED = "blocked"          # 被阻塞
    COMPLETED = "completed"      # 已完成
    FAILED = "failed"            # 失败
    SKIPPED = "skipped"          # 已跳过


class TaskPriority(str, Enum):
    """任务优先级"""
    CRITICAL = "critical"    # 关键任务
    HIGH = "high"           # 高优先级
    NORMAL = "normal"       # 普通优先级
    LOW = "low"             # 低优先级


class TaskType(str, Enum):
    """任务类型"""
    DESIGN = "design"           # 设计任务
    CODING = "coding"           # 编码任务
    TESTING = "testing"         # 测试任务
    DOCUMENTATION = "documentation"  # 文档任务
    REFACTORING = "refactoring"  # 重构任务
    DEBUGGING = "debugging"     # 调试任务
    REVIEW = "review"           # 审查任务
    DEPLOYMENT = "deployment"   # 部署任务
    RESEARCH = "research"       # 研究任务
    CONFIGURATION = "configuration"  # 配置任务


@dataclass
class SubTask:
    """
    子任务数据结构
    
    Attributes:
        id: 任务唯一标识符
        title: 任务标题
        description: 任务描述
        task_type: 任务类型
        priority: 优先级
        status: 当前状态
        dependencies: 依赖的任务 ID 列表
        estimated_effort: 预估工作量（分钟）
        actual_effort: 实际工作量（分钟）
        assignee: 分配给谁
        tags: 标签列表
        created_at: 创建时间
        started_at: 开始时间
        completed_at: 完成时间
        notes: 备注
        artifacts: 产物文件列表
        metadata: 额外元数据
    """
    id: str
    title: str
    description: str = ""
    task_type: TaskType = TaskType.CODING
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    dependencies: list[str] = field(default_factory=list)
    estimated_effort: int = 0  # 分钟
    actual_effort: int = 0
    assignee: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    notes: str = ""
    artifacts: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "task_type": self.task_type.value,
            "priority": self.priority.value,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "estimated_effort": self.estimated_effort,
            "actual_effort": self.actual_effort,
            "assignee": self.assignee,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "notes": self.notes,
            "artifacts": self.artifacts,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubTask":
        """从字典创建"""
        data["task_type"] = TaskType(data["task_type"])
        data["priority"] = TaskPriority(data["priority"])
        data["status"] = TaskStatus(data["status"])
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("started_at"):
            data["started_at"] = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            data["completed_at"] = datetime.fromisoformat(data["completed_at"])
        return cls(**data)
    
    def is_ready(self, completed_ids: set[str]) -> bool:
        """检查任务是否准备就绪"""
        return all(dep_id in completed_ids for dep_id in self.dependencies)
    
    def start(self) -> None:
        """开始任务"""
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = datetime.now()
    
    def complete(self, notes: str = "") -> None:
        """完成任务"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
        if self.started_at:
            self.actual_effort = int((self.completed_at - self.started_at).total_seconds() / 60)
        if notes:
            self.notes = notes
    
    def fail(self, reason: str = "") -> None:
        """标记任务失败"""
        self.status = TaskStatus.FAILED
        if reason:
            self.notes = reason


@dataclass
class DependencyGraph:
    """
    任务依赖图
    
    Attributes:
        nodes: 任务节点
        edges: 依赖边 (from_id, to_id)
        levels: 拓扑层级
    """
    nodes: list[str] = field(default_factory=list)
    edges: list[tuple[str, str]] = field(default_factory=list)
    levels: list[list[str]] = field(default_factory=list)
    
    def get_dependencies(self, task_id: str) -> list[str]:
        """获取任务的所有依赖"""
        return [from_id for from_id, to_id in self.edges if to_id == task_id]
    
    def get_dependents(self, task_id: str) -> list[str]:
        """获取依赖此任务的所有任务"""
        return [to_id for from_id, to_id in self.edges if from_id == task_id]
    
    def has_cycle(self) -> bool:
        """检查是否存在循环依赖"""
        visited = set()
        rec_stack = set()
        
        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            
            for dependent in self.get_dependents(node):
                if dependent not in visited:
                    if dfs(dependent):
                        return True
                elif dependent in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        for node in self.nodes:
            if node not in visited:
                if dfs(node):
                    return True
        
        return False


@dataclass
class EffortEstimate:
    """
    工作量估算
    
    Attributes:
        min_minutes: 最小估算（分钟）
        max_minutes: 最大估算（分钟）
        most_likely_minutes: 最可能估算（分钟）
        confidence: 置信度
        factors: 影响因素
    """
    min_minutes: int = 0
    max_minutes: int = 0
    most_likely_minutes: int = 0
    confidence: float = 0.7
    factors: list[str] = field(default_factory=list)
    
    @property
    def expected_minutes(self) -> float:
        """期望值（使用 PERT 公式）"""
        return (self.min_minutes + 4 * self.most_likely_minutes + self.max_minutes) / 6
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "min_minutes": self.min_minutes,
            "max_minutes": self.max_minutes,
            "most_likely_minutes": self.most_likely_minutes,
            "expected_minutes": self.expected_minutes,
            "confidence": self.confidence,
            "factors": self.factors,
        }


@dataclass
class TaskPlan:
    """
    任务计划
    
    Attributes:
        id: 计划 ID
        title: 计划标题
        description: 计划描述
        tasks: 子任务列表
        created_at: 创建时间
        updated_at: 更新时间
        metadata: 元数据
    """
    id: str
    title: str
    description: str = ""
    tasks: list[SubTask] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def get_task(self, task_id: str) -> SubTask | None:
        """获取任务"""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None
    
    def get_completed_ids(self) -> set[str]:
        """获取已完成任务的 ID 集合"""
        return {t.id for t in self.tasks if t.status == TaskStatus.COMPLETED}


@dataclass
class ProgressReport:
    """
    进度报告
    
    Attributes:
        total_tasks: 总任务数
        completed_tasks: 已完成任务数
        in_progress_tasks: 进行中任务数
        pending_tasks: 待处理任务数
        blocked_tasks: 阻塞任务数
        failed_tasks: 失败任务数
        total_estimated_effort: 总预估工作量
        total_actual_effort: 总实际工作量
        progress_percentage: 进度百分比
        estimated_remaining_time: 预估剩余时间
        current_task: 当前任务
        blockers: 阻塞项列表
    """
    total_tasks: int = 0
    completed_tasks: int = 0
    in_progress_tasks: int = 0
    pending_tasks: int = 0
    blocked_tasks: int = 0
    failed_tasks: int = 0
    total_estimated_effort: int = 0
    total_actual_effort: int = 0
    progress_percentage: float = 0.0
    estimated_remaining_time: int = 0
    current_task: SubTask | None = None
    blockers: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "in_progress_tasks": self.in_progress_tasks,
            "pending_tasks": self.pending_tasks,
            "blocked_tasks": self.blocked_tasks,
            "failed_tasks": self.failed_tasks,
            "total_estimated_effort": self.total_estimated_effort,
            "total_actual_effort": self.total_actual_effort,
            "progress_percentage": self.progress_percentage,
            "estimated_remaining_time": self.estimated_remaining_time,
            "current_task": self.current_task.to_dict() if self.current_task else None,
            "blockers": self.blockers,
        }


class TaskPlannerConfig(BaseModel):
    """
    任务规划器配置
    
    Attributes:
        max_subtasks: 最大子任务数
        default_effort_hours: 默认工作量估算（小时）
        auto_prioritize: 是否自动优先级排序
        detect_dependencies: 是否自动检测依赖
        parallel_execution: 是否支持并行执行
    """
    max_subtasks: int = Field(default=20, ge=1)
    default_effort_hours: float = Field(default=2.0, ge=0.1)
    auto_prioritize: bool = True
    detect_dependencies: bool = True
    parallel_execution: bool = True


class IntelligentTaskPlanner:
    """
    智能任务规划器
    
    提供复杂任务的自动分解、依赖分析和优先级排序功能。
    
    Example:
        >>> planner = IntelligentTaskPlanner()
        >>> tasks = await planner.decompose_task("实现用户认证系统")
        >>> graph = planner.analyze_dependencies(tasks)
        >>> sorted_tasks = planner.prioritize_tasks(tasks)
    """
    
    # 任务分解模板
    DECOMPOSITION_TEMPLATES = {
        "认证系统": [
            ("设计认证流程", TaskType.DESIGN, TaskPriority.HIGH),
            ("实现用户模型", TaskType.CODING, TaskPriority.HIGH),
            ("实现登录功能", TaskType.CODING, TaskPriority.HIGH),
            ("实现注册功能", TaskType.CODING, TaskPriority.HIGH),
            ("添加密码加密", TaskType.CODING, TaskPriority.HIGH),
            ("实现会话管理", TaskType.CODING, TaskPriority.NORMAL),
            ("编写单元测试", TaskType.TESTING, TaskPriority.NORMAL),
            ("编写 API 文档", TaskType.DOCUMENTATION, TaskPriority.LOW),
        ],
        "API": [
            ("设计 API 接口", TaskType.DESIGN, TaskPriority.HIGH),
            ("实现路由处理", TaskType.CODING, TaskPriority.HIGH),
            ("添加请求验证", TaskType.CODING, TaskPriority.NORMAL),
            ("实现错误处理", TaskType.CODING, TaskPriority.NORMAL),
            ("编写 API 文档", TaskType.DOCUMENTATION, TaskPriority.NORMAL),
            ("编写测试用例", TaskType.TESTING, TaskPriority.NORMAL),
        ],
        "数据库": [
            ("设计数据模型", TaskType.DESIGN, TaskPriority.HIGH),
            ("创建数据库迁移", TaskType.CODING, TaskPriority.HIGH),
            ("实现 CRUD 操作", TaskType.CODING, TaskPriority.HIGH),
            ("添加索引优化", TaskType.CODING, TaskPriority.NORMAL),
            ("编写数据测试", TaskType.TESTING, TaskPriority.NORMAL),
        ],
        "前端": [
            ("设计 UI 组件", TaskType.DESIGN, TaskPriority.HIGH),
            ("实现页面布局", TaskType.CODING, TaskPriority.HIGH),
            ("添加交互逻辑", TaskType.CODING, TaskPriority.NORMAL),
            ("实现状态管理", TaskType.CODING, TaskPriority.NORMAL),
            ("样式优化", TaskType.CODING, TaskPriority.LOW),
            ("响应式适配", TaskType.CODING, TaskPriority.LOW),
        ],
        "测试": [
            ("编写单元测试", TaskType.TESTING, TaskPriority.HIGH),
            ("编写集成测试", TaskType.TESTING, TaskPriority.NORMAL),
            ("编写端到端测试", TaskType.TESTING, TaskPriority.NORMAL),
            ("配置测试环境", TaskType.CONFIGURATION, TaskPriority.HIGH),
            ("生成测试报告", TaskType.TESTING, TaskPriority.LOW),
        ],
        "部署": [
            ("配置部署环境", TaskType.CONFIGURATION, TaskPriority.HIGH),
            ("编写部署脚本", TaskType.CODING, TaskPriority.HIGH),
            ("配置 CI/CD", TaskType.CONFIGURATION, TaskPriority.NORMAL),
            ("设置监控告警", TaskType.CONFIGURATION, TaskPriority.NORMAL),
            ("编写部署文档", TaskType.DOCUMENTATION, TaskPriority.LOW),
        ],
    }
    
    # 关键词到任务类型的映射
    KEYWORD_TYPE_MAP = {
        "设计": TaskType.DESIGN,
        "实现": TaskType.CODING,
        "开发": TaskType.CODING,
        "编写": TaskType.CODING,
        "测试": TaskType.TESTING,
        "调试": TaskType.DEBUGGING,
        "重构": TaskType.REFACTORING,
        "文档": TaskType.DOCUMENTATION,
        "部署": TaskType.DEPLOYMENT,
        "配置": TaskType.CONFIGURATION,
        "研究": TaskType.RESEARCH,
        "审查": TaskType.REVIEW,
    }
    
    # 关键词到优先级的映射
    KEYWORD_PRIORITY_MAP = {
        "关键": TaskPriority.CRITICAL,
        "紧急": TaskPriority.CRITICAL,
        "重要": TaskPriority.HIGH,
        "优先": TaskPriority.HIGH,
        "尽快": TaskPriority.HIGH,
        "一般": TaskPriority.NORMAL,
        "普通": TaskPriority.NORMAL,
        "可选": TaskPriority.LOW,
        "低": TaskPriority.LOW,
    }
    
    def __init__(self, config: TaskPlannerConfig | None = None):
        """
        初始化任务规划器
        
        Args:
            config: 规划器配置
        """
        self.config = config or TaskPlannerConfig()
        self._task_counter = 0
        logger.info(f"智能任务规划器初始化完成")
    
    def _generate_task_id(self) -> str:
        """生成任务 ID"""
        self._task_counter += 1
        return f"task-{self._task_counter:03d}"
    
    async def decompose_task(self, description: str) -> list[SubTask]:
        """
        分解任务
        
        根据任务描述自动分解为子任务列表。
        
        Args:
            description: 任务描述
            
        Returns:
            子任务列表
        """
        tasks = []
        
        # 检测任务类型并应用模板
        matched_template = self._match_template(description)
        
        if matched_template:
            # 使用模板生成任务
            for i, (title, task_type, priority) in enumerate(matched_template):
                task = SubTask(
                    id=f"{self._generate_task_id()}-{i+1:02d}",
                    title=title,
                    description=f"自动分解: {title}",
                    task_type=task_type,
                    priority=priority,
                    estimated_effort=self._estimate_from_type(task_type),
                )
                # 设置依赖关系（顺序依赖）
                if i > 0:
                    task.dependencies = [tasks[i-1].id]
                tasks.append(task)
        else:
            # 基于关键词分析分解
            tasks = self._decompose_by_keywords(description)
        
        # 限制子任务数量
        if len(tasks) > self.config.max_subtasks:
            tasks = tasks[:self.config.max_subtasks]
            logger.warning(f"子任务数量超过限制，已截断为 {self.config.max_subtasks}")
        
        logger.info(f"任务分解完成，生成 {len(tasks)} 个子任务")
        return tasks
    
    def _match_template(self, description: str) -> list[tuple] | None:
        """匹配任务模板"""
        desc_lower = description.lower()
        
        for keyword, template in self.DECOMPOSITION_TEMPLATES.items():
            if keyword in desc_lower or keyword in description:
                return template
        
        return None
    
    def _decompose_by_keywords(self, description: str) -> list[SubTask]:
        """基于关键词分解任务"""
        tasks = []
        
        # 按句子分割
        sentences = re.split(r'[，,。.；;]\s*', description)
        
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if not sentence or len(sentence) < 3:
                continue
            
            # 检测任务类型
            task_type = TaskType.CODING
            for keyword, t_type in self.KEYWORD_TYPE_MAP.items():
                if keyword in sentence:
                    task_type = t_type
                    break
            
            # 检测优先级
            priority = TaskPriority.NORMAL
            for keyword, p in self.KEYWORD_PRIORITY_MAP.items():
                if keyword in sentence:
                    priority = p
                    break
            
            task = SubTask(
                id=f"{self._generate_task_id()}-{i+1:02d}",
                title=sentence[:100],  # 限制标题长度
                description=sentence,
                task_type=task_type,
                priority=priority,
                estimated_effort=self._estimate_from_type(task_type),
            )
            tasks.append(task)
        
        # 如果没有分解出任务，创建一个默认任务
        if not tasks:
            tasks.append(SubTask(
                id=self._generate_task_id(),
                title=description[:100],
                description=description,
                estimated_effort=int(self.config.default_effort_hours * 60),
            ))
        
        return tasks
    
    def _estimate_from_type(self, task_type: TaskType) -> int:
        """根据任务类型估算工作量"""
        estimates = {
            TaskType.DESIGN: 60,       # 1 小时
            TaskType.CODING: 120,      # 2 小时
            TaskType.TESTING: 60,      # 1 小时
            TaskType.DOCUMENTATION: 30, # 30 分钟
            TaskType.REFACTORING: 90,   # 1.5 小时
            TaskType.DEBUGGING: 60,     # 1 小时
            TaskType.REVIEW: 30,        # 30 分钟
            TaskType.DEPLOYMENT: 45,    # 45 分钟
            TaskType.RESEARCH: 120,     # 2 小时
            TaskType.CONFIGURATION: 30, # 30 分钟
        }
        return estimates.get(task_type, 60)
    
    def analyze_dependencies(self, tasks: list[SubTask]) -> DependencyGraph:
        """
        分析任务依赖关系
        
        Args:
            tasks: 任务列表
            
        Returns:
            依赖图
        """
        graph = DependencyGraph()
        graph.nodes = [t.id for t in tasks]
        
        # 收集显式依赖
        for task in tasks:
            for dep_id in task.dependencies:
                graph.edges.append((dep_id, task.id))
        
        # 自动检测隐式依赖
        if self.config.detect_dependencies:
            graph = self._detect_implicit_dependencies(tasks, graph)
        
        # 计算拓扑层级
        graph.levels = self._topological_sort(tasks, graph)
        
        # 检查循环依赖
        if graph.has_cycle():
            logger.warning("检测到循环依赖，可能导致任务阻塞")
        
        return graph
    
    def _detect_implicit_dependencies(
        self,
        tasks: list[SubTask],
        graph: DependencyGraph,
    ) -> DependencyGraph:
        """检测隐式依赖"""
        # 定义任务类型的自然顺序
        type_order = {
            TaskType.DESIGN: 0,
            TaskType.RESEARCH: 0,
            TaskType.CODING: 1,
            TaskType.REFACTORING: 1,
            TaskType.DEBUGGING: 2,
            TaskType.TESTING: 2,
            TaskType.REVIEW: 3,
            TaskType.DOCUMENTATION: 3,
            TaskType.CONFIGURATION: 1,
            TaskType.DEPLOYMENT: 4,
        }
        
        # 按类型顺序添加隐式依赖
        for i, task in enumerate(tasks):
            task_order = type_order.get(task.task_type, 1)
            
            for j, prev_task in enumerate(tasks[:i]):
                prev_order = type_order.get(prev_task.task_type, 1)
                
                # 如果前一个任务的类型顺序小于当前任务，添加依赖
                if prev_order < task_order and prev_task.id not in task.dependencies:
                    # 检查是否已经存在依赖关系
                    if not any(e[0] == prev_task.id and e[1] == task.id for e in graph.edges):
                        graph.edges.append((prev_task.id, task.id))
                        task.dependencies.append(prev_task.id)
        
        return graph
    
    def _topological_sort(
        self,
        tasks: list[SubTask],
        graph: DependencyGraph,
    ) -> list[list[str]]:
        """拓扑排序"""
        # 计算入度
        in_degree = {t.id: 0 for t in tasks}
        for from_id, to_id in graph.edges:
            in_degree[to_id] += 1
        
        # 按层级分组
        levels = []
        remaining = set(in_degree.keys())
        
        while remaining:
            # 找出入度为 0 的节点
            level = [node for node in remaining if in_degree[node] == 0]
            
            if not level:
                # 存在循环依赖，按优先级选择
                remaining_tasks = [t for t in tasks if t.id in remaining]
                remaining_tasks.sort(key=lambda t: (
                    {"critical": 0, "high": 1, "normal": 2, "low": 3}.get(t.priority.value, 2)
                ))
                level = [remaining_tasks[0].id]
            
            levels.append(level)
            
            # 移除当前层节点，更新入度
            for node in level:
                remaining.remove(node)
                for from_id, to_id in graph.edges:
                    if from_id == node:
                        in_degree[to_id] -= 1
        
        return levels
    
    def prioritize_tasks(self, tasks: list[SubTask]) -> list[SubTask]:
        """
        任务优先级排序
        
        Args:
            tasks: 任务列表
            
        Returns:
            排序后的任务列表
        """
        # 计算优先级分数
        def priority_score(task: SubTask) -> tuple:
            # 优先级权重
            priority_weights = {
                TaskPriority.CRITICAL: 0,
                TaskPriority.HIGH: 1,
                TaskPriority.NORMAL: 2,
                TaskPriority.LOW: 3,
            }
            
            # 状态权重（已完成的排后面）
            status_weights = {
                TaskStatus.PENDING: 0,
                TaskStatus.READY: 0,
                TaskStatus.IN_PROGRESS: 0,
                TaskStatus.BLOCKED: 1,
                TaskStatus.COMPLETED: 2,
                TaskStatus.FAILED: 1,
                TaskStatus.SKIPPED: 2,
            }
            
            return (
                status_weights.get(task.status, 0),
                priority_weights.get(task.priority, 2),
                len(task.dependencies),  # 依赖少的优先
            )
        
        return sorted(tasks, key=priority_score)
    
    def estimate_effort(self, task: SubTask) -> EffortEstimate:
        """
        估算任务工作量
        
        Args:
            task: 任务
            
        Returns:
            工作量估算
        """
        base_effort = self._estimate_from_type(task.task_type)
        
        # 根据描述长度调整
        desc_factor = min(len(task.description) / 200, 2.0)
        
        # 根据依赖数量调整
        dep_factor = 1 + len(task.dependencies) * 0.1
        
        # 计算估算范围
        most_likely = int(base_effort * desc_factor * dep_factor)
        min_minutes = int(most_likely * 0.5)
        max_minutes = int(most_likely * 2.0)
        
        # 影响因素
        factors = []
        if desc_factor > 1.2:
            factors.append("复杂描述")
        if dep_factor > 1.1:
            factors.append("存在依赖")
        if task.task_type == TaskType.RESEARCH:
            factors.append("不确定性高")
        
        return EffortEstimate(
            min_minutes=min_minutes,
            max_minutes=max_minutes,
            most_likely_minutes=most_likely,
            confidence=0.7 if not factors else 0.5,
            factors=factors,
        )
    
    def track_progress(self, plan: TaskPlan) -> ProgressReport:
        """
        追踪进度
        
        Args:
            plan: 任务计划
            
        Returns:
            进度报告
        """
        tasks = plan.tasks
        
        # 统计各状态任务数量
        status_counts = {}
        for status in TaskStatus:
            status_counts[status] = sum(1 for t in tasks if t.status == status)
        
        # 计算工作量
        total_estimated = sum(t.estimated_effort for t in tasks)
        total_actual = sum(t.actual_effort for t in tasks)
        
        # 计算进度百分比
        completed = status_counts[TaskStatus.COMPLETED]
        total = len(tasks)
        progress = (completed / total * 100) if total > 0 else 0
        
        # 估算剩余时间
        remaining_tasks = [t for t in tasks if t.status not in (TaskStatus.COMPLETED, TaskStatus.SKIPPED)]
        remaining_effort = sum(t.estimated_effort for t in remaining_tasks)
        
        # 获取当前任务
        current_task = None
        for task in tasks:
            if task.status == TaskStatus.IN_PROGRESS:
                current_task = task
                break
        
        # 获取阻塞项
        blockers = []
        for task in tasks:
            if task.status == TaskStatus.BLOCKED:
                blockers.append(f"{task.id}: {task.title}")
        
        return ProgressReport(
            total_tasks=total,
            completed_tasks=completed,
            in_progress_tasks=status_counts[TaskStatus.IN_PROGRESS],
            pending_tasks=status_counts[TaskStatus.PENDING],
            blocked_tasks=status_counts[TaskStatus.BLOCKED],
            failed_tasks=status_counts[TaskStatus.FAILED],
            total_estimated_effort=total_estimated,
            total_actual_effort=total_actual,
            progress_percentage=progress,
            estimated_remaining_time=remaining_effort,
            current_task=current_task,
            blockers=blockers,
        )
    
    def suggest_next_task(self, plan: TaskPlan) -> SubTask | None:
        """
        建议下一个任务
        
        Args:
            plan: 任务计划
            
        Returns:
            建议的任务，如果没有则返回 None
        """
        completed_ids = plan.get_completed_ids()
        
        # 找出准备就绪的任务
        ready_tasks = []
        for task in plan.tasks:
            if task.status == TaskStatus.PENDING and task.is_ready(completed_ids):
                ready_tasks.append(task)
        
        if not ready_tasks:
            # 检查是否有进行中的任务
            for task in plan.tasks:
                if task.status == TaskStatus.IN_PROGRESS:
                    return task
            return None
        
        # 按优先级排序
        ready_tasks = self.prioritize_tasks(ready_tasks)
        
        return ready_tasks[0] if ready_tasks else None
    
    def identify_parallel_tasks(self, tasks: list[SubTask]) -> list[list[SubTask]]:
        """
        识别可并行执行的任务
        
        Args:
            tasks: 任务列表
            
        Returns:
            可并行执行的任务组列表
        """
        if not self.config.parallel_execution:
            return [[t] for t in tasks]
        
        graph = self.analyze_dependencies(tasks)
        
        # 按拓扑层级分组
        parallel_groups = []
        for level in graph.levels:
            group = [t for t in tasks if t.id in level]
            if group:
                parallel_groups.append(group)
        
        return parallel_groups
    
    def create_plan(
        self,
        title: str,
        description: str,
        tasks: list[SubTask] | None = None,
    ) -> TaskPlan:
        """
        创建任务计划
        
        Args:
            title: 计划标题
            description: 计划描述
            tasks: 任务列表（可选）
            
        Returns:
            任务计划
        """
        plan_id = f"plan-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        return TaskPlan(
            id=plan_id,
            title=title,
            description=description,
            tasks=tasks or [],
        )


# 创建默认规划器实例
task_planner = IntelligentTaskPlanner()
