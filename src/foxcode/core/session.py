"""
FoxCode 会话管理模块

管理用户会话的持久化和恢复
支持进度追踪和跨会话上下文传递
支持会话数据加密存储
"""

from __future__ import annotations

import json
import logging
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any, TYPE_CHECKING

from foxcode.core.config import Config, AgentRole
from foxcode.core.message import Conversation, Message, MessageRole

if TYPE_CHECKING:
    from foxcode.core.progress import ProgressManager
    from foxcode.core.feature_list import FeatureList
    from foxcode.core.context_bridge import ContextBridge, SessionType
    from foxcode.core.workflow import WorkflowManager, WorkflowInstance
    from foxcode.core.context_reset import ContextResetManager, ResetTrigger, ContextUsageInfo, ResetResult
    from foxcode.core.handoff import HandoffArtifact, TaskItem

logger = logging.getLogger(__name__)


class Session:
    """
    会话管理类
    
    负责会话的创建、保存、加载和管理
    支持进度追踪和跨会话上下文传递
    """
    
    def __init__(self, config: Config, session_id: str | None = None):
        """
        初始化会话
        
        Args:
            config: 配置实例
            session_id: 会话 ID，如果为 None 则创建新会话
        """
        self.config = config
        self.session_id = session_id or self._generate_session_id()
        self.conversation = Conversation()
        self.metadata: dict[str, Any] = {
            "working_dir": str(config.working_dir),
            "created_at": datetime.now().isoformat(),
        }
        
        # 进度追踪相关属性
        self._progress_manager: "ProgressManager | None" = None
        self._feature_list: "FeatureList | None" = None
        self._context_bridge: "ContextBridge | None" = None
        self._session_type: "SessionType | None" = None
        self._workflow_manager: "WorkflowManager | None" = None
        self._current_workflow: "WorkflowInstance | None" = None
        
        # 上下文重置相关属性
        self._context_reset_manager: "ContextResetManager | None" = None
        self._agent_role: AgentRole = AgentRole.GENERATOR
        
        # 确保目录存在
        config.ensure_directories()
    
    @staticmethod
    def _generate_session_id() -> str:
        """
        生成安全的会话 ID
        
        使用加密安全的随机数生成器创建会话 ID，
        格式为: YYYYMMDD_HHMMSS_<32字节随机十六进制>
        
        安全说明：
        - 使用 16 字节（128 位）的随机数，提供足够的安全性
        - 使用 secrets.token_hex() 生成加密安全的随机数
        - 会话 ID 难以被猜测或预测
        
        Returns:
            格式化的会话 ID 字符串
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 使用 16 字节（128 位）随机数，生成 32 字符的十六进制字符串
        random_suffix = secrets.token_hex(16)
        return f"{timestamp}_{random_suffix}"
    
    @property
    def session_path(self) -> Path:
        """获取会话文件路径"""
        return self.config.get_session_path(self.session_id)
    
    def add_message(self, message: Message) -> None:
        """
        添加消息到会话
        
        Args:
            message: 要添加的消息
        """
        self.conversation.add_message(message)
        
        if self.config.auto_save_session:
            try:
                self.save()
            except Exception as e:
                # 保存失败不应中断程序运行
                logger.warning(f"自动保存会话失败（将继续运行）: {e}")
    
    def add_user_message(self, content: str) -> Message:
        """
        添加用户消息
        
        Args:
            content: 消息内容
            
        Returns:
            创建的消息
        """
        message = Message(role=MessageRole.USER, content=content)
        self.add_message(message)
        return message
    
    def add_assistant_message(
        self, 
        content: str, 
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> Message:
        """
        添加助手消息
        
        Args:
            content: 消息内容
            input_tokens: 输入 token 数
            output_tokens: 输出 token 数
            
        Returns:
            创建的消息
        """
        message = Message(
            role=MessageRole.ASSISTANT,
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        self.add_message(message)
        return message
    
    def save(self) -> None:
        """保存会话到文件（加密存储）"""
        try:
            data = {
                "session_id": self.session_id,
                "conversation": self.conversation.to_dict(),
                "metadata": self.metadata,
            }
            
            try:
                from foxcode.core.session_encryption import get_session_encryptor
                encryptor = get_session_encryptor()
                
                if encryptor.config.enabled:
                    encrypted_data = encryptor.encrypt(data)
                    storage_data = {
                        "encrypted": True,
                        "data": encrypted_data,
                        "version": 1,
                    }
                else:
                    storage_data = {
                        "encrypted": False,
                        "data": data,
                        "version": 1,
                    }
            except ImportError:
                storage_data = {
                    "encrypted": False,
                    "data": data,
                    "version": 1,
                }
            
            with open(self.session_path, "w", encoding="utf-8") as f:
                json.dump(storage_data, f, ensure_ascii=False, indent=2)
            
            # 设置文件权限为仅所有者可读写（安全最佳实践）
            # 在 Windows 上可能不支持，但不应静默忽略失败
            try:
                os.chmod(self.session_path, 0o600)
            except PermissionError as e:
                # 权限设置失败是安全问题，需要记录警告
                logger.warning(
                    f"无法设置会话文件权限 {self.session_path}: {e}。"
                    "会话文件可能被其他用户读取。"
                )
            except OSError as e:
                # Windows 等系统可能不支持 chmod，记录调试信息
                logger.debug(f"设置文件权限不支持或失败: {e}")
            
            logger.debug(f"会话已保存: {self.session_path}")
        except Exception as e:
            logger.error(f"保存会话失败: {e}")
            raise
    
    @classmethod
    def load(cls, config: Config, session_id: str) -> "Session":
        """
        加载会话（支持解密）
        
        Args:
            config: 配置实例
            session_id: 会话 ID
            
        Returns:
            加载的会话实例
        """
        session_path = config.get_session_path(session_id)
        
        if not session_path.exists():
            raise FileNotFoundError(f"会话不存在: {session_id}")
        
        try:
            with open(session_path, "r", encoding="utf-8") as f:
                storage_data = json.load(f)
            
            if storage_data.get("encrypted", False):
                try:
                    from foxcode.core.session_encryption import get_session_encryptor
                    encryptor = get_session_encryptor()
                    data = encryptor.decrypt_to_dict(storage_data.get("data", ""))
                except ImportError:
                    raise ValueError("会话数据已加密，但加密模块不可用")
                except Exception as e:
                    raise ValueError(f"解密会话数据失败: {e}")
            else:
                data = storage_data.get("data", storage_data)
            
            session = cls(config, session_id=data["session_id"])
            session.conversation = Conversation.from_dict(data["conversation"])
            session.metadata = data.get("metadata", {})
            
            logger.info(f"会话已加载: {session_id}")
            return session
        except Exception as e:
            logger.error(f"加载会话失败: {e}")
            raise
    
    def delete(self) -> None:
        """删除会话文件"""
        if self.session_path.exists():
            self.session_path.unlink()
            logger.info(f"会话已删除: {self.session_id}")
    
    @staticmethod
    def list_sessions(config: Config) -> list[dict[str, Any]]:
        """
        列出所有会话
        
        Args:
            config: 配置实例
            
        Returns:
            会话信息列表
        """
        config.ensure_directories()
        sessions = []
        
        for session_file in sorted(
            config.session_dir.glob("*.json"), 
            reverse=True
        ):
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                conversation = data.get("conversation", {})
                messages = conversation.get("messages", [])
                
                sessions.append({
                    "session_id": data.get("session_id", session_file.stem),
                    "created_at": conversation.get("created_at", ""),
                    "message_count": len(messages),
                    "total_tokens": (
                        conversation.get("total_input_tokens", 0) +
                        conversation.get("total_output_tokens", 0)
                    ),
                    "path": str(session_file),
                })
            except Exception as e:
                logger.warning(f"读取会话文件失败 {session_file}: {e}")
        
        return sessions
    
    def clear(self) -> None:
        """清空当前会话"""
        self.conversation.clear()
        self.metadata["cleared_at"] = datetime.now().isoformat()
        
        if self.config.auto_save_session:
            self.save()
    
    def export(self, format: str = "json") -> str:
        """
        导出会话
        
        Args:
            format: 导出格式 (json, markdown)
            
        Returns:
            导出的内容
        """
        if format == "json":
            return self.conversation.to_json()
        elif format == "markdown":
            lines = [
                f"# 会话导出",
                f"",
                f"- 会话 ID: {self.session_id}",
                f"- 创建时间: {self.conversation.created_at}",
                f"- 消息数量: {len(self.conversation.messages)}",
                f"",
                "---",
                f"",
            ]
            
            for msg in self.conversation.messages:
                role_name = {
                    "system": "系统",
                    "user": "用户",
                    "assistant": "助手",
                    "tool": "工具",
                }.get(msg.role.value, msg.role.value)
                
                lines.append(f"## {role_name}")
                lines.append(f"")
                lines.append(msg.get_text_content())
                lines.append(f"")
                lines.append("---")
                lines.append("")
            
            return "\n".join(lines)
        else:
            raise ValueError(f"不支持的导出格式: {format}")
    
    # ==================== 进度追踪相关方法 ====================
    
    def get_progress_manager(self) -> "ProgressManager":
        """
        获取进度管理器实例
        
        Returns:
            进度管理器实例
        """
        if self._progress_manager is None:
            from foxcode.core.progress import ProgressManager
            
            self._progress_manager = ProgressManager(
                working_dir=self.config.working_dir,
                progress_file=self.config.long_running.progress_file,
            )
        
        return self._progress_manager
    
    def get_feature_list(self) -> "FeatureList":
        """
        获取功能列表实例
        
        Returns:
            功能列表实例
        """
        if self._feature_list is None:
            from foxcode.core.feature_list import FeatureList
            
            feature_file = self.config.working_dir / self.config.long_running.feature_list_file
            self._feature_list = FeatureList(file_path=feature_file)
        
        return self._feature_list
    
    def get_context_bridge(self) -> "ContextBridge":
        """
        获取上下文桥接实例
        
        Returns:
            上下文桥接实例
        """
        if self._context_bridge is None:
            from foxcode.core.context_bridge import ContextBridge
            
            self._context_bridge = ContextBridge(
                working_dir=self.config.working_dir,
                summary_file=self.config.long_running.summary_file,
                compression_threshold=self.config.long_running.context_compression_threshold,
            )
        
        return self._context_bridge
    
    def get_session_type(self) -> "SessionType":
        """
        获取会话类型
        
        Returns:
            会话类型（INITIALIZER 或 CODER）
        """
        if self._session_type is None:
            self._session_type = self.get_context_bridge().detect_session_type()
        
        return self._session_type
    
    def load_progress_info(self) -> dict[str, Any]:
        """
        加载进度信息
        
        Returns:
            进度信息字典
        """
        try:
            progress_manager = self.get_progress_manager()
            context_bridge = self.get_context_bridge()
            feature_list = self.get_feature_list()
            
            # 加载进度
            if progress_manager.exists():
                progress_manager.load()
            
            # 加载功能列表
            if feature_list.file_path.exists():
                try:
                    feature_list.load()
                except Exception as e:
                    logger.warning(f"加载功能列表失败: {e}")
            
            # 加载摘要
            summary = context_bridge.load_summary()
            
            return {
                "progress_summary": progress_manager.get_summary() if progress_manager.exists() else "",
                "pending_features": [f.title for f in feature_list.get_pending_features()],
                "current_feature": feature_list.get_next_feature().title if feature_list.get_next_feature() else "",
                "recent_summary": summary.to_markdown() if summary else "",
            }
            
        except Exception as e:
            logger.error(f"加载进度信息失败: {e}")
            return {}
    
    def save_session_summary(
        self,
        completed_work: list[str] | None = None,
        incomplete_work: list[str] | None = None,
        issues: list[str] | None = None,
        next_steps: list[str] | None = None,
        decisions: list[str] | None = None,
        file_changes: list[str] | None = None,
        notes: str = "",
    ) -> None:
        """
        保存会话摘要
        
        Args:
            completed_work: 完成的工作列表
            incomplete_work: 未完成的工作列表
            issues: 遇到的问题列表
            next_steps: 下一步建议列表
            decisions: 关键决策列表
            file_changes: 文件变更列表
            notes: 备注
        """
        try:
            context_bridge = self.get_context_bridge()
            
            # 生成摘要
            summary = context_bridge.generate_summary(
                session_id=self.session_id,
                session_type=self.get_session_type(),
                completed_work=completed_work or [],
                incomplete_work=incomplete_work or [],
                issues=issues or [],
                next_steps=next_steps or [],
                decisions=decisions or [],
                file_changes=file_changes or [],
                notes=notes,
            )
            
            # 追加到历史
            context_bridge.append_summary(summary)
            
            # 保存当前摘要
            context_bridge.save_summary(summary)
            
            logger.info(f"会话摘要已保存: {self.session_id}")
            
        except Exception as e:
            logger.error(f"保存会话摘要失败: {e}")
            raise
    
    def update_progress(
        self,
        current_task: str | None = None,
        completed_tasks: list[str] | None = None,
        new_todos: list[str] | None = None,
    ) -> None:
        """
        更新进度
        
        Args:
            current_task: 当前任务描述
            completed_tasks: 已完成的任务列表
            new_todos: 新增的待办事项
        """
        try:
            progress_manager = self.get_progress_manager()
            
            # 更新当前任务
            if current_task:
                progress_manager.update_status(current_task=current_task)
            
            # 添加工作记录
            if completed_tasks:
                progress_manager.add_work_record(
                    session_id=self.session_id,
                    tasks=completed_tasks,
                )
            
            # 添加待办事项
            if new_todos:
                for todo in new_todos:
                    progress_manager.add_todo(todo)
            
            logger.debug(f"进度已更新: {current_task}")
            
        except Exception as e:
            logger.error(f"更新进度失败: {e}")
            raise
    
    # ==================== 工作流程相关方法 ====================
    
    def get_workflow_manager(self) -> "WorkflowManager":
        """
        获取工作流程管理器实例
        
        Returns:
            工作流程管理器实例
        """
        if self._workflow_manager is None:
            from foxcode.core.workflow import create_workflow_manager
            
            self._workflow_manager = create_workflow_manager(
                working_dir=self.config.working_dir,
            )
        
        return self._workflow_manager
    
    def get_current_workflow(self) -> "WorkflowInstance | None":
        """
        获取当前工作流程实例
        
        Returns:
            当前工作流程实例，如果没有则返回 None
        """
        if self._current_workflow is not None:
            return self._current_workflow
        
        # 尝试获取与当前功能关联的工作流程
        feature_list = self.get_feature_list()
        next_feature = feature_list.get_next_feature()
        
        if next_feature:
            workflow_manager = self.get_workflow_manager()
            self._current_workflow = workflow_manager.get_workflow_by_feature(next_feature.id)
        
        return self._current_workflow
    
    def start_workflow_for_feature(
        self,
        feature_id: str,
        branch_name: str = "",
    ) -> "WorkflowInstance":
        """
        为功能启动工作流程
        
        Args:
            feature_id: 功能 ID
            branch_name: 工作分支名称
            
        Returns:
            创建的工作流程实例
        """
        workflow_manager = self.get_workflow_manager()
        
        # 检查是否已存在工作流程
        existing = workflow_manager.get_workflow_by_feature(feature_id)
        if existing:
            self._current_workflow = existing
            logger.info(f"功能 {feature_id} 已有工作流程: {existing.id}")
            return existing
        
        # 创建新工作流程
        workflow = workflow_manager.create_workflow(
            feature_id=feature_id,
            branch_name=branch_name,
            metadata={
                "working_dir": str(self.config.working_dir),
                "session_id": self.session_id,
            },
        )
        
        self._current_workflow = workflow
        logger.info(f"已为功能 {feature_id} 创建工作流程: {workflow.id}")
        
        return workflow
    
    def advance_workflow(
        self,
        output: str = "",
        artifacts: list[str] | None = None,
    ) -> bool:
        """
        推进当前工作流程到下一阶段
        
        Args:
            output: 当前阶段输出
            artifacts: 产物文件列表
            
        Returns:
            是否成功推进
        """
        workflow = self.get_current_workflow()
        if not workflow:
            logger.warning("没有当前工作流程")
            return False
        
        workflow_manager = self.get_workflow_manager()
        current_phase = workflow.current_phase
        
        success = workflow_manager.complete_phase_manually(
            workflow_id=workflow.id,
            phase=current_phase,
            output=output,
            artifacts=artifacts,
        )
        
        if success:
            logger.info(f"工作流程已推进: {current_phase.get_display_name()} -> {workflow.current_phase.get_display_name()}")
        
        return success
    
    def get_workflow_context(self) -> dict[str, Any]:
        """
        获取工作流程上下文信息
        
        Returns:
            工作流程上下文字典
        """
        workflow = self.get_current_workflow()
        if not workflow:
            return {
                "has_workflow": False,
                "message": "当前没有活动的工作流程",
            }
        
        progress = workflow.get_progress()
        return {
            "has_workflow": True,
            "workflow_id": workflow.id,
            "feature_id": workflow.feature_id,
            "current_phase": workflow.current_phase.value,
            "current_phase_display": workflow.current_phase.get_display_name(),
            "progress_percent": progress["progress_percent"],
            "branch_name": workflow.branch_name,
        }
    
    # ==================== 上下文重置相关方法 ====================
    
    def get_context_reset_manager(self) -> "ContextResetManager":
        """
        获取上下文重置管理器实例
        
        返回当前会话的上下文重置管理器实例。如果实例不存在，则创建一个新的实例。
        上下文重置管理器用于管理上下文窗口的使用情况，并在必要时触发重置。
        
        Returns:
            ContextResetManager: 上下文重置管理器实例
        """
        if self._context_reset_manager is None:
            from foxcode.core.context_reset import ContextResetManager
            self._context_reset_manager = ContextResetManager(config=self.config)
        return self._context_reset_manager
    
    def get_agent_role(self) -> AgentRole:
        """
        获取当前代理角色
        
        返回当前会话中代理的角色类型。代理角色用于多代理协作系统中，
        区分不同职责的代理（如规划器、生成器、评估器）。
        
        Returns:
            AgentRole: 当前代理角色
        """
        return self._agent_role
    
    def switch_agent_role(self, role: AgentRole) -> None:
        """
        切换代理角色
        
        将当前会话的代理角色切换为指定的角色。切换角色后，
        后续的任务处理将按照新角色的职责进行。
        
        Args:
            role: 新的代理角色，可选值为 AgentRole.PLANNER、AgentRole.GENERATOR 或 AgentRole.EVALUATOR
            
        Example:
            >>> session.switch_agent_role(AgentRole.EVALUATOR)
            >>> print(session.get_agent_role())  # AgentRole.EVALUATOR
        """
        self._agent_role = role
        logger.info(f"代理角色已切换: {role.value}")
    
    def get_context_usage(self) -> "ContextUsageInfo":
        """
        获取上下文使用信息
        
        返回当前会话的上下文窗口使用情况，包括已使用的 token 数量、
        最大 token 数量和使用百分比等信息。
        
        Returns:
            ContextUsageInfo: 上下文使用信息实例，包含 token 使用详情
            
        Example:
            >>> usage = session.get_context_usage()
            >>> print(f"使用率: {usage.usage_percentage:.1f}%")
        """
        manager = self.get_context_reset_manager()
        return manager.get_context_usage(self)
    
    def reset_context(
        self,
        trigger: "ResetTrigger" = None,
        completed_work: list[str] | None = None,
        incomplete_work: list[str] | None = None,
        current_task: "TaskItem | None" = None,
        pending_tasks: list["TaskItem"] | None = None,
        completed_tasks: list["TaskItem"] | None = None,
        key_decisions: list[str] | None = None,
        file_changes: list[str] | None = None,
        next_steps: list[str] | None = None,
        issues: list[str] | None = None,
        blockers: list[str] | None = None,
        context_summary: str = "",
    ) -> "ResetResult":
        """
        重置上下文并生成 HandoffArtifact
        
        执行上下文重置操作，保存当前会话状态到 HandoffArtifact，
        清空对话历史，并从 HandoffArtifact 恢复关键上下文信息。
        此方法用于在上下文窗口接近限制时重置会话，避免模型性能下降。
        
        Args:
            trigger: 重置触发原因，默认为 MANUAL（手动触发）
            completed_work: 已完成工作描述列表
            incomplete_work: 未完成工作描述列表
            current_task: 当前正在执行的任务
            pending_tasks: 待处理任务列表
            completed_tasks: 已完成任务列表
            key_decisions: 关键决策列表
            file_changes: 文件变更列表
            next_steps: 下一步计划列表
            issues: 遇到的问题列表
            blockers: 阻塞项列表
            context_summary: 上下文摘要
            
        Returns:
            ResetResult: 重置结果实例，包含操作状态和相关信息
            
        Example:
            >>> result = session.reset_context(
            ...     completed_work=["实现用户登录功能"],
            ...     pending_tasks=[TaskItem(id="2", title="实现注册功能")],
            ... )
            >>> if result.success:
            ...     print(f"重置成功，新会话: {result.new_session_id}")
        """
        from foxcode.core.context_reset import ResetTrigger
        
        # 设置默认触发原因
        if trigger is None:
            trigger = ResetTrigger.MANUAL
        
        manager = self.get_context_reset_manager()
        
        return manager.reset_context(
            session=self,
            trigger=trigger,
            agent_role=self._agent_role,
            completed_work=completed_work,
            incomplete_work=incomplete_work,
            current_task=current_task,
            pending_tasks=pending_tasks,
            completed_tasks=completed_tasks,
            key_decisions=key_decisions,
            file_changes=file_changes,
            next_steps=next_steps,
            issues=issues,
            blockers=blockers,
            context_summary=context_summary,
        )
    
    def restore_from_artifact(self, artifact: "HandoffArtifact") -> bool:
        """
        从 HandoffArtifact 恢复状态
        
        将 HandoffArtifact 中记录的状态信息注入到当前会话中，
        使代理能够无缝继续之前的工作。恢复的内容包括任务状态、
        已完成工作、关键决策等信息。
        
        Args:
            artifact: HandoffArtifact 实例，包含要恢复的状态信息
            
        Returns:
            bool: 是否成功恢复状态
            
        Example:
            >>> artifact = HandoffArtifact.load("handoff_xxx.json")
            >>> success = session.restore_from_artifact(artifact)
            >>> if success:
            ...     print("状态恢复成功")
        """
        manager = self.get_context_reset_manager()
        success = manager.restore_context(self, artifact)
        
        if success:
            self._agent_role = artifact.agent_role
            logger.info(f"已从 HandoffArtifact 恢复状态，代理角色: {artifact.agent_role.value}")
        
        return success
    
    def load_and_restore_handoff(self) -> bool:
        """
        加载最近的 HandoffArtifact 并恢复状态
        
        从 handoff 目录中查找并加载最近创建的 HandoffArtifact 文件，
        然后将其状态恢复到当前会话。此方法通常在新会话开始时调用，
        用于继续之前中断的工作。
        
        Returns:
            bool: 是否成功找到并恢复 HandoffArtifact
            
        Example:
            >>> if session.load_and_restore_handoff():
            ...     print("成功恢复上次会话状态")
            ... else:
            ...     print("没有找到可恢复的会话状态")
        """
        manager = self.get_context_reset_manager()
        artifact = manager.load_latest_handoff()
        
        if artifact:
            return self.restore_from_artifact(artifact)
        
        return False
    
    def check_context_reset_needed(self) -> tuple[bool, str]:
        """
        检查是否需要上下文重置
        
        根据当前上下文使用率和配置的阈值，判断是否需要触发上下文重置。
        当上下文使用率超过配置的重置阈值时，建议执行重置操作。
        
        Returns:
            tuple[bool, str]: 元组 (是否需要重置, 原因说明)
            
        Example:
            >>> need_reset, reason = session.check_context_reset_needed()
            >>> if need_reset:
            ...     print(f"需要重置: {reason}")
            ...     session.reset_context()
        """
        manager = self.get_context_reset_manager()
        usage = self.get_context_usage()
        return manager.check_reset_needed(usage.used_tokens, usage.max_tokens)
