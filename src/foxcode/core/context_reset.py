"""
FoxCode 上下文重置管理模块

实现上下文重置机制，在上下文窗口接近限制时自动保存状态并启动新会话。
解决模型的"上下文焦虑"问题，支持长时间运行的代理任务。

核心功能：
- 检测是否需要重置（基于 token 使用率）
- 检测上下文焦虑行为（过早结束任务）
- 创建状态传递产物（HandoffArtifact）
- 从产物恢复状态
- 完整的重置流程管理
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

from foxcode.core.config import Config, AgentRole
from foxcode.core.handoff import HandoffArtifact, TaskItem

if TYPE_CHECKING:
    from foxcode.core.session import Session

logger = logging.getLogger(__name__)


class ResetTrigger(str, Enum):
    """
    重置触发原因枚举
    
    定义所有可能触发上下文重置的原因类型，用于追踪和诊断重置行为。
    
    Attributes:
        AUTO_THRESHOLD: 自动阈值触发 - 当上下文使用率达到配置的阈值时自动触发
        MANUAL: 手动触发 - 用户或系统显式请求重置
        ANXIETY_DETECTED: 焦虑检测触发 - 检测到模型的上下文焦虑行为
        ERROR_RECOVERY: 错误恢复触发 - 从错误状态恢复时触发重置
    """
    AUTO_THRESHOLD = "auto_threshold"
    MANUAL = "manual"
    ANXIETY_DETECTED = "anxiety_detected"
    ERROR_RECOVERY = "error_recovery"


@dataclass
class ResetResult:
    """
    重置结果数据类
    
    记录上下文重置操作的完整结果信息，包括成功/失败状态、
    相关 ID、文件路径和错误信息等。
    
    Attributes:
        success: 重置是否成功
        trigger: 触发重置的原因
        old_session_id: 重置前的会话 ID
        new_session_id: 重置后的新会话 ID（成功时）
        handoff_path: HandoffArtifact 文件路径（成功时）
        error: 错误信息（失败时）
        timestamp: 重置操作的时间戳
    """
    success: bool
    trigger: ResetTrigger
    old_session_id: str
    new_session_id: str | None = None
    handoff_path: str | None = None
    error: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict[str, Any]:
        """
        将重置结果转换为字典格式
        
        Returns:
            包含所有重置结果属性的字典
        """
        return {
            "success": self.success,
            "trigger": self.trigger.value,
            "old_session_id": self.old_session_id,
            "new_session_id": self.new_session_id,
            "handoff_path": self.handoff_path,
            "error": self.error,
            "timestamp": self.timestamp,
        }


@dataclass
class ContextUsageInfo:
    """
    上下文使用信息数据类
    
    记录当前上下文窗口的使用情况，包括 token 数量和使用百分比。
    用于监控上下文使用率，决定是否需要触发重置。
    
    Attributes:
        total_tokens: 总 token 数（输入 + 输出）
        used_tokens: 已使用的 token 数
        max_tokens: 最大允许的 token 数
        usage_percentage: 使用百分比（0-100）
    """
    total_tokens: int = 0
    used_tokens: int = 0
    max_tokens: int = 128000
    usage_percentage: float = 0.0
    
    def calculate_percentage(self) -> float:
        """
        计算使用百分比
        
        根据 used_tokens 和 max_tokens 计算使用百分比，
        结果保存在 usage_percentage 属性中。
        
        Returns:
            计算后的使用百分比（0-100）
        """
        if self.max_tokens <= 0:
            self.usage_percentage = 0.0
            return 0.0
        
        self.usage_percentage = (self.used_tokens / self.max_tokens) * 100
        return self.usage_percentage
    
    def is_above_threshold(self, threshold: float) -> bool:
        """
        检查使用率是否超过指定阈值
        
        Args:
            threshold: 阈值（0.0-1.0 之间的小数）
            
        Returns:
            如果使用率超过阈值返回 True，否则返回 False
        """
        return (self.usage_percentage / 100) >= threshold
    
    def to_dict(self) -> dict[str, Any]:
        """
        将上下文使用信息转换为字典格式
        
        Returns:
            包含所有使用信息的字典
        """
        return {
            "total_tokens": self.total_tokens,
            "used_tokens": self.used_tokens,
            "max_tokens": self.max_tokens,
            "usage_percentage": round(self.usage_percentage, 2),
        }


class ContextResetManager:
    """
    上下文重置管理器
    
    管理上下文重置流程，解决模型在长对话中的"上下文焦虑"问题。
    当上下文窗口接近限制时，自动保存当前状态并启动新会话，
    确保代理能够无缝继续工作。
    
    核心功能：
    - 检测是否需要重置（基于 token 使用率）
    - 检测上下文焦虑行为（过早结束任务）
    - 创建状态传递产物（HandoffArtifact）
    - 从产物恢复状态
    - 完整的重置流程管理
    
    Attributes:
        config: 配置实例
        handoff_dir: HandoffArtifact 存储目录
        reset_threshold: 重置阈值（0.0-1.0）
        warning_threshold: 警告阈值（0.0-1.0）
        max_context_tokens: 最大上下文 token 数
    """
    
    # 过早结束行为的关键词模式（上下文焦虑检测）
    # 这些模式用于检测模型是否因为上下文过长而试图过早结束任务
    ANXIETY_PATTERNS = [
        r"总结[一下]?$",
        r"完成[了]?$",
        r"结束[了]?$",
        r"这就是.*全部",
        r"以上.*总结",
        r"最后[，,].*总结",
        r"我来总结",
        r"让我总结",
        r"简要总结",
        r"快速总结",
        r"收尾工作",
        r"即将完成",
        r"接近尾声",
        r"差不多.*完成",
        r"基本完成",
        r"已经完成.*任务",
        r"任务.*完成",
        r"工作.*完成",
        r"差不多.*结束",
        r"差不多.*收尾",
    ]
    
    def __init__(
        self,
        config: Config,
        handoff_dir: str | None = None,
    ):
        """
        初始化上下文重置管理器
        
        Args:
            config: 配置实例，包含重置阈值等配置项
            handoff_dir: HandoffArtifact 存储目录，如果为 None 则使用配置中的目录
            
        Raises:
            OSError: 当无法创建 HandoffArtifact 目录时
        """
        self.config = config
        
        # 设置 HandoffArtifact 存储目录
        self.handoff_dir = Path(handoff_dir or config.long_running.handoff_dir)
        self._ensure_directory()
        
        # 从配置获取阈值
        self.reset_threshold = config.long_running.context_reset_threshold
        self.warning_threshold = config.long_running.context_warning_threshold
        self.max_context_tokens = config.long_running.max_context_tokens
        
        # 状态追踪
        self._last_reset_time: str | None = None
        self._reset_count: int = 0
        self._last_usage_info: ContextUsageInfo | None = None
        
        logger.info(
            f"上下文重置管理器初始化完成 - "
            f"重置阈值: {self.reset_threshold * 100:.1f}%, "
            f"警告阈值: {self.warning_threshold * 100:.1f}%, "
            f"最大上下文: {self.max_context_tokens} tokens"
        )
    
    def _ensure_directory(self) -> None:
        """
        确保 HandoffArtifact 目录存在
        
        如果目录不存在，则创建它。包括所有必要的父目录。
        
        Raises:
            OSError: 当创建目录失败时
        """
        try:
            self.handoff_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"HandoffArtifact 目录已确认: {self.handoff_dir}")
        except OSError as e:
            logger.error(f"创建 HandoffArtifact 目录失败: {e}")
            raise
    
    def check_reset_needed(
        self,
        current_tokens: int,
        max_tokens: int | None = None,
    ) -> tuple[bool, str]:
        """
        检测是否需要重置
        
        根据当前 token 使用量和配置的阈值判断是否需要触发上下文重置。
        
        Args:
            current_tokens: 当前使用的 token 数
            max_tokens: 最大 token 数，如果为 None 则使用配置值
            
        Returns:
            元组 (是否需要重置, 原因说明)
            
        Example:
            >>> manager = ContextResetManager(config)
            >>> need_reset, reason = manager.check_reset_needed(100000)
            >>> if need_reset:
            ...     print(f"需要重置: {reason}")
        """
        max_tokens = max_tokens or self.max_context_tokens
        
        # 参数验证
        if max_tokens <= 0:
            error_msg = "无效的最大 token 数（必须大于 0）"
            logger.warning(error_msg)
            return False, error_msg
        
        if current_tokens < 0:
            error_msg = "无效的当前 token 数（不能为负数）"
            logger.warning(error_msg)
            return False, error_msg
        
        # 计算使用率
        usage_ratio = current_tokens / max_tokens
        
        # 更新最后的使用信息
        self._last_usage_info = ContextUsageInfo(
            total_tokens=current_tokens,
            used_tokens=current_tokens,
            max_tokens=max_tokens,
        )
        self._last_usage_info.calculate_percentage()
        
        # 检查是否超过重置阈值
        if usage_ratio >= self.reset_threshold:
            reason = (
                f"上下文使用率达到 {usage_ratio * 100:.1f}%，"
                f"超过重置阈值 {self.reset_threshold * 100:.1f}%"
            )
            logger.warning(f"[重置触发] {reason}")
            return True, reason
        
        # 检查是否超过警告阈值
        if usage_ratio >= self.warning_threshold:
            logger.info(
                f"[上下文警告] 使用率达到 {usage_ratio * 100:.1f}%，"
                f"接近重置阈值 {self.reset_threshold * 100:.1f}%"
            )
        
        return False, f"上下文使用率 {usage_ratio * 100:.1f}%，无需重置"
    
    def detect_anxiety(
        self,
        output_text: str,
        pending_tasks: list[TaskItem] | None = None,
    ) -> tuple[bool, str]:
        """
        检测上下文焦虑行为
        
        分析模型输出文本，检测是否存在"上下文焦虑"行为。
        上下文焦虑是指模型因为上下文过长而试图过早结束任务的行为。
        
        检测逻辑：
        1. 检查输出是否匹配焦虑模式（如"总结"、"完成"等关键词）
        2. 检查是否仍有待处理任务
        3. 如果两者都成立，则判定为焦虑行为
        
        Args:
            output_text: 模型输出文本
            pending_tasks: 待处理任务列表
            
        Returns:
            元组 (是否检测到焦虑, 检测到的模式说明)
            
        Example:
            >>> manager = ContextResetManager(config)
            >>> tasks = [TaskItem(id="1", title="实现功能")]
            >>> is_anxious, reason = manager.detect_anxiety("让我总结一下", tasks)
            >>> if is_anxious:
            ...     print(f"检测到焦虑: {reason}")
        """
        if not output_text:
            return False, ""
        
        # 检查是否有待处理任务
        has_pending = pending_tasks and len(pending_tasks) > 0
        
        # 检查输出是否匹配焦虑模式
        detected_patterns: list[str] = []
        
        for pattern in self.ANXIETY_PATTERNS:
            try:
                if re.search(pattern, output_text, re.IGNORECASE):
                    detected_patterns.append(pattern)
            except re.error as e:
                logger.warning(f"正则表达式错误（模式: {pattern}）: {e}")
                continue
        
        # 如果检测到焦虑模式且仍有待处理任务，则判定为焦虑行为
        if detected_patterns and has_pending:
            reason = (
                f"检测到上下文焦虑行为 - "
                f"匹配模式: {detected_patterns[:3]}{'...' if len(detected_patterns) > 3 else ''}，"
                f"仍有 {len(pending_tasks)} 个待处理任务"
            )
            logger.warning(f"[焦虑检测] {reason}")
            return True, reason
        
        # 如果检测到焦虑模式但没有待处理任务，记录调试信息
        if detected_patterns and not has_pending:
            logger.debug(
                f"检测到结束模式但无待处理任务，可能是正常结束 - "
                f"匹配模式: {detected_patterns[:3]}"
            )
        
        return False, ""
    
    def get_context_usage(
        self,
        session: "Session",
    ) -> ContextUsageInfo:
        """
        获取上下文使用信息
        
        从会话实例中提取当前的上下文使用情况，包括 token 数量和使用百分比。
        
        Args:
            session: 会话实例
            
        Returns:
            ContextUsageInfo 实例，包含当前上下文使用信息
            
        Example:
            >>> manager = ContextResetManager(config)
            >>> usage = manager.get_context_usage(session)
            >>> print(f"使用率: {usage.usage_percentage:.1f}%")
        """
        info = ContextUsageInfo(max_tokens=self.max_context_tokens)
        
        try:
            # 从会话获取 token 使用情况
            conversation = session.conversation
            info.total_tokens = (
                conversation.total_input_tokens + 
                conversation.total_output_tokens
            )
            info.used_tokens = info.total_tokens
            info.calculate_percentage()
            
            # 缓存使用信息
            self._last_usage_info = info
            
            logger.debug(
                f"上下文使用信息 - "
                f"输入: {conversation.total_input_tokens}, "
                f"输出: {conversation.total_output_tokens}, "
                f"总计: {info.total_tokens}, "
                f"使用率: {info.usage_percentage:.1f}%"
            )
            
        except AttributeError as e:
            logger.error(f"获取上下文使用信息失败（属性错误）: {e}")
        except Exception as e:
            logger.error(f"获取上下文使用信息失败: {e}")
        
        return info
    
    def create_handoff(
        self,
        session: "Session",
        agent_role: AgentRole = AgentRole.GENERATOR,
        trigger: ResetTrigger = ResetTrigger.AUTO_THRESHOLD,
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
    ) -> HandoffArtifact:
        """
        创建状态传递产物
        
        创建一个 HandoffArtifact 实例，记录当前会话的完整状态信息，
        用于在上下文重置后恢复工作上下文。
        
        Args:
            session: 会话实例
            agent_role: 当前代理角色
            trigger: 重置触发原因
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
            创建的 HandoffArtifact 实例
            
        Example:
            >>> manager = ContextResetManager(config)
            >>> artifact = manager.create_handoff(
            ...     session=session,
            ...     completed_work=["实现用户登录功能"],
            ...     pending_tasks=[TaskItem(id="2", title="实现用户注册")],
            ... )
        """
        # 创建 HandoffArtifact
        artifact = HandoffArtifact(
            session_id=session.session_id,
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
            working_directory=str(self.config.working_dir),
            metadata={
                "trigger": trigger.value,
                "reset_count": self._reset_count,
                "created_at": datetime.now().isoformat(),
                "manager_version": "1.0.0",
            },
        )
        
        # 保存到文件
        handoff_path = self._get_handoff_path(session.session_id)
        
        try:
            artifact.save(handoff_path)
            logger.info(f"HandoffArtifact 已创建并保存: {handoff_path}")
        except Exception as e:
            logger.error(f"保存 HandoffArtifact 失败: {e}")
            raise
        
        return artifact
    
    def restore_context(
        self,
        session: "Session",
        handoff: HandoffArtifact,
    ) -> bool:
        """
        从 HandoffArtifact 恢复状态
        
        将 HandoffArtifact 中记录的状态信息注入到新会话中，
        使代理能够无缝继续之前的工作。
        
        Args:
            session: 目标会话实例
            handoff: HandoffArtifact 实例
            
        Returns:
            是否成功恢复
            
        Example:
            >>> manager = ContextResetManager(config)
            >>> handoff = manager.load_latest_handoff()
            >>> if handoff:
            ...     success = manager.restore_context(new_session, handoff)
        """
        try:
            # 构建恢复上下文消息
            context_message = handoff.to_prompt_context()
            
            # 添加恢复提示
            restore_prompt = (
                f"[系统] 从上一会话恢复上下文\n\n"
                f"**源会话 ID**: {handoff.session_id}\n"
                f"**恢复时间**: {datetime.now().isoformat()}\n\n"
                f"---\n\n{context_message}\n\n"
                f"---\n\n"
                f"请根据以上上下文继续工作。"
            )
            
            # 添加到会话
            session.add_user_message(restore_prompt)
            
            logger.info(
                f"上下文已恢复 - "
                f"源会话: {handoff.session_id}, "
                f"待处理任务: {len(handoff.pending_tasks)}, "
                f"已完成工作: {len(handoff.completed_work)}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"恢复上下文失败: {e}")
            return False
    
    def load_latest_handoff(self) -> HandoffArtifact | None:
        """
        加载最近的 HandoffArtifact
        
        从 handoff_dir 目录中查找并加载最近创建的 HandoffArtifact 文件。
        按文件修改时间排序，返回最新的一个。
        
        Returns:
            最近的 HandoffArtifact 实例，如果没有找到则返回 None
            
        Example:
            >>> manager = ContextResetManager(config)
            >>> latest = manager.load_latest_handoff()
            >>> if latest:
            ...     print(f"最新会话: {latest.session_id}")
        """
        try:
            # 查找所有 handoff 文件
            handoff_files = list(self.handoff_dir.glob("handoff_*.json"))
            
            if not handoff_files:
                logger.debug("没有找到 HandoffArtifact 文件")
                return None
            
            # 按修改时间排序，获取最新的
            handoff_files.sort(
                key=lambda f: f.stat().st_mtime, 
                reverse=True
            )
            latest_file = handoff_files[0]
            
            # 加载文件
            artifact = HandoffArtifact.load(latest_file)
            
            logger.info(
                f"已加载最近的 HandoffArtifact - "
                f"文件: {latest_file.name}, "
                f"会话: {artifact.session_id}"
            )
            
            return artifact
            
        except FileNotFoundError:
            logger.warning("HandoffArtifact 文件不存在")
            return None
        except Exception as e:
            logger.error(f"加载 HandoffArtifact 失败: {e}")
            return None
    
    def load_handoff_by_session(self, session_id: str) -> HandoffArtifact | None:
        """
        根据会话 ID 加载 HandoffArtifact
        
        查找并加载指定会话 ID 对应的 HandoffArtifact 文件。
        
        Args:
            session_id: 会话 ID
            
        Returns:
            对应的 HandoffArtifact 实例，如果没有找到则返回 None
        """
        try:
            # 查找匹配的 handoff 文件
            pattern = f"handoff_{session_id}_*.json"
            handoff_files = list(self.handoff_dir.glob(pattern))
            
            if not handoff_files:
                logger.debug(f"没有找到会话 {session_id} 的 HandoffArtifact")
                return None
            
            # 按修改时间排序，获取最新的
            handoff_files.sort(
                key=lambda f: f.stat().st_mtime, 
                reverse=True
            )
            latest_file = handoff_files[0]
            
            artifact = HandoffArtifact.load(latest_file)
            logger.info(f"已加载会话 {session_id} 的 HandoffArtifact")
            
            return artifact
            
        except Exception as e:
            logger.error(f"加载会话 {session_id} 的 HandoffArtifact 失败: {e}")
            return None
    
    def reset_context(
        self,
        session: "Session",
        trigger: ResetTrigger = ResetTrigger.MANUAL,
        agent_role: AgentRole = AgentRole.GENERATOR,
        **handoff_kwargs: Any,
    ) -> ResetResult:
        """
        执行上下文重置
        
        执行完整的上下文重置流程：
        1. 创建 HandoffArtifact 保存当前状态
        2. 保存当前会话
        3. 清空对话历史
        4. 从 HandoffArtifact 恢复关键上下文
        
        Args:
            session: 会话实例
            trigger: 重置触发原因
            agent_role: 当前代理角色
            **handoff_kwargs: 传递给 create_handoff 的额外参数
            
        Returns:
            ResetResult 实例，包含重置操作的完整结果
            
        Example:
            >>> manager = ContextResetManager(config)
            >>> result = manager.reset_context(
            ...     session=session,
            ...     trigger=ResetTrigger.AUTO_THRESHOLD,
            ...     completed_work=["实现登录功能"],
            ...     pending_tasks=[TaskItem(id="2", title="实现注册")],
            ... )
            >>> if result.success:
            ...     print(f"重置成功，新会话: {result.new_session_id}")
        """
        old_session_id = session.session_id
        
        logger.info(
            f"开始上下文重置 - "
            f"会话: {old_session_id}, "
            f"触发原因: {trigger.value}"
        )
        
        try:
            # 步骤 1: 创建 HandoffArtifact
            handoff = self.create_handoff(
                session=session,
                agent_role=agent_role,
                trigger=trigger,
                **handoff_kwargs,
            )
            
            # 步骤 2: 保存当前会话
            try:
                session.save()
                logger.debug(f"会话已保存: {old_session_id}")
            except Exception as e:
                logger.warning(f"保存会话失败（将继续重置）: {e}")
            
            # 步骤 3: 清空对话
            session.clear()
            logger.debug("对话已清空")
            
            # 步骤 4: 恢复上下文
            restore_success = self.restore_context(session, handoff)
            
            if not restore_success:
                logger.warning("上下文恢复失败，会话将以空上下文继续")
            
            # 更新状态追踪
            self._last_reset_time = datetime.now().isoformat()
            self._reset_count += 1
            
            # 构建成功结果
            result = ResetResult(
                success=True,
                trigger=trigger,
                old_session_id=old_session_id,
                new_session_id=session.session_id,
                handoff_path=str(self._get_handoff_path(old_session_id)),
            )
            
            logger.info(
                f"上下文重置成功 - "
                f"旧会话: {old_session_id}, "
                f"新会话: {session.session_id}, "
                f"累计重置次数: {self._reset_count}"
            )
            
            return result
            
        except Exception as e:
            error_msg = f"上下文重置失败: {e}"
            logger.error(error_msg, exc_info=True)
            
            return ResetResult(
                success=False,
                trigger=trigger,
                old_session_id=old_session_id,
                error=str(e),
            )
    
    def _get_handoff_path(self, session_id: str) -> Path:
        """
        获取 HandoffArtifact 文件路径
        
        根据会话 ID 和当前时间戳生成唯一的文件路径。
        
        Args:
            session_id: 会话 ID
            
        Returns:
            HandoffArtifact 文件的完整路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"handoff_{session_id}_{timestamp}.json"
        return self.handoff_dir / filename
    
    def get_statistics(self) -> dict[str, Any]:
        """
        获取重置统计信息
        
        返回上下文重置管理器的运行统计信息，包括重置次数、
        阈值配置、目录路径等。
        
        Returns:
            包含统计信息的字典
            
        Example:
            >>> manager = ContextResetManager(config)
            >>> stats = manager.get_statistics()
            >>> print(f"累计重置次数: {stats['reset_count']}")
        """
        stats = {
            "reset_count": self._reset_count,
            "last_reset_time": self._last_reset_time,
            "reset_threshold": self.reset_threshold,
            "warning_threshold": self.warning_threshold,
            "max_context_tokens": self.max_context_tokens,
            "handoff_dir": str(self.handoff_dir),
        }
        
        # 添加最后的使用信息
        if self._last_usage_info:
            stats["last_usage"] = self._last_usage_info.to_dict()
        
        # 统计 handoff 文件数量
        try:
            handoff_count = len(list(self.handoff_dir.glob("handoff_*.json")))
            stats["handoff_file_count"] = handoff_count
        except Exception:
            stats["handoff_file_count"] = 0
        
        return stats
    
    def cleanup_old_handoffs(
        self,
        max_age_days: int = 30,
        max_count: int = 100,
    ) -> int:
        """
        清理旧的 HandoffArtifact 文件
        
        根据文件年龄和数量限制清理旧的 handoff 文件，
        防止文件堆积占用过多磁盘空间。
        
        Args:
            max_age_days: 最大保留天数，超过此天数的文件将被删除
            max_count: 最大保留数量，超过此数量时删除最旧的文件
            
        Returns:
            删除的文件数量
        """
        import time
        
        deleted_count = 0
        
        try:
            # 获取所有 handoff 文件
            handoff_files = list(self.handoff_dir.glob("handoff_*.json"))
            
            if not handoff_files:
                return 0
            
            # 按修改时间排序（旧的在前）
            handoff_files.sort(key=lambda f: f.stat().st_mtime)
            
            current_time = time.time()
            max_age_seconds = max_age_days * 24 * 60 * 60
            
            # 按年龄删除
            for file_path in handoff_files:
                file_age = current_time - file_path.stat().st_mtime
                
                if file_age > max_age_seconds:
                    try:
                        file_path.unlink()
                        deleted_count += 1
                        logger.debug(f"已删除过期 handoff 文件: {file_path.name}")
                    except Exception as e:
                        logger.warning(f"删除文件失败 {file_path}: {e}")
            
            # 如果删除后仍超过最大数量，继续删除最旧的
            remaining_files = list(self.handoff_dir.glob("handoff_*.json"))
            remaining_files.sort(key=lambda f: f.stat().st_mtime)
            
            while len(remaining_files) > max_count:
                oldest = remaining_files.pop(0)
                try:
                    oldest.unlink()
                    deleted_count += 1
                    logger.debug(f"已删除超量 handoff 文件: {oldest.name}")
                except Exception as e:
                    logger.warning(f"删除文件失败 {oldest}: {e}")
            
            if deleted_count > 0:
                logger.info(f"清理完成，共删除 {deleted_count} 个 handoff 文件")
            
        except Exception as e:
            logger.error(f"清理 handoff 文件失败: {e}")
        
        return deleted_count
    
    def should_trigger_reset(
        self,
        session: "Session",
        output_text: str = "",
        pending_tasks: list[TaskItem] | None = None,
    ) -> tuple[bool, ResetTrigger, str]:
        """
        综合判断是否应该触发重置
        
        综合考虑上下文使用率和焦虑检测，判断是否应该触发重置。
        这是 check_reset_needed 和 detect_anxiety 的组合方法。
        
        Args:
            session: 会话实例
            output_text: 模型输出文本（用于焦虑检测）
            pending_tasks: 待处理任务列表
            
        Returns:
            元组 (是否应该重置, 触发原因, 详细说明)
            
        Example:
            >>> manager = ContextResetManager(config)
            >>> should, trigger, reason = manager.should_trigger_reset(
            ...     session, "让我总结一下", pending_tasks
            ... )
            >>> if should:
            ...     print(f"触发重置: {trigger.value} - {reason}")
        """
        # 获取上下文使用信息
        usage_info = self.get_context_usage(session)
        
        # 检查是否超过阈值
        need_reset, threshold_reason = self.check_reset_needed(usage_info.used_tokens)
        
        if need_reset:
            return True, ResetTrigger.AUTO_THRESHOLD, threshold_reason
        
        # 检查焦虑行为
        if output_text and pending_tasks:
            is_anxious, anxiety_reason = self.detect_anxiety(
                output_text, pending_tasks
            )
            
            if is_anxious:
                # 只有在上下文使用率较高时才因焦虑触发重置
                if usage_info.is_above_threshold(self.warning_threshold):
                    return True, ResetTrigger.ANXIETY_DETECTED, anxiety_reason
                else:
                    logger.info(
                        f"检测到焦虑行为但上下文使用率较低 "
                        f"({usage_info.usage_percentage:.1f}%)，暂不触发重置"
                    )
        
        return False, ResetTrigger.MANUAL, "无需重置"


def create_context_reset_manager(config: Config) -> ContextResetManager:
    """
    创建上下文重置管理器的便捷函数
    
    提供一种简洁的方式来创建 ContextResetManager 实例。
    
    Args:
        config: 配置实例
        
    Returns:
        上下文重置管理器实例
        
    Example:
        >>> from foxcode.core.config import Config
        >>> config = Config.create()
        >>> manager = create_context_reset_manager(config)
    """
    return ContextResetManager(config=config)
