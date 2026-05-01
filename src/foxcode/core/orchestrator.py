"""
FoxCode 多代理协调器模块 - 规划器-生成器-评估器协作系统

这个文件实现了FoxCode的多代理协作模式，通过三个专业代理协作完成复杂任务：
1. 规划器（PLANNER）：分解任务、制定计划、生成验收标准
2. 生成器（GENERATOR）：执行具体编码任务、实现功能
3. 评估器（EVALUATOR）：独立评估工作质量、提供反馈

为什么需要多代理协作？
1. 单个AI容易陷入局部最优
2. 不同角色专注不同任务，提高质量
3. 评估器独立审查，减少错误
4. 模拟人类团队的协作模式

工作流程：
用户需求 -> 规划器分解任务 -> 生成器执行 -> 评估器评估 -> 反馈修订 -> 完成

使用方式：
    from foxcode.core.orchestrator import MultiAgentOrchestrator
    
    orchestrator = MultiAgentOrchestrator(config)
    result = await orchestrator.execute_workflow(user_request)

关键特性：
- 自动任务分解和分配
- 独立质量评估
- 迭代修订机制
- 代理间通信和协作
- 上下文管理和重置
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from foxcode.core.config import AgentRole, Config
from foxcode.core.context_reset import ContextResetManager, ResetTrigger
from foxcode.core.evaluator import EvaluationReport, EvaluatorAgent
from foxcode.core.handoff import HandoffArtifact, TaskItem

if TYPE_CHECKING:
    from foxcode.core.session import Session

logger = logging.getLogger(__name__)


class OrchestratorState(str, Enum):
    """
    协调器状态枚举
    
    定义协调器在多代理协作过程中的各种状态，用于追踪和管理工作流程。
    
    Attributes:
        IDLE: 空闲状态 - 协调器未执行任何任务
        PLANNING: 规划中 - 规划器代理正在分解任务
        GENERATING: 生成中 - 生成器代理正在执行编码任务
        EVALUATING: 评估中 - 评估器代理正在评估工作质量
        REVISION: 修订中 - 根据评估反馈进行修订
        COMPLETED: 已完成 - 所有任务已完成
        ERROR: 错误状态 - 执行过程中发生错误
    """
    IDLE = "idle"
    PLANNING = "planning"
    GENERATING = "generating"
    EVALUATING = "evaluating"
    REVISION = "revision"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class AgentMessage:
    """
    代理间消息数据类
    
    用于在多代理系统中传递消息，支持不同类型的消息传递，
    如任务分配、结果反馈、状态通知等。
    
    Attributes:
        from_role: 发送者角色
        to_role: 接收者角色
        content: 消息内容
        message_type: 消息类型 (info, task, result, feedback)
        timestamp: 消息时间戳
        metadata: 额外元数据
    """
    from_role: AgentRole
    to_role: AgentRole
    content: str
    message_type: str = "info"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """
        将消息转换为字典格式
        
        Returns:
            包含所有消息属性的字典
        """
        return {
            "from_role": self.from_role.value,
            "to_role": self.to_role.value,
            "content": self.content,
            "message_type": self.message_type,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class TaskResult:
    """
    任务执行结果数据类
    
    记录单个任务的执行结果，包括成功状态、输出内容、
    评估报告和修订信息等。
    
    Attributes:
        task_id: 任务唯一标识符
        success: 任务是否成功完成
        output: 任务输出内容
        artifacts: 产物文件列表
        evaluation_report: 评估报告（如果执行了评估）
        error: 错误信息（如果任务失败）
        needs_revision: 是否需要修订
        revision_count: 修订次数
    """
    task_id: str
    success: bool
    output: str = ""
    artifacts: list[str] = field(default_factory=list)
    evaluation_report: EvaluationReport | None = None
    error: str | None = None
    needs_revision: bool = False
    revision_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """
        将结果转换为字典格式
        
        Returns:
            包含所有结果属性的字典
        """
        return {
            "task_id": self.task_id,
            "success": self.success,
            "output": self.output,
            "artifacts": self.artifacts,
            "evaluation_report": self.evaluation_report.to_dict() if self.evaluation_report else None,
            "error": self.error,
            "needs_revision": self.needs_revision,
            "revision_count": self.revision_count,
        }


class MultiAgentOrchestrator:
    """
    多代理协调器
    
    管理规划器-生成器-评估器三代理协作模式，实现以下工作流程：
    
    1. 规划器（PLANNER）：分解任务、生成可验证的完成标准
    2. 生成器（GENERATOR）：执行具体编码任务
    3. 评估器（EVALUATOR）：独立评估工作质量，提供反馈
    
    支持功能：
    - 代理角色切换和状态管理
    - 任务分配和结果收集
    - 生成-评估循环（支持多次修订）
    - 上下文重置和状态恢复
    - 代理间消息传递
    
    Attributes:
        config: 配置实例
        session: 会话实例
        max_revisions: 最大修订次数
        state: 当前协调器状态
        current_role: 当前代理角色
    """

    DEFAULT_MAX_REVISIONS = 3

    def __init__(
        self,
        config: Config,
        session: Session,
        max_revisions: int = DEFAULT_MAX_REVISIONS,
    ):
        """
        初始化多代理协调器
        
        Args:
            config: 配置实例，包含评估器标准等配置项
            session: 会话实例，用于状态持久化和上下文管理
            max_revisions: 最大修订次数，默认为 3
            
        Raises:
            ValueError: 当 max_revisions 小于 0 时
        """
        # 参数验证
        if max_revisions < 0:
            raise ValueError("最大修订次数不能为负数")

        self.config = config
        self.session = session
        self.max_revisions = max_revisions

        # 状态管理
        self._state = OrchestratorState.IDLE
        self._current_role = AgentRole.PLANNER

        # 任务管理
        self._tasks: list[TaskItem] = []
        self._current_task: TaskItem | None = None
        self._task_results: dict[str, TaskResult] = {}

        # 消息队列
        self._message_queue: list[AgentMessage] = []

        # 评估器（延迟初始化）
        self._evaluator: EvaluatorAgent | None = None

        # 上下文重置管理器（延迟初始化）
        self._context_reset_manager: ContextResetManager | None = None

        # 统计信息
        self._stats = {
            "tasks_planned": 0,
            "tasks_completed": 0,
            "tasks_revised": 0,
            "evaluations_passed": 0,
            "evaluations_failed": 0,
        }

        logger.info(
            f"多代理协调器初始化完成 - "
            f"最大修订次数: {max_revisions}, "
            f"初始角色: {self._current_role.value}"
        )

    @property
    def state(self) -> OrchestratorState:
        """
        获取当前协调器状态
        
        Returns:
            当前状态枚举值
        """
        return self._state

    @property
    def current_role(self) -> AgentRole:
        """
        获取当前代理角色
        
        Returns:
            当前代理角色枚举值
        """
        return self._current_role

    def get_evaluator(self) -> EvaluatorAgent:
        """
        获取评估器实例
        
        延迟初始化评估器代理，根据配置中的评估标准创建实例。
        
        Returns:
            EvaluatorAgent: 评估器代理实例
        """
        if self._evaluator is None:
            criteria = self.config.long_running.evaluator_criteria
            self._evaluator = EvaluatorAgent(
                passing_threshold=criteria.passing_threshold,
                code_weights={
                    "correctness": criteria.code_correctness_weight,
                    "test_coverage": criteria.test_coverage_weight,
                    "code_style": criteria.code_style_weight,
                    "error_handling": criteria.error_handling_weight,
                },
                design_weights={
                    "requirements": criteria.design_requirements_weight,
                    "architecture": criteria.architecture_weight,
                    "extensibility": criteria.extensibility_weight,
                    "documentation": criteria.documentation_weight,
                },
            )
            logger.debug(f"评估器已初始化，通过阈值: {criteria.passing_threshold}")

        return self._evaluator

    def get_context_reset_manager(self) -> ContextResetManager:
        """
        获取上下文重置管理器实例
        
        延迟初始化上下文重置管理器，用于管理上下文窗口使用情况。
        
        Returns:
            ContextResetManager: 上下文重置管理器实例
        """
        if self._context_reset_manager is None:
            self._context_reset_manager = ContextResetManager(config=self.config)
            logger.debug("上下文重置管理器已初始化")

        return self._context_reset_manager

    # ==================== 角色切换 ====================

    def switch_role(self, new_role: AgentRole) -> None:
        """
        切换代理角色
        
        将当前代理角色切换为指定的新角色，并通知会话进行相应的状态更新。
        同时发送角色切换消息到消息队列。
        
        Args:
            new_role: 新的代理角色
            
        Example:
            >>> orchestrator.switch_role(AgentRole.GENERATOR)
            >>> print(orchestrator.current_role)  # AgentRole.GENERATOR
        """
        old_role = self._current_role
        self._current_role = new_role

        # 通知会话切换角色
        try:
            self.session.switch_agent_role(new_role)
        except Exception as e:
            logger.warning(f"通知会话切换角色失败: {e}")

        logger.info(f"代理角色切换: {old_role.value} -> {new_role.value}")

        # 发送角色切换消息
        self._add_message(AgentMessage(
            from_role=old_role,
            to_role=new_role,
            content=f"角色切换: {old_role.value} -> {new_role.value}",
            message_type="info",
        ))

    # ==================== 任务管理 ====================

    def set_tasks(self, tasks: list[TaskItem]) -> None:
        """
        设置任务列表
        
        设置协调器要处理的任务列表，并更新统计信息。
        
        Args:
            tasks: 任务列表
            
        Raises:
            ValueError: 当任务列表为空时
        """
        if not tasks:
            raise ValueError("任务列表不能为空")

        self._tasks = list(tasks)  # 创建副本以避免外部修改
        self._stats["tasks_planned"] = len(tasks)

        logger.info(f"已设置 {len(tasks)} 个任务")

        # 记录任务详情
        for i, task in enumerate(self._tasks[:5], 1):
            logger.debug(f"  任务 {i}: [{task.id}] {task.title}")
        if len(self._tasks) > 5:
            logger.debug(f"  ... 共 {len(self._tasks)} 个任务")

    def get_next_task(self) -> TaskItem | None:
        """
        获取下一个待处理任务
        
        从任务列表中查找并返回第一个状态为 pending 的任务。
        
        Returns:
            下一个待处理任务，如果没有则返回 None
        """
        for task in self._tasks:
            if task.status == "pending":
                return task
        return None

    def get_task_by_id(self, task_id: str) -> TaskItem | None:
        """
        根据 ID 获取任务
        
        Args:
            task_id: 任务唯一标识符
            
        Returns:
            任务实例，如果未找到则返回 None
        """
        for task in self._tasks:
            if task.id == task_id:
                return task
        return None

    def start_task(self, task: TaskItem) -> None:
        """
        开始执行任务
        
        将任务状态设置为 in_progress，并切换到生成器角色开始执行。
        
        Args:
            task: 要开始的任务实例
        """
        task.status = "in_progress"
        self._current_task = task
        self._state = OrchestratorState.GENERATING
        self.switch_role(AgentRole.GENERATOR)

        logger.info(f"开始执行任务: {task.id} - {task.title}")

        # 发送任务开始消息
        self._add_message(AgentMessage(
            from_role=AgentRole.PLANNER,
            to_role=AgentRole.GENERATOR,
            content=f"开始执行任务: {task.title}\n描述: {task.description}",
            message_type="task",
            metadata={"task_id": task.id},
        ))

    def complete_task(self, task: TaskItem, result: TaskResult) -> None:
        """
        完成任务
        
        根据任务结果更新任务状态和统计信息。
        
        Args:
            task: 任务实例
            result: 任务执行结果
        """
        if result.success and not result.needs_revision:
            task.status = "completed"
            self._stats["tasks_completed"] += 1
            logger.info(f"任务完成: {task.id} - {task.title}")
        else:
            task.status = "needs_revision"
            logger.warning(
                f"任务需要修订: {task.id}, "
                f"原因: {result.error or '评估未通过'}"
            )

        # 保存结果
        self._task_results[task.id] = result

        # 检查是否所有任务都已完成
        pending_count = len([t for t in self._tasks if t.status in ("pending", "in_progress")])
        if pending_count == 0:
            self._state = OrchestratorState.COMPLETED
            logger.info("所有任务已完成")

        self._current_task = None

    def fail_task(self, task: TaskItem, error: str) -> None:
        """
        标记任务失败
        
        将任务标记为失败状态，并记录错误信息。
        
        Args:
            task: 任务实例
            error: 错误信息
        """
        task.status = "failed"
        task.notes = f"错误: {error}"

        # 创建失败结果
        result = TaskResult(
            task_id=task.id,
            success=False,
            error=error,
        )
        self._task_results[task.id] = result

        logger.error(f"任务失败: {task.id} - {error}")
        self._current_task = None

    # ==================== 评估流程 ====================

    async def evaluate_task(
        self,
        task: TaskItem,
        code_content: str,
        design_doc: str = "",
    ) -> EvaluationReport:
        """
        评估任务产物
        
        使用评估器代理对任务的代码产物进行质量评估。
        
        Args:
            task: 任务实例
            code_content: 代码内容字符串
            design_doc: 设计文档内容（可选）
            
        Returns:
            EvaluationReport: 评估报告
            
        Raises:
            ValueError: 当代码内容为空时
        """
        if not code_content or not code_content.strip():
            raise ValueError("代码内容不能为空")

        self._state = OrchestratorState.EVALUATING
        self.switch_role(AgentRole.EVALUATOR)

        evaluator = self.get_evaluator()

        try:
            # 执行完整评估
            if design_doc:
                report = await evaluator.evaluate_full(
                    code_content=code_content,
                    design_doc=design_doc,
                )
            else:
                report = await evaluator.evaluate_code(
                    code_content=code_content,
                )

            # 更新统计
            if report.passed:
                self._stats["evaluations_passed"] += 1
            else:
                self._stats["evaluations_failed"] += 1

            logger.info(
                f"任务 {task.id} 评估完成: "
                f"{'通过' if report.passed else '未通过'}, "
                f"总分: {report.total_score:.1f}/10"
            )

            return report

        except Exception as e:
            logger.error(f"评估任务 {task.id} 时发生错误: {e}")
            self._stats["evaluations_failed"] += 1
            raise

    async def run_generation_evaluation_cycle(
        self,
        task: TaskItem,
        generator_func: Callable[[TaskItem], Awaitable[str]],
        code_extractor: Callable[[str], str],
        design_doc: str = "",
    ) -> TaskResult:
        """
        运行生成-评估循环
        
        执行完整的生成-评估-修订循环，直到任务通过评估或达到最大修订次数。
        
        工作流程：
        1. 调用生成器函数生成代码
        2. 提取代码内容
        3. 执行评估
        4. 如果未通过，根据反馈进行修订
        5. 重复直到通过或达到最大修订次数
        
        Args:
            task: 任务实例
            generator_func: 异步生成器函数，接收任务并返回输出
            code_extractor: 代码提取函数，从输出中提取代码
            design_doc: 设计文档内容（可选）
            
        Returns:
            TaskResult: 任务执行结果
        """
        revision_count = 0
        last_error = None
        last_output = ""

        while revision_count < self.max_revisions:
            try:
                # 生成阶段
                self._state = OrchestratorState.GENERATING
                self.switch_role(AgentRole.GENERATOR)

                logger.info(
                    f"开始生成 (尝试 {revision_count + 1}/{self.max_revisions}): "
                    f"{task.id}"
                )

                # 执行生成
                output = await generator_func(task)
                last_output = output
                code_content = code_extractor(output)

                if not code_content:
                    raise ValueError("无法从输出中提取代码内容")

                # 评估阶段
                report = await self.evaluate_task(
                    task=task,
                    code_content=code_content,
                    design_doc=design_doc,
                )

                if report.passed:
                    logger.info(f"任务 {task.id} 通过评估")
                    return TaskResult(
                        task_id=task.id,
                        success=True,
                        output=output,
                        evaluation_report=report,
                    )

                # 评估未通过，准备修订
                revision_count += 1
                self._stats["tasks_revised"] += 1
                self._state = OrchestratorState.REVISION

                # 发送反馈给生成器
                feedback = self._create_feedback_message(report, revision_count)
                self._add_message(feedback)

                last_error = (
                    f"评估未通过，总分: {report.total_score:.1f}/10, "
                    f"阈值: {report.threshold}"
                )

                logger.warning(
                    f"任务 {task.id} 评估未通过，准备修订 "
                    f"({revision_count}/{self.max_revisions})"
                )

            except Exception as e:
                logger.error(f"生成-评估循环出错: {e}")
                last_error = str(e)
                revision_count += 1

                # 如果是最后一次尝试，不再继续
                if revision_count >= self.max_revisions:
                    break

        # 达到最大修订次数仍未通过
        logger.error(
            f"任务 {task.id} 达到最大修订次数 ({self.max_revisions}) 仍未通过"
        )

        return TaskResult(
            task_id=task.id,
            success=False,
            output=last_output,
            error=last_error or "达到最大修订次数仍未通过评估",
            needs_revision=True,
            revision_count=revision_count,
        )

    def _create_feedback_message(
        self,
        report: EvaluationReport,
        revision_count: int = 0,
    ) -> AgentMessage:
        """
        创建评估反馈消息
        
        根据评估报告生成反馈消息，用于指导生成器进行修订。
        
        Args:
            report: 评估报告
            revision_count: 当前修订次数
            
        Returns:
            AgentMessage: 反馈消息
        """
        recommendations = "\n".join(
            f"- {r}" for r in report.recommendations[:5]
        )

        content = f"""
## 评估结果

- **状态**: {'✅ 通过' if report.passed else '❌ 未通过'}
- **总分**: {report.total_score:.1f}/10
- **阈值**: {report.threshold}
- **修订次数**: {revision_count}/{self.max_revisions}

## 详细评分

"""
        for score in report.scores:
            status = "✅" if score.score >= report.threshold else "❌"
            content += f"- {status} **{score.category}**: {score.score:.1f}/10\n"
            if score.comments:
                content += f"  - {score.comments}\n"

        if report.recommendations:
            content += f"\n## 改进建议\n\n{recommendations}\n"

        return AgentMessage(
            from_role=AgentRole.EVALUATOR,
            to_role=AgentRole.GENERATOR,
            content=content,
            message_type="feedback",
            metadata={
                "evaluation_report": report.to_dict(),
                "revision_count": revision_count,
            },
        )

    def _add_message(self, message: AgentMessage) -> None:
        """
        添加消息到队列
        
        将消息添加到消息队列，用于代理间通信。
        
        Args:
            message: 要添加的消息
        """
        self._message_queue.append(message)
        logger.debug(
            f"消息已添加: {message.from_role.value} -> {message.to_role.value} "
            f"[{message.message_type}]"
        )

    def get_messages(self, to_role: AgentRole | None = None) -> list[AgentMessage]:
        """
        获取消息
        
        从消息队列中获取消息，可以按接收者角色过滤。
        
        Args:
            to_role: 接收者角色，None 则获取所有消息
            
        Returns:
            消息列表
        """
        if to_role is None:
            return list(self._message_queue)

        return [m for m in self._message_queue if m.to_role == to_role]

    def clear_messages(self) -> int:
        """
        清空消息队列
        
        Returns:
            清空前的消息数量
        """
        count = len(self._message_queue)
        self._message_queue.clear()
        logger.debug(f"已清空 {count} 条消息")
        return count

    # ==================== 上下文重置 ====================

    async def check_and_reset_context(self) -> bool:
        """
        检查并执行上下文重置
        
        检查当前上下文使用率，如果超过阈值则执行重置操作。
        
        Returns:
            是否执行了重置
        """
        manager = self.get_context_reset_manager()
        usage = self.session.get_context_usage()

        needs_reset, reason = manager.check_reset_needed(
            usage.used_tokens,
            usage.max_tokens,
        )

        if needs_reset:
            logger.warning(f"触发上下文重置: {reason}")

            try:
                # 创建 HandoffArtifact
                result = self.session.reset_context(
                    trigger=ResetTrigger.AUTO_THRESHOLD,
                    current_task=self._current_task,
                    pending_tasks=[t for t in self._tasks if t.status == "pending"],
                    completed_tasks=[t for t in self._tasks if t.status == "completed"],
                    context_summary=f"协调器状态: {self._state.value}",
                )

                if result.success:
                    logger.info(
                        f"上下文重置成功 - "
                        f"旧会话: {result.old_session_id}, "
                        f"新会话: {result.new_session_id}"
                    )
                    return True
                else:
                    logger.error(f"上下文重置失败: {result.error}")
                    return False

            except Exception as e:
                logger.error(f"上下文重置过程中发生错误: {e}")
                return False

        return False

    # ==================== 状态管理 ====================

    def create_handoff(self) -> HandoffArtifact:
        """
        创建当前状态的 HandoffArtifact
        
        将协调器的当前状态序列化为 HandoffArtifact，用于会话切换或状态恢复。
        
        Returns:
            HandoffArtifact: 包含当前状态的 HandoffArtifact 实例
        """
        artifact = HandoffArtifact(
            session_id=self.session.session_id,
            agent_role=self._current_role,
            current_task=self._current_task,
            pending_tasks=[t for t in self._tasks if t.status == "pending"],
            completed_tasks=[t for t in self._tasks if t.status == "completed"],
            metadata={
                "orchestrator_state": self._state.value,
                "stats": self._stats.copy(),
                "message_count": len(self._message_queue),
            },
            working_directory=str(self.config.working_dir),
        )

        logger.info(f"已创建 HandoffArtifact: {artifact.session_id}")
        return artifact

    def restore_from_handoff(self, artifact: HandoffArtifact) -> None:
        """
        从 HandoffArtifact 恢复状态
        
        将 HandoffArtifact 中的状态信息恢复到协调器中。
        
        Args:
            artifact: HandoffArtifact 实例
        """
        # 恢复角色
        self._current_role = artifact.agent_role

        # 恢复任务
        self._current_task = artifact.current_task
        self._tasks = artifact.pending_tasks + artifact.completed_tasks

        # 恢复统计信息
        if "stats" in artifact.metadata:
            self._stats.update(artifact.metadata["stats"])

        # 恢复会话状态
        try:
            self.session.restore_from_artifact(artifact)
        except Exception as e:
            logger.warning(f"恢复会话状态失败: {e}")

        logger.info(
            f"已从 HandoffArtifact 恢复协调器状态 - "
            f"角色: {self._current_role.value}, "
            f"任务数: {len(self._tasks)}"
        )

    def get_statistics(self) -> dict[str, Any]:
        """
        获取统计信息
        
        返回协调器的运行统计信息，包括任务完成情况、评估结果等。
        
        Returns:
            统计信息字典
        """
        return {
            **self._stats,
            "state": self._state.value,
            "current_role": self._current_role.value,
            "total_tasks": len(self._tasks),
            "pending_tasks": len([t for t in self._tasks if t.status == "pending"]),
            "in_progress_tasks": len([t for t in self._tasks if t.status == "in_progress"]),
            "completed_tasks": len([t for t in self._tasks if t.status == "completed"]),
            "failed_tasks": len([t for t in self._tasks if t.status == "failed"]),
            "message_count": len(self._message_queue),
            "max_revisions": self.max_revisions,
        }

    def reset(self) -> None:
        """
        重置协调器状态
        
        清空所有任务、消息和统计信息，将协调器恢复到初始状态。
        """
        self._state = OrchestratorState.IDLE
        self._current_role = AgentRole.PLANNER
        self._tasks.clear()
        self._current_task = None
        self._task_results.clear()
        self._message_queue.clear()
        self._stats = {
            "tasks_planned": 0,
            "tasks_completed": 0,
            "tasks_revised": 0,
            "evaluations_passed": 0,
            "evaluations_failed": 0,
        }

        logger.info("协调器已重置")

    def get_progress_summary(self) -> str:
        """
        获取进度摘要
        
        生成简短的进度描述，包括任务完成情况和当前状态。
        
        Returns:
            进度摘要文本
        """
        completed = len([t for t in self._tasks if t.status == "completed"])
        total = len(self._tasks)

        if total == 0:
            return "无任务"

        progress = (completed / total) * 100

        summary = (
            f"进度: {completed}/{total} ({progress:.0f}%) | "
            f"状态: {self._state.value} | "
            f"角色: {self._current_role.value}"
        )

        if self._current_task:
            summary += f" | 当前: {self._current_task.title}"

        return summary


def create_multi_agent_orchestrator(
    config: Config,
    session: Session,
    max_revisions: int = 3,
) -> MultiAgentOrchestrator:
    """
    创建多代理协调器的便捷函数
    
    提供一种简洁的方式来创建 MultiAgentOrchestrator 实例。
    
    Args:
        config: 配置实例
        session: 会话实例
        max_revisions: 最大修订次数，默认为 3
        
    Returns:
        MultiAgentOrchestrator: 多代理协调器实例
        
    Example:
        >>> from foxcode.core.config import Config
        >>> from foxcode.core.session import Session
        >>> config = Config.create()
        >>> session = Session(config)
        >>> orchestrator = create_multi_agent_orchestrator(config, session)
    """
    return MultiAgentOrchestrator(
        config=config,
        session=session,
        max_revisions=max_revisions,
    )
