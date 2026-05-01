"""
FoxCode 工作流程管理模块 - 标准化的开发流程管理

这个文件定义了FoxCode在长时间运行模式下的标准工作流程：
设计规划 -> 编码实现 -> 质量评估 -> 本地测试 -> 合并主分支 -> 集成测试 -> 推送分支

为什么需要标准化工作流程？
1. 保证代码质量：每个阶段都有明确的目标和验收标准
2. 减少错误：测试和评估阶段可以及时发现问题
3. 提高效率：自动化流程减少人工干预
4. 可追溯性：记录每个阶段的状态和结果

工作流程阶段：
1. DESIGN: 设计规划 - 分析需求、设计方案
2. CODING: 编码实现 - 编写代码、实现功能
3. EVALUATION: 质量评估 - 代码审查、质量检查
4. LOCAL_TEST: 本地测试 - 运行测试用例
5. MERGE_MAIN: 合并主分支 - 拉取并合并最新代码
6. INTEGRATION_TEST: 集成测试 - 测试整体功能
7. PUSH: 推送分支 - 推送到远程仓库
8. COMPLETED: 完成 - 工作流程结束

使用方式：
    from foxcode.core.workflow import WorkflowManager
    
    manager = WorkflowManager(config)
    workflow = manager.create_workflow("实现用户登录功能")
    
    # 推进工作流程
    await manager.advance_phase(workflow.id)
    
    # 获取当前状态
    status = manager.get_status(workflow.id)

关键特性：
- 自动化阶段转换
- 状态持久化
- 失败重试机制
- 进度可视化
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class WorkflowPhase(str, Enum):
    """
    工作流程阶段枚举
    
    定义完整的工作流程阶段顺序
    """
    DESIGN = "design"                    # 设计规划阶段
    CODING = "coding"                     # 编码实现阶段
    EVALUATION = "evaluation"             # 评估阶段（新增）
    LOCAL_TEST = "local_test"            # 本地完整测试阶段
    MERGE_MAIN = "merge_main"            # 拉取主分支合并阶段
    INTEGRATION_TEST = "integration_test"  # 集成测试阶段
    PUSH = "push"                         # 推送分支阶段
    COMPLETED = "completed"               # 已完成

    @classmethod
    def get_order(cls) -> list[WorkflowPhase]:
        """获取阶段顺序列表"""
        return [
            cls.DESIGN,
            cls.CODING,
            cls.EVALUATION,  # 新增评估阶段
            cls.LOCAL_TEST,
            cls.MERGE_MAIN,
            cls.INTEGRATION_TEST,
            cls.PUSH,
            cls.COMPLETED,
        ]

    def get_next(self) -> WorkflowPhase | None:
        """获取下一个阶段"""
        order = self.get_order()
        try:
            idx = order.index(self)
            if idx < len(order) - 1:
                return order[idx + 1]
        except ValueError:
            pass
        return None

    def get_previous(self) -> WorkflowPhase | None:
        """获取上一个阶段"""
        order = self.get_order()
        try:
            idx = order.index(self)
            if idx > 0:
                return order[idx - 1]
        except ValueError:
            pass
        return None

    def get_display_name(self) -> str:
        """获取阶段显示名称"""
        names = {
            WorkflowPhase.DESIGN: "设计规划",
            WorkflowPhase.CODING: "编码实现",
            WorkflowPhase.EVALUATION: "质量评估",  # 新增
            WorkflowPhase.LOCAL_TEST: "本地测试",
            WorkflowPhase.MERGE_MAIN: "合并主分支",
            WorkflowPhase.INTEGRATION_TEST: "集成测试",
            WorkflowPhase.PUSH: "推送分支",
            WorkflowPhase.COMPLETED: "已完成",
        }
        return names.get(self, self.value)


class PhaseStatus(str, Enum):
    """阶段状态枚举"""
    PENDING = "pending"           # 待处理
    IN_PROGRESS = "in_progress"   # 进行中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
    SKIPPED = "skipped"           # 已跳过
    BLOCKED = "blocked"           # 已阻塞


@dataclass
class PhaseResult:
    """
    阶段执行结果
    
    记录单个阶段的执行结果和相关信息
    """
    phase: WorkflowPhase
    status: PhaseStatus = PhaseStatus.PENDING
    started_at: str | None = None
    completed_at: str | None = None
    output: str = ""
    error: str | None = None
    artifacts: list[str] = field(default_factory=list)  # 产物文件列表
    notes: str = ""

    def mark_started(self) -> None:
        """标记阶段开始"""
        self.status = PhaseStatus.IN_PROGRESS
        self.started_at = datetime.now().isoformat()

    def mark_completed(self, output: str = "", artifacts: list[str] | None = None) -> None:
        """标记阶段完成"""
        self.status = PhaseStatus.COMPLETED
        self.completed_at = datetime.now().isoformat()
        self.output = output
        if artifacts:
            self.artifacts = artifacts

    def mark_failed(self, error: str) -> None:
        """标记阶段失败"""
        self.status = PhaseStatus.FAILED
        self.completed_at = datetime.now().isoformat()
        self.error = error

    def mark_skipped(self, reason: str = "") -> None:
        """标记阶段跳过"""
        self.status = PhaseStatus.SKIPPED
        self.notes = reason

    @property
    def duration_seconds(self) -> float | None:
        """计算阶段持续时间（秒）"""
        if not self.started_at or not self.completed_at:
            return None
        start = datetime.fromisoformat(self.started_at)
        end = datetime.fromisoformat(self.completed_at)
        return (end - start).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "phase": self.phase.value,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "output": self.output,
            "error": self.error,
            "artifacts": self.artifacts,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PhaseResult:
        """从字典创建"""
        return cls(
            phase=WorkflowPhase(data["phase"]),
            status=PhaseStatus(data.get("status", "pending")),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            output=data.get("output", ""),
            error=data.get("error"),
            artifacts=data.get("artifacts", []),
            notes=data.get("notes", ""),
        )


@dataclass
class WorkflowInstance:
    """
    工作流程实例
    
    代表一个完整的工作流程执行实例，关联到具体的功能或任务
    """
    id: str                                    # 工作流程实例 ID
    feature_id: str                            # 关联的功能 ID
    branch_name: str = ""                      # 工作分支名称
    current_phase: WorkflowPhase = WorkflowPhase.DESIGN
    phase_results: dict[WorkflowPhase, PhaseResult] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """初始化阶段结果"""
        # 确保所有阶段都有结果记录
        for phase in WorkflowPhase.get_order():
            if phase not in self.phase_results:
                self.phase_results[phase] = PhaseResult(phase=phase)

    def get_phase_result(self, phase: WorkflowPhase) -> PhaseResult:
        """获取指定阶段的结果"""
        if phase not in self.phase_results:
            self.phase_results[phase] = PhaseResult(phase=phase)
        return self.phase_results[phase]

    def advance_to_phase(self, phase: WorkflowPhase) -> bool:
        """
        推进到指定阶段
        
        Args:
            phase: 目标阶段
            
        Returns:
            是否成功推进
        """
        order = WorkflowPhase.get_order()
        try:
            current_idx = order.index(self.current_phase)
            target_idx = order.index(phase)

            # 只能向前推进到下一个阶段或当前阶段
            if target_idx > current_idx + 1:
                logger.warning(f"无法跳过阶段: {self.current_phase} -> {phase}")
                return False

            self.current_phase = phase
            self.updated_at = datetime.now().isoformat()
            logger.info(f"工作流程 {self.id} 推进到阶段: {phase.get_display_name()}")
            return True

        except ValueError:
            logger.error(f"无效的阶段: {phase}")
            return False

    def complete_phase(
        self,
        phase: WorkflowPhase,
        output: str = "",
        artifacts: list[str] | None = None,
    ) -> bool:
        """
        完成指定阶段并自动推进到下一阶段
        
        Args:
            phase: 要完成的阶段
            output: 输出信息
            artifacts: 产物文件列表
            
        Returns:
            是否成功完成并推进
        """
        result = self.get_phase_result(phase)
        result.mark_completed(output, artifacts)

        # 自动推进到下一阶段
        next_phase = phase.get_next()
        if next_phase:
            self.current_phase = next_phase
            # 初始化下一阶段
            next_result = self.get_phase_result(next_phase)
            next_result.mark_started()

        self.updated_at = datetime.now().isoformat()
        logger.info(f"阶段 {phase.get_display_name()} 已完成")
        return True

    def fail_phase(self, phase: WorkflowPhase, error: str) -> None:
        """标记阶段失败"""
        result = self.get_phase_result(phase)
        result.mark_failed(error)
        self.updated_at = datetime.now().isoformat()
        logger.error(f"阶段 {phase.get_display_name()} 失败: {error}")

    def get_progress(self) -> dict[str, Any]:
        """获取进度信息"""
        order = WorkflowPhase.get_order()
        completed = sum(
            1 for p in order[:-1]  # 排除 COMPLETED
            if self.phase_results.get(p, PhaseResult(p)).status == PhaseStatus.COMPLETED
        )
        total = len(order) - 1  # 排除 COMPLETED

        return {
            "workflow_id": self.id,
            "feature_id": self.feature_id,
            "current_phase": self.current_phase.value,
            "current_phase_display": self.current_phase.get_display_name(),
            "completed_phases": completed,
            "total_phases": total,
            "progress_percent": round(completed / total * 100, 1) if total > 0 else 0,
            "branch_name": self.branch_name,
        }

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "feature_id": self.feature_id,
            "branch_name": self.branch_name,
            "current_phase": self.current_phase.value,
            "phase_results": {
                p.value: r.to_dict()
                for p, r in self.phase_results.items()
            },
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
            "progress": self.get_progress(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowInstance:
        """从字典创建"""
        phase_results = {}
        for p_str, r_data in data.get("phase_results", {}).items():
            phase = WorkflowPhase(p_str)
            phase_results[phase] = PhaseResult.from_dict(r_data)

        return cls(
            id=data["id"],
            feature_id=data["feature_id"],
            branch_name=data.get("branch_name", ""),
            current_phase=WorkflowPhase(data.get("current_phase", "design")),
            phase_results=phase_results,
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
        )

    def to_markdown(self) -> str:
        """转换为 Markdown 格式"""
        lines = [
            f"# 工作流程: {self.id}",
            "",
            f"**功能 ID**: {self.feature_id}",
            f"**分支**: {self.branch_name or '未创建'}",
            f"**当前阶段**: {self.current_phase.get_display_name()}",
            f"**创建时间**: {self.created_at}",
            "",
            "## 阶段详情",
            "",
        ]

        for phase in WorkflowPhase.get_order():
            result = self.get_phase_result(phase)
            status_icon = {
                PhaseStatus.PENDING: "⏳",
                PhaseStatus.IN_PROGRESS: "🔄",
                PhaseStatus.COMPLETED: "✅",
                PhaseStatus.FAILED: "❌",
                PhaseStatus.SKIPPED: "⏭️",
                PhaseStatus.BLOCKED: "🚫",
            }.get(result.status, "❓")

            lines.append(f"### {status_icon} {phase.get_display_name()}")
            lines.append(f"- 状态: {result.status.value}")

            if result.started_at:
                lines.append(f"- 开始时间: {result.started_at}")
            if result.completed_at:
                lines.append(f"- 完成时间: {result.completed_at}")
            if result.duration_seconds:
                lines.append(f"- 持续时间: {result.duration_seconds:.1f} 秒")
            if result.output:
                lines.append(f"- 输出: {result.output[:200]}...")
            if result.error:
                lines.append(f"- 错误: {result.error}")
            if result.artifacts:
                lines.append(f"- 产物: {', '.join(result.artifacts)}")

            lines.append("")

        return "\n".join(lines)


class WorkflowManager:
    """
    工作流程管理器
    
    管理工作流程实例的创建、执行、状态追踪和持久化
    """

    DEFAULT_WORKFLOW_DIR = ".foxcode/workflows"

    def __init__(self, working_dir: Path, workflow_dir: str | None = None):
        """
        初始化工作流程管理器
        
        Args:
            working_dir: 工作目录
            workflow_dir: 工作流程存储目录（相对于工作目录）
        """
        self.working_dir = Path(working_dir)
        self.workflow_dir = self.working_dir / (workflow_dir or self.DEFAULT_WORKFLOW_DIR)
        self._workflows: dict[str, WorkflowInstance] = {}

        # 阶段执行器注册表
        self._phase_executors: dict[WorkflowPhase, Callable] = {}

        # 确保目录存在
        self._ensure_directory()

        logger.debug(f"工作流程管理器初始化完成，目录: {self.workflow_dir}")

    def _ensure_directory(self) -> None:
        """确保工作流程目录存在"""
        try:
            self.workflow_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"创建工作流程目录失败: {e}")
            raise

    def register_phase_executor(
        self,
        phase: WorkflowPhase,
        executor: Callable[[WorkflowInstance, dict[str, Any]], Any],
    ) -> None:
        """
        注册阶段执行器
        
        Args:
            phase: 阶段
            executor: 执行函数，接收工作流实例和参数，返回执行结果
        """
        self._phase_executors[phase] = executor
        logger.debug(f"已注册阶段执行器: {phase.get_display_name()}")

    def create_workflow(
        self,
        feature_id: str,
        branch_name: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> WorkflowInstance:
        """
        创建新的工作流程实例
        
        Args:
            feature_id: 关联的功能 ID
            branch_name: 工作分支名称
            metadata: 元数据
            
        Returns:
            创建的工作流程实例
        """
        # 生成工作流程 ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        workflow_id = f"WF-{feature_id}-{timestamp}"

        workflow = WorkflowInstance(
            id=workflow_id,
            feature_id=feature_id,
            branch_name=branch_name,
            metadata=metadata or {},
        )

        # 初始化第一个阶段
        first_phase = WorkflowPhase.DESIGN
        result = workflow.get_phase_result(first_phase)
        result.mark_started()

        self._workflows[workflow_id] = workflow
        self._save_workflow(workflow)

        logger.info(f"已创建工作流程: {workflow_id}")
        return workflow

    def get_workflow(self, workflow_id: str) -> WorkflowInstance | None:
        """
        获取工作流程实例
        
        Args:
            workflow_id: 工作流程 ID
            
        Returns:
            工作流程实例，不存在则返回 None
        """
        # 先从内存获取
        if workflow_id in self._workflows:
            return self._workflows[workflow_id]

        # 尝试从文件加载
        workflow = self._load_workflow(workflow_id)
        if workflow:
            self._workflows[workflow_id] = workflow
        return workflow

    def get_workflow_by_feature(self, feature_id: str) -> WorkflowInstance | None:
        """
        根据功能 ID 获取工作流程
        
        Args:
            feature_id: 功能 ID
            
        Returns:
            工作流程实例
        """
        for workflow in self._workflows.values():
            if workflow.feature_id == feature_id:
                return workflow

        # 尝试从文件查找
        for workflow_file in self.workflow_dir.glob("*.json"):
            try:
                workflow = self._load_workflow(workflow_file.stem)
                if workflow and workflow.feature_id == feature_id:
                    self._workflows[workflow.id] = workflow
                    return workflow
            except Exception as e:
                logger.warning(f"加载工作流程文件失败: {workflow_file}: {e}")

        return None

    def list_workflows(
        self,
        status: PhaseStatus | None = None,
        phase: WorkflowPhase | None = None,
    ) -> list[WorkflowInstance]:
        """
        列出工作流程
        
        Args:
            status: 过滤状态
            phase: 过滤当前阶段
            
        Returns:
            工作流程列表
        """
        workflows = list(self._workflows.values())

        # 加载所有工作流程文件
        for workflow_file in self.workflow_dir.glob("*.json"):
            workflow_id = workflow_file.stem
            if workflow_id not in self._workflows:
                workflow = self._load_workflow(workflow_id)
                if workflow:
                    self._workflows[workflow_id] = workflow
                    workflows.append(workflow)

        # 过滤
        if status:
            workflows = [
                w for w in workflows
                if w.get_phase_result(w.current_phase).status == status
            ]

        if phase:
            workflows = [w for w in workflows if w.current_phase == phase]

        # 按更新时间排序
        workflows.sort(key=lambda w: w.updated_at, reverse=True)

        return workflows

    async def execute_phase(
        self,
        workflow_id: str,
        phase: WorkflowPhase,
        params: dict[str, Any] | None = None,
    ) -> PhaseResult:
        """
        执行指定阶段
        
        Args:
            workflow_id: 工作流程 ID
            phase: 要执行的阶段
            params: 执行参数
            
        Returns:
            阶段执行结果
        """
        workflow = self.get_workflow(workflow_id)
        if not workflow:
            raise ValueError(f"工作流程不存在: {workflow_id}")

        result = workflow.get_phase_result(phase)
        result.mark_started()

        # 检查是否有注册的执行器
        executor = self._phase_executors.get(phase)
        if executor:
            try:
                output = await asyncio.to_thread(
                    executor, workflow, params or {}
                )

                # 处理执行结果
                if isinstance(output, dict):
                    workflow.complete_phase(
                        phase,
                        output=output.get("output", ""),
                        artifacts=output.get("artifacts"),
                    )
                else:
                    workflow.complete_phase(phase, output=str(output))

            except Exception as e:
                workflow.fail_phase(phase, str(e))
                logger.error(f"阶段执行失败: {phase.get_display_name()}: {e}")
                raise
        else:
            # 没有执行器，标记为需要手动完成
            logger.info(f"阶段 {phase.get_display_name()} 需要手动完成")

        self._save_workflow(workflow)
        return result

    def complete_phase_manually(
        self,
        workflow_id: str,
        phase: WorkflowPhase,
        output: str = "",
        artifacts: list[str] | None = None,
    ) -> bool:
        """
        手动完成阶段
        
        Args:
            workflow_id: 工作流程 ID
            phase: 阶段
            output: 输出信息
            artifacts: 产物文件列表
            
        Returns:
            是否成功
        """
        workflow = self.get_workflow(workflow_id)
        if not workflow:
            logger.error(f"工作流程不存在: {workflow_id}")
            return False

        success = workflow.complete_phase(phase, output, artifacts)
        if success:
            self._save_workflow(workflow)
        return success

    def fail_phase_manually(
        self,
        workflow_id: str,
        phase: WorkflowPhase,
        error: str,
    ) -> bool:
        """
        手动标记阶段失败
        
        Args:
            workflow_id: 工作流程 ID
            phase: 阶段
            error: 错误信息
            
        Returns:
            是否成功
        """
        workflow = self.get_workflow(workflow_id)
        if not workflow:
            logger.error(f"工作流程不存在: {workflow_id}")
            return False

        workflow.fail_phase(phase, error)
        self._save_workflow(workflow)
        return True

    def skip_phase(
        self,
        workflow_id: str,
        phase: WorkflowPhase,
        reason: str = "",
    ) -> bool:
        """
        跳过阶段
        
        Args:
            workflow_id: 工作流程 ID
            phase: 阶段
            reason: 跳过原因
            
        Returns:
            是否成功
        """
        workflow = self.get_workflow(workflow_id)
        if not workflow:
            logger.error(f"工作流程不存在: {workflow_id}")
            return False

        result = workflow.get_phase_result(phase)
        result.mark_skipped(reason)

        # 推进到下一阶段
        next_phase = phase.get_next()
        if next_phase:
            workflow.current_phase = next_phase

        self._save_workflow(workflow)
        return True

    def _save_workflow(self, workflow: WorkflowInstance) -> None:
        """保存工作流程到文件"""
        import json

        try:
            file_path = self.workflow_dir / f"{workflow.id}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(workflow.to_dict(), f, ensure_ascii=False, indent=2)
            logger.debug(f"工作流程已保存: {file_path}")
        except Exception as e:
            logger.error(f"保存工作流程失败: {e}")
            raise

    def _load_workflow(self, workflow_id: str) -> WorkflowInstance | None:
        """从文件加载工作流程"""
        import json

        file_path = self.workflow_dir / f"{workflow_id}.json"
        if not file_path.exists():
            return None

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            return WorkflowInstance.from_dict(data)
        except Exception as e:
            logger.error(f"加载工作流程失败: {workflow_id}: {e}")
            return None

    def delete_workflow(self, workflow_id: str) -> bool:
        """
        删除工作流程
        
        Args:
            workflow_id: 工作流程 ID
            
        Returns:
            是否成功
        """
        # 从内存删除
        if workflow_id in self._workflows:
            del self._workflows[workflow_id]

        # 删除文件
        file_path = self.workflow_dir / f"{workflow_id}.json"
        if file_path.exists():
            try:
                file_path.unlink()
                logger.info(f"工作流程已删除: {workflow_id}")
                return True
            except Exception as e:
                logger.error(f"删除工作流程文件失败: {e}")
                return False

        return True

    def get_statistics(self) -> dict[str, Any]:
        """
        获取工作流程统计信息
        
        Returns:
            统计信息字典
        """
        workflows = self.list_workflows()

        stats = {
            "total": len(workflows),
            "by_phase": {},
            "by_status": {},
        }

        for phase in WorkflowPhase.get_order():
            stats["by_phase"][phase.value] = len([
                w for w in workflows if w.current_phase == phase
            ])

        for status in PhaseStatus:
            stats["by_status"][status.value] = len([
                w for w in workflows
                if w.get_phase_result(w.current_phase).status == status
            ])

        return stats

    def get_context_for_prompt(self, workflow_id: str | None = None) -> str:
        """
        获取用于注入系统提示词的上下文
        
        Args:
            workflow_id: 工作流程 ID，为 None 则获取当前活动的工作流程
            
        Returns:
            格式化的上下文文本
        """
        workflow = None
        if workflow_id:
            workflow = self.get_workflow(workflow_id)
        else:
            # 获取最近的活动工作流程
            workflows = self.list_workflows()
            in_progress = [
                w for w in workflows
                if w.get_phase_result(w.current_phase).status == PhaseStatus.IN_PROGRESS
            ]
            if in_progress:
                workflow = in_progress[0]

        if not workflow:
            return "当前没有活动的工作流程"

        progress = workflow.get_progress()
        lines = [
            "## 当前工作流程",
            "",
            f"- **工作流程 ID**: {workflow.id}",
            f"- **关联功能**: {workflow.feature_id}",
            f"- **当前阶段**: {progress['current_phase_display']}",
            f"- **进度**: {progress['progress_percent']}% ({progress['completed_phases']}/{progress['total_phases']})",
            f"- **分支**: {workflow.branch_name or '未创建'}",
            "",
        ]

        # 显示当前阶段详情
        current_result = workflow.get_phase_result(workflow.current_phase)
        lines.append("### 当前阶段状态")
        lines.append(f"- 状态: {current_result.status.value}")
        if current_result.output:
            lines.append(f"- 输出: {current_result.output[:100]}...")
        if current_result.error:
            lines.append(f"- 错误: {current_result.error}")

        return "\n".join(lines)


# ==================== 默认阶段执行器 ====================

def create_default_design_executor() -> Callable:
    """
    创建默认的设计规划阶段执行器
    
    该阶段通常需要人工参与，执行器仅提供指导
    """
    def executor(workflow: WorkflowInstance, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "output": "设计规划阶段需要人工参与，请完成设计文档后手动标记完成",
            "artifacts": [],
        }
    return executor


def create_default_coding_executor() -> Callable:
    """
    创建默认的编码阶段执行器
    
    该阶段由 AI 代理执行编码任务
    """
    def executor(workflow: WorkflowInstance, params: dict[str, Any]) -> dict[str, Any]:
        # 编码阶段通常由 Agent 直接执行
        return {
            "output": "编码阶段由 AI 代理执行",
            "artifacts": [],
        }
    return executor


def create_default_test_executor(test_command: str = "pytest") -> Callable:
    """
    创建默认的测试阶段执行器
    
    Args:
        test_command: 测试命令
    """
    def executor(workflow: WorkflowInstance, params: dict[str, Any]) -> dict[str, Any]:
        import subprocess

        try:
            result = subprocess.run(
                test_command.split(),
                cwd=workflow.metadata.get("working_dir", "."),
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode == 0:
                return {
                    "output": result.stdout,
                    "artifacts": [],
                }
            else:
                raise Exception(f"测试失败: {result.stderr}")

        except subprocess.TimeoutExpired:
            raise Exception("测试执行超时")
        except Exception as e:
            raise Exception(f"测试执行错误: {e}")

    return executor


def create_default_merge_executor(
    main_branch: str = "main",
    remote: str = "origin",
) -> Callable:
    """
    创建默认的合并阶段执行器
    
    Args:
        main_branch: 主分支名称
        remote: 远程仓库名称
    """
    def executor(workflow: WorkflowInstance, params: dict[str, Any]) -> dict[str, Any]:
        import subprocess

        working_dir = workflow.metadata.get("working_dir", ".")

        try:
            # 拉取最新主分支
            subprocess.run(
                ["git", "fetch", remote, main_branch],
                cwd=working_dir,
                capture_output=True,
                check=True,
            )

            # 合并主分支
            subprocess.run(
                ["git", "merge", f"{remote}/{main_branch}"],
                cwd=working_dir,
                capture_output=True,
                check=True,
            )

            return {
                "output": f"成功合并 {remote}/{main_branch}",
                "artifacts": [],
            }

        except subprocess.CalledProcessError as e:
            raise Exception(f"合并失败: {e.stderr}")

    return executor


def create_default_push_executor(remote: str = "origin") -> Callable:
    """
    创建默认的推送阶段执行器
    
    Args:
        remote: 远程仓库名称
    """
    def executor(workflow: WorkflowInstance, params: dict[str, Any]) -> dict[str, Any]:
        import subprocess

        working_dir = workflow.metadata.get("working_dir", ".")
        branch = workflow.branch_name

        if not branch:
            raise Exception("未设置工作分支名称")

        try:
            subprocess.run(
                ["git", "push", remote, branch],
                cwd=working_dir,
                capture_output=True,
                check=True,
            )

            return {
                "output": f"成功推送分支 {branch} 到 {remote}",
                "artifacts": [],
            }

        except subprocess.CalledProcessError as e:
            raise Exception(f"推送失败: {e.stderr}")

    return executor


def create_default_evaluation_executor() -> Callable:
    """
    创建默认的评估阶段执行器
    
    该阶段由 EvaluatorAgent 执行代码和设计质量评估。
    支持三种评估类型：
    - code_quality: 仅评估代码质量
    - design_quality: 仅评估设计质量
    - full: 完整评估（代码和设计）
    
    Returns:
        评估阶段执行器函数
    """
    def executor(workflow: WorkflowInstance, params: dict[str, Any]) -> dict[str, Any]:
        from foxcode.core.evaluator import EvaluatorAgent

        # 获取评估参数
        code_content = params.get("code_content", "")
        design_doc = params.get("design_doc", "")
        evaluation_type = params.get("evaluation_type", "full")

        # 获取评估标准配置
        criteria = workflow.metadata.get("evaluator_criteria")

        # 创建评估器实例
        evaluator = EvaluatorAgent(
            passing_threshold=criteria.passing_threshold if criteria else 7.0,
        )

        # 定义异步评估执行函数
        async def run_evaluation() -> Any:
            """
            执行异步评估
            
            根据评估类型调用相应的评估方法
            """
            if evaluation_type == "code_quality":
                # 仅评估代码质量
                logger.info("执行代码质量评估")
                return await evaluator.evaluate_code(code_content)
            elif evaluation_type == "design_quality":
                # 仅评估设计质量
                logger.info("执行设计质量评估")
                return await evaluator.evaluate_design(design_doc)
            else:
                # 完整评估（代码和设计）
                logger.info("执行完整质量评估")
                return await evaluator.evaluate_full(code_content, design_doc)

        try:
            # 运行评估
            logger.info(f"开始评估阶段，类型: {evaluation_type}")
            report = asyncio.run(run_evaluation())

            # 检查评估是否通过
            if report.passed:
                logger.info(f"评估通过，总分: {report.total_score:.1f}/10")
                return {
                    "output": f"评估通过，总分: {report.total_score:.1f}/10",
                    "artifacts": [],
                    "evaluation_report": report.to_dict(),
                }
            else:
                # 评估未通过，返回到编码阶段进行改进
                recommendations = ", ".join(report.recommendations[:3]) if report.recommendations else "无具体建议"
                logger.warning(f"评估未通过，总分: {report.total_score:.1f}/10。需要改进: {recommendations}")
                return {
                    "output": f"评估未通过，总分: {report.total_score:.1f}/10。需要改进: {recommendations}",
                    "artifacts": [],
                    "evaluation_report": report.to_dict(),
                    "needs_revision": True,  # 标记需要返回编码阶段
                }

        except ImportError as e:
            # EvaluatorAgent 模块导入失败
            error_msg = f"评估器模块导入失败: {e}"
            logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            # 评估过程发生错误
            error_msg = f"评估执行错误: {e}"
            logger.error(error_msg)
            raise Exception(error_msg)

    return executor


# ==================== 便捷函数 ====================

def create_workflow_manager(
    working_dir: Path | str,
    workflow_dir: str | None = None,
) -> WorkflowManager:
    """
    创建工作流程管理器的便捷函数
    
    Args:
        working_dir: 工作目录
        workflow_dir: 工作流程存储目录
        
    Returns:
        工作流程管理器实例
    """
    manager = WorkflowManager(
        working_dir=Path(working_dir),
        workflow_dir=workflow_dir,
    )

    # 注册默认执行器
    manager.register_phase_executor(
        WorkflowPhase.EVALUATION,  # 新增评估阶段执行器
        create_default_evaluation_executor(),
    )
    manager.register_phase_executor(
        WorkflowPhase.LOCAL_TEST,
        create_default_test_executor(),
    )
    manager.register_phase_executor(
        WorkflowPhase.INTEGRATION_TEST,
        create_default_test_executor(),
    )
    manager.register_phase_executor(
        WorkflowPhase.MERGE_MAIN,
        create_default_merge_executor(),
    )
    manager.register_phase_executor(
        WorkflowPhase.PUSH,
        create_default_push_executor(),
    )

    return manager
