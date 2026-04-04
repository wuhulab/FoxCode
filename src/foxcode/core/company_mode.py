"""
FoxCode 公司模式管理器

整合公司模式的所有功能，包括：
- 模式开关控制
- QQbot 服务管理
- 安全验证管理
- 长期工作模式执行
- 状态监控和报告
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from foxcode.core.agent import FoxCodeAgent
    from foxcode.core.config import Config
    from foxcode.core.orchestrator import MultiAgentOrchestrator

from foxcode.core.company_mode_config import (
    CompanyModeConfig,
    CompanyModeStatus,
)
from foxcode.core.qqbot_logger import (
    LogEventType,
    QQbotLogger,
)
from foxcode.core.qqbot_service import (
    QQbotMessage,
    QQbotService,
    QQbotStatus,
)
from foxcode.core.security_filter import (
    SecurityManager,
)

logger = logging.getLogger(__name__)


class AgentExecutionMode(str, Enum):
    """Agent 执行模式枚举"""
    SIMULATION = "simulation"     # 模拟模式（默认，不调用真实 AI）
    SINGLE_AGENT = "single_agent" # 单代理模式（使用 FoxCodeAgent）
    MULTI_AGENT = "multi_agent"   # 多代理模式（使用 MultiAgentOrchestrator）


@dataclass
class WorkTask:
    """工作任务"""
    id: str                                     # 任务 ID
    description: str                            # 任务描述
    target_subfolder: str                       # 目标子文件夹
    status: str = "pending"                     # 状态: pending, running, completed, failed
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: str | None = None
    completed_at: str | None = None
    current_phase: str = ""                     # 当前阶段
    phases: list[dict[str, Any]] = field(default_factory=list)  # 阶段列表
    result: str = ""                            # 结果
    error: str | None = None                    # 错误信息
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "description": self.description,
            "target_subfolder": self.target_subfolder,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "current_phase": self.current_phase,
            "phases": self.phases,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class CompanyModeState:
    """公司模式状态"""
    status: CompanyModeStatus = CompanyModeStatus.DISABLED
    qqbot_status: QQbotStatus = QQbotStatus.DISCONNECTED
    active_tasks: list[str] = field(default_factory=list)
    completed_tasks: int = 0
    failed_tasks: int = 0
    security_events: int = 0
    uptime_seconds: float = 0
    last_activity: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "status": self.status.value,
            "qqbot_status": self.qqbot_status.value,
            "active_tasks": self.active_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "security_events": self.security_events,
            "uptime_seconds": self.uptime_seconds,
            "last_activity": self.last_activity,
        }


class CompanyModeManager:
    """
    公司模式管理器
    
    管理公司模式的启用/禁用、QQbot 服务、安全验证和工作任务
    
    支持三种执行模式：
    - SIMULATION: 模拟模式，不调用真实 AI（默认）
    - SINGLE_AGENT: 单代理模式，使用 FoxCodeAgent 执行任务
    - MULTI_AGENT: 多代理模式，使用 MultiAgentOrchestrator 协调多代理协作
    """

    STATE_FILE = ".foxcode/company_mode_state.json"

    def __init__(
        self,
        config: CompanyModeConfig,
        working_dir: Path | None = None,
        foxcode_config: Config | None = None,
        execution_mode: AgentExecutionMode = AgentExecutionMode.SIMULATION,
    ):
        """
        初始化公司模式管理器
        
        Args:
            config: 公司模式配置
            working_dir: 工作目录
            foxcode_config: FoxCode 主配置（用于创建 Agent）
            execution_mode: Agent 执行模式
        """
        self.config = config
        self.working_dir = working_dir or Path.cwd()
        self.execution_mode = execution_mode

        # FoxCode 配置（用于创建 Agent）
        self._foxcode_config = foxcode_config

        # 状态
        self.state = CompanyModeState()
        self._start_time: float = 0

        # QQbot 服务
        self._qqbot_service: QQbotService | None = None

        # 安全管理器
        self._security_manager: SecurityManager | None = None

        # 日志记录器
        self._logger: QQbotLogger | None = None

        # 工作任务
        self._tasks: dict[str, WorkTask] = {}
        self._task_queue: asyncio.Queue | None = None
        self._worker_task: asyncio.Task | None = None

        # 消息处理器
        self._message_handlers: list[Callable] = []

        # 报告回调
        self._report_callback: Callable | None = None

        # AI Agent 相关
        self._agent: FoxCodeAgent | None = None
        self._orchestrator: MultiAgentOrchestrator | None = None

        # 加载状态
        self._load_state()

        logger.info(f"公司模式管理器初始化完成，执行模式: {execution_mode.value}")

    def _load_state(self) -> None:
        """加载状态"""
        state_file = self.working_dir / self.STATE_FILE
        if state_file.exists():
            try:
                with open(state_file, encoding="utf-8") as f:
                    data = json.load(f)
                self.state.status = CompanyModeStatus(data.get("status", "disabled"))
                self.state.completed_tasks = data.get("completed_tasks", 0)
                self.state.failed_tasks = data.get("failed_tasks", 0)
                logger.debug(f"加载状态: {self.state.status.value}")
            except Exception as e:
                logger.warning(f"加载状态失败: {e}")

    def _save_state(self) -> None:
        """保存状态"""
        state_file = self.working_dir / self.STATE_FILE
        try:
            state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(self.state.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存状态失败: {e}")

    # ==================== 模式控制 ====================

    async def enable(self) -> tuple[bool, str]:
        """
        启用公司模式
        
        Returns:
            (是否成功, 消息)
        """
        if self.state.status == CompanyModeStatus.ENABLED:
            return True, "公司模式已启用"

        if self.state.status == CompanyModeStatus.STARTING:
            return False, "公司模式正在启动中"

        try:
            self.state.status = CompanyModeStatus.STARTING
            self._start_time = datetime.now().timestamp()

            # 初始化日志记录器
            self._logger = QQbotLogger(
                config=self.config.logging,
                working_dir=self.working_dir,
            )

            # 初始化安全管理器
            self._security_manager = SecurityManager(
                content_filter_config=self.config.content_filter,
                security_config=self.config.security,
            )

            # 检查是否可以启动 QQbot
            if self.config.can_start_qqbot():
                # 初始化 QQbot 服务
                self._qqbot_service = QQbotService(self.config.qqbot)

                # 注册消息处理器
                self._qqbot_service.on_message(self._handle_qqbot_message)

                # 启动 QQbot 服务
                success = await self._qqbot_service.start()
                if success:
                    self.state.qqbot_status = QQbotStatus.READY
                    self._logger.log_connection(LogEventType.CONNECTED)
                else:
                    logger.warning("QQbot 服务启动失败，公司模式将以无机器人模式运行")
                    self.state.qqbot_status = QQbotStatus.ERROR
            else:
                logger.info("QQbot 配置不完整，公司模式将以无机器人模式运行")
                self.state.qqbot_status = QQbotStatus.DISCONNECTED

            # 启动工作任务处理器
            if self.config.long_work_mode:
                self._task_queue = asyncio.Queue()
                self._worker_task = asyncio.create_task(self._work_loop())

            self.state.status = CompanyModeStatus.ENABLED
            self.state.last_activity = datetime.now().isoformat()

            self._save_state()

            if self._logger:
                self._logger.log_work_mode(
                    event_type=LogEventType.WORK_MODE_STARTED,
                    content="公司模式已启用",
                )

            logger.info("公司模式已启用")
            return True, "公司模式已启用"

        except Exception as e:
            logger.error(f"启用公司模式失败: {e}")
            self.state.status = CompanyModeStatus.ERROR
            return False, f"启用失败: {str(e)}"

    async def disable(self) -> tuple[bool, str]:
        """
        禁用公司模式
        
        Returns:
            (是否成功, 消息)
        """
        if self.state.status == CompanyModeStatus.DISABLED:
            return True, "公司模式已禁用"

        try:
            self.state.status = CompanyModeStatus.STOPPING

            # 停止工作任务处理器
            if self._worker_task:
                self._worker_task.cancel()
                try:
                    await self._worker_task
                except asyncio.CancelledError:
                    pass
                self._worker_task = None

            # 停止 QQbot 服务
            if self._qqbot_service:
                await self._qqbot_service.stop()
                self.state.qqbot_status = QQbotStatus.DISCONNECTED

                if self._logger:
                    self._logger.log_connection(LogEventType.DISCONNECTED)

            # 计算运行时间
            if self._start_time > 0:
                self.state.uptime_seconds = datetime.now().timestamp() - self._start_time

            self.state.status = CompanyModeStatus.DISABLED

            if self._logger:
                self._logger.log_work_mode(
                    event_type=LogEventType.WORK_MODE_STOPPED,
                    content="公司模式已禁用",
                )

            self._save_state()

            logger.info("公司模式已禁用")
            return True, "公司模式已禁用"

        except Exception as e:
            logger.error(f"禁用公司模式失败: {e}")
            self.state.status = CompanyModeStatus.ERROR
            return False, f"禁用失败: {str(e)}"

    def is_enabled(self) -> bool:
        """检查公司模式是否启用"""
        return self.state.status == CompanyModeStatus.ENABLED

    # ==================== QQbot 消息处理 ====================

    async def _handle_qqbot_message(self, message: QQbotMessage) -> None:
        """
        处理 QQbot 消息
        
        Args:
            message: QQbot 消息
        """
        if not self._security_manager or not self._logger:
            return

        # 记录收到的消息
        self._logger.log_message_received(
            message_id=message.id,
            channel_id=message.channel_id,
            author_id=message.author_id,
            content=message.content,
        )

        # 安全验证
        allowed, filtered, reason = self._security_manager.validate_request(
            content=message.content,
            identifier=message.author_id,
        )

        if not allowed:
            # 记录阻止
            self._logger.log_message_blocked(
                author_id=message.author_id,
                content=message.content,
                block_reason=reason,
            )
            self.state.security_events += 1
            return

        if filtered.was_filtered:
            # 记录过滤
            self._logger.log_message_filtered(
                author_id=message.author_id,
                content=message.content,
                filter_reason=", ".join(filtered.matched_rules),
            )

        # 使用过滤后的内容
        safe_content = filtered.filtered

        # 调用消息处理器
        for handler in self._message_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message, safe_content)
                else:
                    handler(message, safe_content)
            except Exception as e:
                logger.error(f"消息处理器执行失败: {e}")

        self.state.last_activity = datetime.now().isoformat()

    def register_message_handler(self, handler: Callable) -> None:
        """
        注册消息处理器
        
        Args:
            handler: 处理函数，接收 (message, safe_content) 参数
        """
        self._message_handlers.append(handler)
        logger.debug(f"注册消息处理器: {handler.__name__ if hasattr(handler, '__name__') else 'anonymous'}")

    async def send_qqbot_message(
        self,
        channel_id: str,
        content: str,
    ) -> tuple[bool, str]:
        """
        发送 QQbot 消息
        
        Args:
            channel_id: 频道 ID
            content: 消息内容
            
        Returns:
            (是否成功, 消息)
        """
        if not self._qqbot_service or not self._qqbot_service.is_ready():
            return False, "QQbot 服务未就绪"

        # 内容过滤
        if self._security_manager:
            filtered = self._security_manager.content_filter.filter(content)
            content = filtered.filtered

        # 发送消息
        response = await self._qqbot_service.send_message(
            channel_id=channel_id,
            content=content,
        )

        # 记录日志
        if self._logger:
            self._logger.log_message_sent(
                channel_id=channel_id,
                content=content,
                success=response.success,
            )

        return response.success, response.error or "发送成功"

    # ==================== 工作任务管理 ====================

    def create_work_task(
        self,
        description: str,
        target_subfolder: str,
        metadata: dict[str, Any] | None = None,
    ) -> WorkTask:
        """
        创建工作任务
        
        Args:
            description: 任务描述
            target_subfolder: 目标子文件夹
            metadata: 元数据
            
        Returns:
            创建的任务
        """
        import uuid

        task_id = f"TASK-{uuid.uuid4().hex[:8].upper()}"

        task = WorkTask(
            id=task_id,
            description=description,
            target_subfolder=target_subfolder,
            metadata=metadata or {},
        )

        self._tasks[task_id] = task

        if self._logger:
            self._logger.log_work_mode(
                event_type=LogEventType.TASK_STARTED,
                task_id=task_id,
                content=f"创建任务: {description}",
                metadata={"target_subfolder": target_subfolder},
            )

        logger.info(f"创建工作任务: {task_id} - {description}")
        return task

    async def start_work_task(self, task: WorkTask) -> bool:
        """
        启动工作任务
        
        Args:
            task: 工作任务
            
        Returns:
            是否成功启动
        """
        if not self.is_enabled():
            logger.warning("公司模式未启用，无法启动任务")
            return False

        if task.status != "pending":
            logger.warning(f"任务状态不正确: {task.status}")
            return False

        # 确保任务队列已初始化
        if self._task_queue is None:
            logger.info("初始化任务队列...")
            self._task_queue = asyncio.Queue()
            if self._worker_task is None or self._worker_task.done():
                self._worker_task = asyncio.create_task(self._work_loop())
                logger.info("工作任务处理循环已启动")

        task.status = "running"
        task.started_at = datetime.now().isoformat()
        self.state.active_tasks.append(task.id)

        await self._task_queue.put(task)

        logger.info(f"工作任务已启动: {task.id}")
        return True

    async def _work_loop(self) -> None:
        """工作任务处理循环"""
        logger.info("工作任务处理循环已启动")

        while True:
            try:
                # 获取任务
                task = await self._task_queue.get()

                # 执行任务
                await self._execute_work_task(task)

                # 标记完成
                self._task_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"工作任务处理异常: {e}")

    async def _execute_work_task(self, task: WorkTask) -> None:
        """
        执行工作任务
        
        Args:
            task: 工作任务
        """
        if self._logger:
            self._logger.log_work_mode(
                event_type=LogEventType.TASK_STARTED,
                task_id=task.id,
                content=f"开始执行任务: {task.description}",
            )

        logger.info(f"[WORK] 开始执行任务: {task.id} - {task.description}")

        try:
            # 定义工作阶段
            phases = [
                {"name": "analyze", "description": "分析任务"},
                {"name": "locate", "description": "定位目标"},
                {"name": "execute", "description": "执行工作"},
                {"name": "verify", "description": "验证结果"},
                {"name": "report", "description": "生成报告"},
            ]

            task.phases = phases

            # 执行每个阶段
            for phase in phases:
                task.current_phase = phase["name"]
                logger.info(f"[WORK] {task.id} - 执行阶段: {phase['description']}")

                # 执行阶段
                phase_result = await self._execute_phase(task, phase)

                phase["status"] = "completed" if phase_result["success"] else "failed"
                phase["result"] = phase_result.get("output", "")

                logger.info(
                    f"[WORK] {task.id} - 阶段完成: {phase['description']} - "
                    f"{'成功' if phase_result['success'] else '失败'}"
                )

                # 报告阶段进度
                if self._logger:
                    self._logger.log_phase_report(
                        task_id=task.id,
                        phase=phase["name"],
                        status=phase["status"],
                        content=phase["result"],
                    )

                # 调用报告回调
                if self._report_callback:
                    try:
                        if asyncio.iscoroutinefunction(self._report_callback):
                            await self._report_callback(task, phase, phase_result)
                        else:
                            self._report_callback(task, phase, phase_result)
                    except Exception as e:
                        logger.error(f"报告回调执行失败: {e}")

                # 如果阶段失败，终止任务
                if not phase_result["success"]:
                    raise Exception(phase_result.get("error", "阶段执行失败"))

            # 任务完成
            task.status = "completed"
            task.completed_at = datetime.now().isoformat()
            task.result = "任务执行成功"

            self.state.completed_tasks += 1

            if self._logger:
                self._logger.log_work_mode(
                    event_type=LogEventType.TASK_COMPLETED,
                    task_id=task.id,
                    content=f"任务完成: {task.description}",
                )

            logger.info(f"[WORK] 任务完成: {task.id} - {task.description}")

        except Exception as e:
            task.status = "failed"
            task.completed_at = datetime.now().isoformat()
            task.error = str(e)

            self.state.failed_tasks += 1

            if self._logger:
                self._logger.log_work_mode(
                    event_type=LogEventType.TASK_FAILED,
                    task_id=task.id,
                    content=f"任务失败: {str(e)}",
                )

            logger.error(f"[WORK] 任务失败: {task.id} - {e}")

        finally:
            # 从活动任务列表移除
            if task.id in self.state.active_tasks:
                self.state.active_tasks.remove(task.id)

            self._save_state()

    async def _execute_phase(
        self,
        task: WorkTask,
        phase: dict[str, Any],
    ) -> dict[str, Any]:
        """
        执行工作阶段
        
        Args:
            task: 工作任务
            phase: 阶段信息
            
        Returns:
            执行结果
        """
        phase_name = phase["name"]

        # 分析阶段
        if phase_name == "analyze":
            return await self._phase_analyze(task)

        # 定位阶段
        elif phase_name == "locate":
            return await self._phase_locate(task)

        # 执行阶段
        elif phase_name == "execute":
            return await self._phase_execute(task)

        # 验证阶段
        elif phase_name == "verify":
            return await self._phase_verify(task)

        # 报告阶段
        elif phase_name == "report":
            return await self._phase_report(task)

        else:
            return {"success": False, "error": f"未知阶段: {phase_name}"}

    async def _phase_analyze(self, task: WorkTask) -> dict[str, Any]:
        """
        分析阶段
        
        智能分析任务内容，识别任务类型、涉及文件和复杂度。
        
        Args:
            task: 工作任务
            
        Returns:
            分析结果
        """
        logger.info(f"[WORK] 分析任务: {task.description}")

        analysis_result = {
            "success": True,
            "output": "",
            "task_type": "general",
            "file_types": [],
            "complexity": "medium",
            "estimated_steps": 3,
            "keywords_found": [],
            "suggested_actions": [],
            "target_subfolder": task.target_subfolder,
        }

        task_desc_lower = task.description.lower()

        task_type_patterns = {
            "create": ["创建", "新建", "添加", "实现", "开发", "create", "add", "new", "implement", "develop"],
            "modify": ["修改", "更新", "编辑", "重构", "modify", "update", "edit", "refactor", "change"],
            "delete": ["删除", "移除", "清理", "delete", "remove", "clean", "drop"],
            "query": ["查询", "搜索", "查找", "分析", "query", "search", "find", "analyze", "check"],
            "fix": ["修复", "解决", "修正", "fix", "resolve", "patch", "bug"],
            "test": ["测试", "单元测试", "集成测试", "test", "unit test", "integration test"],
            "document": ["文档", "注释", "说明", "document", "comment", "readme", "doc"],
            "config": ["配置", "设置", "环境", "config", "setting", "environment", "setup"],
        }

        detected_types = []
        for task_type, patterns in task_type_patterns.items():
            for pattern in patterns:
                if pattern in task_desc_lower:
                    detected_types.append(task_type)
                    analysis_result["keywords_found"].append(pattern)
                    break

        if detected_types:
            analysis_result["task_type"] = detected_types[0] if len(detected_types) == 1 else "mixed"
            analysis_result["detected_types"] = list(set(detected_types))

        file_type_patterns = {
            "python": [".py", "python", "django", "flask", "fastapi"],
            "javascript": [".js", ".jsx", "javascript", "node", "react", "vue", "angular"],
            "typescript": [".ts", ".tsx", "typescript"],
            "html": [".html", ".htm", "html"],
            "css": [".css", ".scss", ".sass", ".less", "css", "style"],
            "json": [".json", "json"],
            "yaml": [".yaml", ".yml", "yaml"],
            "markdown": [".md", "markdown", "readme"],
            "sql": [".sql", "sql", "database", "query"],
            "shell": [".sh", ".bash", ".ps1", "shell", "script"],
            "docker": ["dockerfile", "docker", "container"],
            "config": [".ini", ".toml", ".cfg", ".env", "config"],
        }

        detected_file_types = []
        for file_type, patterns in file_type_patterns.items():
            for pattern in patterns:
                if pattern in task_desc_lower:
                    detected_file_types.append(file_type)
                    break

        analysis_result["file_types"] = list(set(detected_file_types)) if detected_file_types else ["unknown"]

        complexity_indicators = {
            "high": ["架构", "系统", "重构", "迁移", "集成", "architecture", "system", "refactor", "migration", "integration", "复杂"],
            "low": ["简单", "快速", "小", "simple", "quick", "small", "minor", "简单修改"],
        }

        for indicator in complexity_indicators["high"]:
            if indicator in task_desc_lower:
                analysis_result["complexity"] = "high"
                analysis_result["estimated_steps"] = 5
                break
        else:
            for indicator in complexity_indicators["low"]:
                if indicator in task_desc_lower:
                    analysis_result["complexity"] = "low"
                    analysis_result["estimated_steps"] = 2
                    break
            else:
                analysis_result["complexity"] = "medium"
                analysis_result["estimated_steps"] = 3

        action_suggestions = {
            "create": ["分析需求", "设计结构", "创建文件", "实现功能", "测试验证"],
            "modify": ["定位文件", "分析代码", "修改内容", "测试验证"],
            "delete": ["确认目标", "备份检查", "执行删除", "验证结果"],
            "query": ["收集信息", "分析数据", "生成报告"],
            "fix": ["定位问题", "分析原因", "修复代码", "测试验证"],
            "test": ["分析测试目标", "编写测试用例", "执行测试", "生成报告"],
            "document": ["分析文档需求", "收集信息", "编写文档", "审核完善"],
            "config": ["分析配置需求", "确定配置项", "修改配置", "验证配置"],
        }

        task_type = analysis_result["task_type"]
        if task_type in action_suggestions:
            analysis_result["suggested_actions"] = action_suggestions[task_type]
        elif task_type == "mixed":
            all_actions = []
            for t in analysis_result.get("detected_types", []):
                if t in action_suggestions:
                    all_actions.extend(action_suggestions[t])
            analysis_result["suggested_actions"] = list(dict.fromkeys(all_actions))
        else:
            analysis_result["suggested_actions"] = ["分析任务", "执行操作", "验证结果"]

        target_path = self.working_dir / task.target_subfolder
        if target_path.exists():
            try:
                file_count = sum(1 for _ in target_path.rglob("*") if _.is_file())
                dir_count = sum(1 for _ in target_path.rglob("*") if _.is_dir())
                analysis_result["target_stats"] = {
                    "exists": True,
                    "file_count": file_count,
                    "dir_count": dir_count,
                    "path": str(target_path),
                }
            except Exception as e:
                logger.warning(f"无法获取目标目录统计: {e}")
                analysis_result["target_stats"] = {"exists": True, "path": str(target_path)}
        else:
            analysis_result["target_stats"] = {"exists": False, "path": str(target_path)}

        output_lines = [
            f"✅ 任务分析完成",
            f"",
            f"**任务类型**: {analysis_result['task_type']}",
            f"**涉及文件类型**: {', '.join(analysis_result['file_types'])}",
            f"**复杂度**: {analysis_result['complexity']}",
            f"**预计步骤**: {analysis_result['estimated_steps']}",
            f"",
            f"**建议操作**:",
        ]
        for i, action in enumerate(analysis_result["suggested_actions"], 1):
            output_lines.append(f"  {i}. {action}")

        if analysis_result.get("target_stats"):
            stats = analysis_result["target_stats"]
            output_lines.append(f"")
            output_lines.append(f"**目标目录**: {stats['path']}")
            if stats.get("exists"):
                output_lines.append(f"  - 文件数: {stats.get('file_count', 'N/A')}")
                output_lines.append(f"  - 目录数: {stats.get('dir_count', 'N/A')}")

        analysis_result["output"] = "\n".join(output_lines)

        task.metadata["analysis"] = analysis_result

        logger.info(f"[WORK] 任务分析完成: 类型={analysis_result['task_type']}, 复杂度={analysis_result['complexity']}")

        return analysis_result

    async def _phase_locate(self, task: WorkTask) -> dict[str, Any]:
        """定位阶段"""
        target_path = self.working_dir / task.target_subfolder

        if not target_path.exists():
            # 尝试自动检测
            if self.config.auto_detect_subfolders:
                detected = self._detect_subfolder(task.description)
                if detected:
                    task.target_subfolder = detected
                    target_path = self.working_dir / detected

        if target_path.exists():
            return {
                "success": True,
                "output": f"已定位目标: {task.target_subfolder}",
                "path": str(target_path),
            }
        else:
            # 目标不存在，但继续执行（使用工作目录）
            logger.warning(f"目标子文件夹不存在: {task.target_subfolder}，将使用工作目录")
            return {
                "success": True,
                "output": f"目标子文件夹不存在，将使用工作目录: {self.working_dir}",
                "path": str(self.working_dir),
                "warning": f"目标子文件夹不存在: {task.target_subfolder}",
            }

    async def _phase_execute(self, task: WorkTask) -> dict[str, Any]:
        """
        执行阶段
        
        根据执行模式选择不同的执行方式：
        - SIMULATION: 模拟执行，不调用真实 AI
        - SINGLE_AGENT: 使用 FoxCodeAgent 执行
        - MULTI_AGENT: 使用 MultiAgentOrchestrator 协调多代理执行
        
        Args:
            task: 工作任务
            
        Returns:
            执行结果
        """
        logger.info(f"[WORK] 执行任务: {task.description}")
        logger.info(f"[WORK] 目标路径: {task.target_subfolder}")
        logger.info(f"[WORK] 执行模式: {self.execution_mode.value}")

        # 根据执行模式选择执行方式
        if self.execution_mode == AgentExecutionMode.SIMULATION:
            return await self._phase_execute_simulation(task)
        elif self.execution_mode == AgentExecutionMode.SINGLE_AGENT:
            return await self._phase_execute_single_agent(task)
        elif self.execution_mode == AgentExecutionMode.MULTI_AGENT:
            return await self._phase_execute_multi_agent(task)
        else:
            return {
                "success": False,
                "error": f"未知的执行模式: {self.execution_mode.value}",
            }

    async def _phase_execute_simulation(self, task: WorkTask) -> dict[str, Any]:
        """
        模拟执行模式
        
        不调用真实 AI，通过智能分析任务生成模拟执行过程。
        包括文件扫描、代码分析、模拟操作等功能。
        
        Args:
            task: 工作任务
            
        Returns:
            执行结果
        """
        import random
        from datetime import datetime

        execution_log = []
        execution_log.append(f"🕐 开始时间: {datetime.now().isoformat()}")
        execution_log.append(f"")
        execution_log.append(f"📋 任务信息:")
        execution_log.append(f"  - 描述: {task.description}")
        execution_log.append(f"  - 目标路径: {task.target_subfolder}")
        execution_log.append(f"  - 执行模式: 模拟模式 (SIMULATION)")
        execution_log.append(f"")

        analysis = task.metadata.get("analysis", {})
        task_type = analysis.get("task_type", "general")
        file_types = analysis.get("file_types", ["unknown"])
        complexity = analysis.get("complexity", "medium")
        suggested_actions = analysis.get("suggested_actions", ["分析任务", "执行操作", "验证结果"])

        execution_log.append(f"📊 任务分析结果:")
        execution_log.append(f"  - 类型: {task_type}")
        execution_log.append(f"  - 文件类型: {', '.join(file_types)}")
        execution_log.append(f"  - 复杂度: {complexity}")
        execution_log.append(f"")

        target_path = self.working_dir / task.target_subfolder
        scanned_files = []
        scanned_dirs = []

        execution_log.append(f"🔍 扫描目标目录...")
        if target_path.exists():
            try:
                for item in target_path.rglob("*"):
                    if item.is_file():
                        scanned_files.append(str(item.relative_to(target_path)))
                    elif item.is_dir():
                        scanned_dirs.append(str(item.relative_to(target_path)))
                
                execution_log.append(f"  ✅ 扫描完成")
                execution_log.append(f"  - 发现文件: {len(scanned_files)} 个")
                execution_log.append(f"  - 发现目录: {len(scanned_dirs)} 个")
                
                if scanned_files:
                    execution_log.append(f"  - 主要文件:")
                    for f in scanned_files[:10]:
                        execution_log.append(f"    • {f}")
                    if len(scanned_files) > 10:
                        execution_log.append(f"    ... 还有 {len(scanned_files) - 10} 个文件")
            except Exception as e:
                execution_log.append(f"  ⚠️ 扫描失败: {e}")
        else:
            execution_log.append(f"  ⚠️ 目标目录不存在，将创建")
            scanned_dirs.append(task.target_subfolder)
        execution_log.append(f"")

        execution_log.append(f"⚙️ 执行模拟操作...")
        simulated_operations = []
        
        for i, action in enumerate(suggested_actions, 1):
            await asyncio.sleep(0.1)
            operation_detail = await self._simulate_operation(action, task, target_path, scanned_files)
            simulated_operations.append({
                "step": i,
                "action": action,
                "detail": operation_detail,
                "status": "completed",
            })
            execution_log.append(f"  {i}. {action}")
            for line in operation_detail.split("\n"):
                if line.strip():
                    execution_log.append(f"     {line}")
        
        execution_log.append(f"")

        execution_log.append(f"📁 模拟文件变更:")
        simulated_changes = self._generate_simulated_changes(task, task_type, file_types, scanned_files)
        for change in simulated_changes:
            execution_log.append(f"  • {change}")
        execution_log.append(f"")

        execution_log.append(f"📈 执行统计:")
        execution_log.append(f"  - 执行步骤: {len(simulated_operations)}")
        execution_log.append(f"  - 模拟变更: {len(simulated_changes)} 个文件")
        execution_log.append(f"  - 扫描文件: {len(scanned_files)} 个")
        execution_log.append(f"")

        execution_log.append(f"💡 后续建议:")
        suggestions = self._generate_suggestions(task_type, complexity, scanned_files)
        for suggestion in suggestions:
            execution_log.append(f"  • {suggestion}")
        execution_log.append(f"")

        execution_log.append(f"🕐 完成时间: {datetime.now().isoformat()}")
        execution_log.append(f"")
        execution_log.append(f"⚠️ 注意: 这是模拟执行，实际文件未被修改。")
        execution_log.append(f"   要执行真实操作，请切换到 SINGLE_AGENT 或 MULTI_AGENT 模式。")

        return {
            "success": True,
            "output": "\n".join(execution_log),
            "simulated_operations": simulated_operations,
            "simulated_changes": simulated_changes,
            "scanned_files": len(scanned_files),
            "scanned_dirs": len(scanned_dirs),
        }

    async def _simulate_operation(
        self,
        action: str,
        task: WorkTask,
        target_path: Path,
        existing_files: list[str],
    ) -> str:
        """
        模拟单个操作
        
        Args:
            action: 操作名称
            task: 工作任务
            target_path: 目标路径
            existing_files: 现有文件列表
            
        Returns:
            操作详情
        """
        action_lower = action.lower()
        
        if "分析" in action or "analyze" in action_lower:
            return f"分析任务需求: {task.description[:50]}..."
        
        elif "定位" in action or "locate" in action_lower:
            if existing_files:
                return f"定位到 {len(existing_files)} 个相关文件"
            return f"目标目录: {target_path}"
        
        elif "创建" in action or "create" in action_lower:
            return f"模拟创建新文件结构"
        
        elif "修改" in action or "修改" in action or "update" in action_lower or "edit" in action_lower:
            if existing_files:
                return f"模拟修改文件: {existing_files[0] if existing_files else 'new_file'}"
            return f"模拟修改操作"
        
        elif "删除" in action or "delete" in action_lower or "remove" in action_lower:
            return f"模拟删除操作 (未实际执行)"
        
        elif "测试" in action or "test" in action_lower:
            return f"模拟测试执行 - 预计通过"
        
        elif "验证" in action or "verify" in action_lower:
            return f"验证操作完成 - 检查通过"
        
        elif "设计" in action or "design" in action_lower:
            return f"设计文件结构和接口"
        
        elif "实现" in action or "implement" in action_lower:
            return f"模拟实现功能代码"
        
        elif "备份" in action or "backup" in action_lower:
            return f"模拟备份当前状态"
        
        elif "生成" in action or "generate" in action_lower:
            return f"模拟生成报告/文档"
        
        elif "收集" in action or "collect" in action_lower:
            return f"收集相关信息完成"
        
        elif "编写" in action or "write" in action_lower:
            return f"模拟编写内容"
        
        elif "审核" in action or "review" in action_lower:
            return f"模拟审核完成"
        
        elif "确定" in action or "confirm" in action_lower:
            return f"确定配置项完成"
        
        else:
            return f"执行: {action}"

    def _generate_simulated_changes(
        self,
        task: WorkTask,
        task_type: str,
        file_types: list[str],
        existing_files: list[str],
    ) -> list[str]:
        """
        生成模拟文件变更列表
        
        Args:
            task: 工作任务
            task_type: 任务类型
            file_types: 文件类型
            existing_files: 现有文件列表
            
        Returns:
            模拟变更列表
        """
        changes = []
        task_desc = task.description[:30]
        
        file_extensions = {
            "python": ".py",
            "javascript": ".js",
            "typescript": ".ts",
            "html": ".html",
            "css": ".css",
            "json": ".json",
            "yaml": ".yaml",
            "markdown": ".md",
            "sql": ".sql",
            "shell": ".sh",
            "docker": "Dockerfile",
            "config": ".conf",
        }

        if task_type == "create":
            for ft in file_types[:3]:
                ext = file_extensions.get(ft, ".txt")
                if ft == "python":
                    changes.append(f"[新建] {task.target_subfolder}/new_module{ext}")
                    changes.append(f"[新建] {task.target_subfolder}/tests/test_new_module.py")
                elif ft == "javascript":
                    changes.append(f"[新建] {task.target_subfolder}/src/newComponent.jsx")
                    changes.append(f"[新建] {task.target_subfolder}/src/newComponent.test.js")
                elif ft == "typescript":
                    changes.append(f"[新建] {task.target_subfolder}/src/newModule.ts")
                    changes.append(f"[新建] {task.target_subfolder}/src/newModule.test.ts")
                else:
                    changes.append(f"[新建] {task.target_subfolder}/new_file{ext}")
        
        elif task_type == "modify":
            if existing_files:
                for f in existing_files[:3]:
                    changes.append(f"[修改] {task.target_subfolder}/{f}")
            else:
                changes.append(f"[修改] {task.target_subfolder}/main_file (模拟)")
        
        elif task_type == "delete":
            if existing_files:
                changes.append(f"[删除] {task.target_subfolder}/{existing_files[0]} (模拟)")
            else:
                changes.append(f"[删除] {task.target_subfolder}/old_file (模拟)")
        
        elif task_type == "fix":
            if existing_files:
                changes.append(f"[修复] {task.target_subfolder}/{existing_files[0]}")
            else:
                changes.append(f"[修复] {task.target_subfolder}/buggy_file.py (模拟)")
        
        elif task_type == "test":
            changes.append(f"[新建] {task.target_subfolder}/tests/test_new.py")
            changes.append(f"[修改] {task.target_subfolder}/tests/__init__.py")
        
        elif task_type == "document":
            changes.append(f"[新建] {task.target_subfolder}/docs/README.md")
            changes.append(f"[修改] {task.target_subfolder}/README.md")
        
        elif task_type == "config":
            changes.append(f"[修改] {task.target_subfolder}/config/settings.py")
            changes.append(f"[新建] {task.target_subfolder}/.env.example")
        
        else:
            changes.append(f"[操作] {task.target_subfolder}/ (模拟变更)")

        return changes[:5]

    def _generate_suggestions(
        self,
        task_type: str,
        complexity: str,
        existing_files: list[str],
    ) -> list[str]:
        """
        生成后续建议
        
        Args:
            task_type: 任务类型
            complexity: 复杂度
            existing_files: 现有文件列表
            
        Returns:
            建议列表
        """
        suggestions = []
        
        if complexity == "high":
            suggestions.append("建议分阶段执行，先完成核心功能")
            suggestions.append("考虑添加单元测试覆盖")
        
        if task_type == "create":
            suggestions.append("创建完成后运行测试验证")
            suggestions.append("添加必要的文档说明")
        elif task_type == "modify":
            suggestions.append("修改前建议备份原文件")
            suggestions.append("修改后进行回归测试")
        elif task_type == "fix":
            suggestions.append("修复后添加相关测试用例")
            suggestions.append("记录问题和解决方案")
        elif task_type == "test":
            suggestions.append("确保测试覆盖率达标")
            suggestions.append("运行完整测试套件")
        
        if len(existing_files) > 20:
            suggestions.append("项目较大，建议使用版本控制")
        
        if not suggestions:
            suggestions.append("任务执行完成，建议验证结果")
            suggestions.append("如有问题可重新执行或切换到真实模式")
        
        return suggestions

    async def _phase_execute_single_agent(self, task: WorkTask) -> dict[str, Any]:
        """
        单代理执行模式
        
        使用 FoxCodeAgent 执行任务。
        
        Args:
            task: 工作任务
            
        Returns:
            执行结果
        """
        logger.info(f"[WORK] 单代理模式: 正在获取 Agent...")

        agent = await self._get_agent()

        if agent is None:
            logger.warning("[WORK] 无法获取 Agent，回退到模拟模式")
            return await self._phase_execute_simulation(task)

        try:
            # 构建执行提示
            target_path = self.working_dir / task.target_subfolder

            prompt = self._build_execution_prompt(task, target_path)

            logger.info(f"[WORK] 发送任务到 Agent: {task.id}")
            logger.info(f"[WORK] 目标路径: {target_path}")

            # 收集 Agent 响应
            response_parts = []
            async for chunk in agent.chat(prompt):
                response_parts.append(chunk)

            full_response = "".join(response_parts)

            logger.info(f"[WORK] Agent 执行完成: {task.id}")
            logger.info(f"[WORK] 响应长度: {len(full_response)} 字符")

            return {
                "success": True,
                "output": full_response,
                "agent_mode": "single_agent",
            }

        except Exception as e:
            logger.error(f"[WORK] Agent 执行失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Agent 执行失败: {str(e)}",
                "output": "",
            }

    async def _phase_execute_multi_agent(self, task: WorkTask) -> dict[str, Any]:
        """
        多代理执行模式
        
        使用 MultiAgentOrchestrator 协调多代理执行任务。
        
        Args:
            task: 工作任务
            
        Returns:
            执行结果
        """
        orchestrator = await self._get_orchestrator()

        if orchestrator is None:
            logger.warning("无法获取 Orchestrator，回退到单代理模式")
            return await self._phase_execute_single_agent(task)

        try:
            from foxcode.core.orchestrator import TaskItem

            target_path = self.working_dir / task.target_subfolder

            # 创建任务项
            task_item = TaskItem(
                id=task.id,
                description=task.description,
                target_path=str(target_path),
                metadata=task.metadata,
            )

            logger.info(f"[WORK] 分配任务到多代理协调器: {task.id}")

            # 分配任务
            orchestrator.assign_task(task_item)

            # 执行任务
            result = await orchestrator.execute_current_task()

            logger.info(f"[WORK] 多代理执行完成: {task.id}")

            return {
                "success": result.success,
                "output": result.output or "",
                "error": result.error,
                "agent_mode": "multi_agent",
                "revisions": result.revisions,
            }

        except Exception as e:
            logger.error(f"[WORK] 多代理执行失败: {e}")
            return {
                "success": False,
                "error": f"多代理执行失败: {str(e)}",
                "output": "",
            }

    def _build_execution_prompt(self, task: WorkTask, target_path: Path) -> str:
        """
        构建执行提示
        
        根据任务信息构建发送给 Agent 的提示。
        
        Args:
            task: 工作任务
            target_path: 目标路径
            
        Returns:
            执行提示
        """
        prompt_parts = [
            f"# 任务: {task.description}",
            "",
            f"**任务 ID**: {task.id}",
            f"**目标路径**: {target_path}",
            "",
            "## 任务要求",
            "",
            f"请在 `{target_path}` 目录下完成以下任务:",
            f"- {task.description}",
            "",
            "## 执行指南",
            "",
            "1. 首先了解目标目录的结构",
            "2. 分析任务需求，制定执行计划",
            "3. 按步骤执行任务",
            "4. 确保代码质量和错误处理",
            "5. 完成后验证结果",
        ]

        # 添加元数据信息
        if task.metadata:
            prompt_parts.extend([
                "",
                "## 附加信息",
                "",
            ])
            for key, value in task.metadata.items():
                prompt_parts.append(f"- **{key}**: {value}")

        return "\n".join(prompt_parts)

    async def _phase_verify(self, task: WorkTask) -> dict[str, Any]:
        """
        验证阶段
        
        智能验证任务执行结果，包括文件检查、代码语法检查、
        目录结构验证等。
        
        Args:
            task: 工作任务
            
        Returns:
            验证结果
        """
        from datetime import datetime

        logger.info(f"[WORK] 验证任务结果: {task.id}")

        verify_result = {
            "success": True,
            "output": "",
            "checks": [],
            "warnings": [],
            "errors": [],
        }

        verify_log = []
        verify_log.append(f"🔍 开始验证任务: {task.id}")
        verify_log.append(f"🕐 验证时间: {datetime.now().isoformat()}")
        verify_log.append(f"")

        target_path = self.working_dir / task.target_subfolder
        analysis = task.metadata.get("analysis", {})
        task_type = analysis.get("task_type", "general")

        verify_log.append(f"📁 检查目标目录...")
        if target_path.exists():
            verify_result["checks"].append({"name": "目录存在", "status": "passed"})
            verify_log.append(f"  ✅ 目标目录存在: {target_path}")
            
            try:
                file_count = sum(1 for _ in target_path.rglob("*") if _.is_file())
                dir_count = sum(1 for _ in target_path.rglob("*") if _.is_dir())
                verify_log.append(f"  ✅ 文件数量: {file_count}")
                verify_log.append(f"  ✅ 目录数量: {dir_count}")
                verify_result["checks"].append({
                    "name": "目录结构", 
                    "status": "passed",
                    "file_count": file_count,
                    "dir_count": dir_count,
                })
            except Exception as e:
                verify_log.append(f"  ⚠️ 无法统计目录: {e}")
                verify_result["warnings"].append(f"目录统计失败: {e}")
        else:
            verify_result["checks"].append({"name": "目录存在", "status": "warning"})
            verify_log.append(f"  ⚠️ 目标目录不存在: {target_path}")
            verify_result["warnings"].append("目标目录不存在")

        verify_log.append(f"")
        verify_log.append(f"📝 检查文件类型...")
        file_type_checks = self._verify_file_types(target_path, analysis.get("file_types", []))
        for check in file_type_checks:
            verify_result["checks"].append(check)
            if check["status"] == "passed":
                verify_log.append(f"  ✅ {check['name']}")
            elif check["status"] == "warning":
                verify_log.append(f"  ⚠️ {check['name']}: {check.get('message', '')}")
                verify_result["warnings"].append(check.get("message", ""))
            else:
                verify_log.append(f"  ❌ {check['name']}: {check.get('message', '')}")
                verify_result["errors"].append(check.get("message", ""))

        verify_log.append(f"")
        verify_log.append(f"🔧 检查代码语法...")
        syntax_checks = await self._verify_code_syntax(target_path)
        for check in syntax_checks:
            verify_result["checks"].append(check)
            if check["status"] == "passed":
                verify_log.append(f"  ✅ {check['name']}")
            elif check["status"] == "warning":
                verify_log.append(f"  ⚠️ {check['name']}: {check.get('message', '')}")
                verify_result["warnings"].append(check.get("message", ""))
            else:
                verify_log.append(f"  ❌ {check['name']}: {check.get('message', '')}")
                verify_result["errors"].append(check.get("message", ""))

        verify_log.append(f"")
        verify_log.append(f"📋 检查任务完成度...")
        completion_check = self._verify_task_completion(task, task_type, target_path)
        verify_result["checks"].append(completion_check)
        if completion_check["status"] == "passed":
            verify_log.append(f"  ✅ {completion_check['name']}")
        else:
            verify_log.append(f"  ⚠️ {completion_check['name']}: {completion_check.get('message', '')}")
            verify_result["warnings"].append(completion_check.get("message", ""))

        verify_log.append(f"")
        verify_log.append(f"📊 验证统计:")
        passed_count = sum(1 for c in verify_result["checks"] if c["status"] == "passed")
        warning_count = sum(1 for c in verify_result["checks"] if c["status"] == "warning")
        failed_count = sum(1 for c in verify_result["checks"] if c["status"] == "failed")
        total_checks = len(verify_result["checks"])

        verify_log.append(f"  - 总检查项: {total_checks}")
        verify_log.append(f"  - 通过: {passed_count}")
        verify_log.append(f"  - 警告: {warning_count}")
        verify_log.append(f"  - 失败: {failed_count}")
        verify_log.append(f"")

        if failed_count > 0:
            verify_result["success"] = False
            verify_log.append(f"❌ 验证结果: 存在失败项")
        elif warning_count > 0:
            verify_log.append(f"⚠️ 验证结果: 通过（存在警告）")
        else:
            verify_log.append(f"✅ 验证结果: 全部通过")

        verify_result["output"] = "\n".join(verify_log)
        verify_result["stats"] = {
            "total": total_checks,
            "passed": passed_count,
            "warnings": warning_count,
            "failed": failed_count,
        }

        logger.info(f"[WORK] 验证完成: 通过={passed_count}, 警告={warning_count}, 失败={failed_count}")

        return verify_result

    def _verify_file_types(self, target_path: Path, expected_types: list[str]) -> list[dict]:
        """
        验证文件类型
        
        Args:
            target_path: 目标路径
            expected_types: 预期的文件类型
            
        Returns:
            检查结果列表
        """
        checks = []

        if not target_path.exists():
            checks.append({
                "name": "文件类型检查",
                "status": "warning",
                "message": "目标目录不存在",
            })
            return checks

        type_extensions = {
            "python": [".py"],
            "javascript": [".js", ".jsx", ".mjs"],
            "typescript": [".ts", ".tsx"],
            "html": [".html", ".htm"],
            "css": [".css", ".scss", ".sass", ".less"],
            "json": [".json"],
            "yaml": [".yaml", ".yml"],
            "markdown": [".md"],
            "sql": [".sql"],
            "shell": [".sh", ".bash", ".ps1"],
            "docker": ["Dockerfile", ".dockerignore"],
            "config": [".ini", ".toml", ".cfg", ".env", ".conf"],
        }

        found_types = set()
        try:
            for file_path in target_path.rglob("*"):
                if file_path.is_file():
                    ext = file_path.suffix.lower()
                    name = file_path.name
                    for ftype, extensions in type_extensions.items():
                        if ext in extensions or name in extensions:
                            found_types.add(ftype)
                            break
        except Exception as e:
            checks.append({
                "name": "文件类型扫描",
                "status": "warning",
                "message": f"扫描失败: {e}",
            })
            return checks

        if expected_types and expected_types != ["unknown"]:
            for expected in expected_types:
                if expected in found_types:
                    checks.append({
                        "name": f"文件类型: {expected}",
                        "status": "passed",
                        "message": f"发现 {expected} 文件",
                    })
                else:
                    checks.append({
                        "name": f"文件类型: {expected}",
                        "status": "warning",
                        "message": f"未发现 {expected} 文件",
                    })

        if found_types:
            checks.append({
                "name": "发现文件类型",
                "status": "passed",
                "message": f"类型: {', '.join(found_types)}",
            })
        else:
            checks.append({
                "name": "文件类型检查",
                "status": "warning",
                "message": "未发现任何已知类型的文件",
            })

        return checks

    async def _verify_code_syntax(self, target_path: Path) -> list[dict]:
        """
        验证代码语法
        
        Args:
            target_path: 目标路径
            
        Returns:
            检查结果列表
        """
        checks = []

        if not target_path.exists():
            return checks

        python_files = list(target_path.rglob("*.py"))[:5]
        if python_files:
            python_valid = True
            for py_file in python_files:
                try:
                    with open(py_file, encoding="utf-8", errors="ignore") as f:
                        source = f.read()
                    compile(source, str(py_file), "exec")
                except SyntaxError as e:
                    python_valid = False
                    checks.append({
                        "name": f"Python 语法: {py_file.name}",
                        "status": "warning",
                        "message": f"语法错误: 行 {e.lineno}",
                    })
                except Exception as e:
                    pass

            if python_valid:
                checks.append({
                    "name": "Python 语法检查",
                    "status": "passed",
                    "message": f"检查了 {len(python_files)} 个文件",
                })

        json_files = list(target_path.rglob("*.json"))[:5]
        if json_files:
            import json
            json_valid = True
            for json_file in json_files:
                try:
                    with open(json_file, encoding="utf-8", errors="ignore") as f:
                        json.load(f)
                except json.JSONDecodeError as e:
                    json_valid = False
                    checks.append({
                        "name": f"JSON 语法: {json_file.name}",
                        "status": "warning",
                        "message": f"JSON 错误: 行 {e.lineno}",
                    })
                except Exception as e:
                    pass

            if json_valid:
                checks.append({
                    "name": "JSON 语法检查",
                    "status": "passed",
                    "message": f"检查了 {len(json_files)} 个文件",
                })

        yaml_files = list(target_path.rglob("*.yaml")) + list(target_path.rglob("*.yml"))
        yaml_files = yaml_files[:5]
        if yaml_files:
            try:
                import yaml
                yaml_valid = True
                for yaml_file in yaml_files:
                    try:
                        with open(yaml_file, encoding="utf-8", errors="ignore") as f:
                            yaml.safe_load(f)
                    except yaml.YAMLError as e:
                        yaml_valid = False
                        checks.append({
                            "name": f"YAML 语法: {yaml_file.name}",
                            "status": "warning",
                            "message": f"YAML 错误",
                        })
                    except Exception as e:
                        pass

                if yaml_valid:
                    checks.append({
                        "name": "YAML 语法检查",
                        "status": "passed",
                        "message": f"检查了 {len(yaml_files)} 个文件",
                    })
            except ImportError:
                pass

        return checks

    def _verify_task_completion(
        self,
        task: WorkTask,
        task_type: str,
        target_path: Path,
    ) -> dict:
        """
        验证任务完成度
        
        Args:
            task: 工作任务
            task_type: 任务类型
            target_path: 目标路径
            
        Returns:
            检查结果
        """
        result = {
            "name": "任务完成度检查",
            "status": "passed",
            "message": "",
        }

        if not target_path.exists():
            result["status"] = "warning"
            result["message"] = "目标目录不存在"
            return result

        if task_type == "create":
            file_count = sum(1 for _ in target_path.rglob("*") if _.is_file())
            if file_count > 0:
                result["message"] = f"发现 {file_count} 个文件"
            else:
                result["status"] = "warning"
                result["message"] = "未发现新创建的文件"

        elif task_type == "modify":
            result["message"] = "修改任务已完成（模拟模式）"

        elif task_type == "delete":
            result["message"] = "删除任务已完成（模拟模式）"

        elif task_type == "test":
            test_files = list(target_path.rglob("test_*.py")) + list(target_path.rglob("*_test.py"))
            if test_files:
                result["message"] = f"发现 {len(test_files)} 个测试文件"
            else:
                result["status"] = "warning"
                result["message"] = "未发现测试文件"

        elif task_type == "document":
            doc_files = list(target_path.rglob("*.md")) + list(target_path.rglob("README*"))
            if doc_files:
                result["message"] = f"发现 {len(doc_files)} 个文档文件"
            else:
                result["status"] = "warning"
                result["message"] = "未发现文档文件"

        else:
            result["message"] = "任务验证完成"

        return result

    async def _phase_report(self, task: WorkTask) -> dict[str, Any]:
        """
        报告阶段
        
        生成详细的任务执行报告，包括执行摘要、阶段详情、
        文件变更、验证结果和后续建议。
        
        Args:
            task: 工作任务
            
        Returns:
            报告结果
        """
        from datetime import datetime

        logger.info(f"[WORK] 生成任务报告: {task.id}")

        report_parts = []

        report_parts.append("=" * 60)
        report_parts.append(f"📋 任务执行报告")
        report_parts.append("=" * 60)
        report_parts.append("")

        report_parts.append("## 基本信息")
        report_parts.append("")
        report_parts.append(f"| 项目 | 值 |")
        report_parts.append(f"|------|-----|")
        report_parts.append(f"| 任务 ID | {task.id} |")
        report_parts.append(f"| 描述 | {task.description[:50]}{'...' if len(task.description) > 50 else ''} |")
        report_parts.append(f"| 目标路径 | {task.target_subfolder} |")
        report_parts.append(f"| 状态 | {task.status} |")
        report_parts.append(f"| 创建时间 | {task.created_at} |")
        if task.started_at:
            report_parts.append(f"| 开始时间 | {task.started_at} |")
        if task.completed_at:
            report_parts.append(f"| 完成时间 | {task.completed_at} |")
        report_parts.append("")

        analysis = task.metadata.get("analysis", {})
        if analysis:
            report_parts.append("## 任务分析")
            report_parts.append("")
            report_parts.append(f"- **任务类型**: {analysis.get('task_type', 'unknown')}")
            report_parts.append(f"- **文件类型**: {', '.join(analysis.get('file_types', ['unknown']))}")
            report_parts.append(f"- **复杂度**: {analysis.get('complexity', 'unknown')}")
            report_parts.append(f"- **预计步骤**: {analysis.get('estimated_steps', 'N/A')}")
            if analysis.get('keywords_found'):
                report_parts.append(f"- **识别关键词**: {', '.join(analysis['keywords_found'][:5])}")
            report_parts.append("")

        report_parts.append("## 执行阶段")
        report_parts.append("")
        report_parts.append("| 阶段 | 状态 | 结果摘要 |")
        report_parts.append("|------|------|----------|")

        phase_summary = []
        for phase in task.phases:
            status_icon = "✅" if phase.get("status") == "completed" else "❌"
            result_summary = phase.get("result", "")[:30]
            if len(phase.get("result", "")) > 30:
                result_summary += "..."
            report_parts.append(f"| {phase['description']} | {status_icon} | {result_summary} |")
            phase_summary.append({
                "name": phase["name"],
                "description": phase["description"],
                "status": phase.get("status", "unknown"),
                "result_length": len(phase.get("result", "")),
            })
        report_parts.append("")

        execution_data = task.metadata.get("execution", {})
        if execution_data.get("simulated_changes"):
            report_parts.append("## 模拟文件变更")
            report_parts.append("")
            for change in execution_data["simulated_changes"]:
                report_parts.append(f"- {change}")
            report_parts.append("")

        verify_data = task.metadata.get("verify", {})
        if verify_data.get("stats"):
            report_parts.append("## 验证结果")
            report_parts.append("")
            stats = verify_data["stats"]
            report_parts.append(f"| 检查项 | 数量 |")
            report_parts.append(f"|--------|------|")
            report_parts.append(f"| 总计 | {stats.get('total', 0)} |")
            report_parts.append(f"| 通过 | {stats.get('passed', 0)} |")
            report_parts.append(f"| 警告 | {stats.get('warnings', 0)} |")
            report_parts.append(f"| 失败 | {stats.get('failed', 0)} |")
            report_parts.append("")

            if verify_data.get("warnings"):
                report_parts.append("**警告项**:")
                for warning in verify_data["warnings"][:3]:
                    report_parts.append(f"- ⚠️ {warning}")
                report_parts.append("")

        report_parts.append("## 执行统计")
        report_parts.append("")

        total_duration = 0
        if task.started_at and task.completed_at:
            try:
                start = datetime.fromisoformat(task.started_at)
                end = datetime.fromisoformat(task.completed_at)
                total_duration = (end - start).total_seconds()
            except Exception:
                pass

        stats_lines = [
            f"- **总阶段数**: {len(task.phases)}",
            f"- **完成阶段**: {sum(1 for p in task.phases if p.get('status') == 'completed')}",
            f"- **执行时长**: {total_duration:.2f} 秒" if total_duration > 0 else "- **执行时长**: N/A",
            f"- **执行模式**: {self.execution_mode.value}",
        ]
        report_parts.extend(stats_lines)
        report_parts.append("")

        report_parts.append("## 后续建议")
        report_parts.append("")
        suggestions = self._generate_final_suggestions(task, analysis, verify_data)
        for suggestion in suggestions:
            report_parts.append(f"- 💡 {suggestion}")
        report_parts.append("")

        if task.error:
            report_parts.append("## 错误信息")
            report_parts.append("")
            report_parts.append("```")
            report_parts.append(task.error)
            report_parts.append("```")
            report_parts.append("")

        report_parts.append("=" * 60)
        report_parts.append(f"报告生成时间: {datetime.now().isoformat()}")
        report_parts.append("=" * 60)

        full_report = "\n".join(report_parts)

        return {
            "success": True,
            "output": full_report,
            "report": full_report,
            "phase_summary": phase_summary,
            "stats": {
                "total_phases": len(task.phases),
                "completed_phases": sum(1 for p in task.phases if p.get("status") == "completed"),
                "duration": total_duration,
                "execution_mode": self.execution_mode.value,
            },
        }

    def _generate_final_suggestions(
        self,
        task: WorkTask,
        analysis: dict,
        verify_data: dict,
    ) -> list[str]:
        """
        生成最终建议
        
        Args:
            task: 工作任务
            analysis: 分析结果
            verify_data: 验证结果
            
        Returns:
            建议列表
        """
        suggestions = []

        if task.status == "completed":
            suggestions.append("任务已成功完成")
        elif task.status == "failed":
            suggestions.append("任务执行失败，请检查错误信息并重试")
            suggestions.append("可以尝试切换到 SINGLE_AGENT 模式获取更详细的执行过程")
        else:
            suggestions.append("任务仍在进行中")

        if self.execution_mode == AgentExecutionMode.SIMULATION:
            suggestions.append("当前为模拟模式，实际文件未修改")
            suggestions.append("要执行真实操作，请切换到 SINGLE_AGENT 或 MULTI_AGENT 模式")

        if verify_data.get("warnings"):
            suggestions.append(f"存在 {len(verify_data['warnings'])} 个警告项，建议检查")

        task_type = analysis.get("task_type", "general")
        if task_type == "create":
            suggestions.append("建议运行测试验证新创建的功能")
            suggestions.append("考虑添加必要的文档说明")
        elif task_type == "modify":
            suggestions.append("建议进行回归测试确保修改不影响其他功能")
        elif task_type == "fix":
            suggestions.append("建议添加测试用例防止问题再次出现")

        complexity = analysis.get("complexity", "medium")
        if complexity == "high":
            suggestions.append("复杂任务建议分阶段验证")
            suggestions.append("考虑使用版本控制跟踪变更")

        if not suggestions:
            suggestions.append("任务执行完成，建议验证结果")

        return suggestions[:5]

    def _detect_subfolder(self, description: str) -> str | None:
        """
        根据任务描述自动检测目标子文件夹
        
        使用多种策略检测目标目录：
        1. 中文关键词匹配
        2. 英文关键词匹配
        3. 文件类型推断
        4. 项目结构分析
        
        Args:
            description: 任务描述
            
        Returns:
            检测到的子文件夹路径，未检测到返回 None
        """
        desc_lower = description.lower()

        keywords_to_folders = {
            "前端": ["src/frontend", "frontend", "web", "client", "src/web", "ui"],
            "后端": ["src/backend", "backend", "server", "api", "src/api", "src/server"],
            "测试": ["tests", "test", "spec", "specs", "__tests__", "src/tests"],
            "文档": ["docs", "doc", "documentation", "wiki"],
            "配置": ["config", "configs", "settings", "src/config"],
            "核心": ["src/core", "core", "src", "lib"],
            "数据库": ["db", "database", "migrations", "src/db", "models"],
            "工具": ["utils", "tools", "helpers", "src/utils", "src/tools"],
            "服务": ["services", "service", "src/services"],
            "组件": ["components", "src/components", "src/views", "pages"],
            "路由": ["routes", "router", "src/routes", "src/router"],
            "静态": ["static", "public", "assets", "src/static"],
            "脚本": ["scripts", "script", "bin"],
            "日志": ["logs", "log"],
            "缓存": ["cache", "temp", "tmp"],
        }

        for keyword, folders in keywords_to_folders.items():
            if keyword in description:
                for folder in folders:
                    if (self.working_dir / folder).exists():
                        logger.debug(f"通过中文关键词 '{keyword}' 检测到目录: {folder}")
                        return folder

        english_keywords = {
            "frontend": ["src/frontend", "frontend", "web", "client", "ui"],
            "backend": ["src/backend", "backend", "server", "api"],
            "test": ["tests", "test", "spec", "__tests__"],
            "doc": ["docs", "doc", "documentation"],
            "config": ["config", "configs", "settings"],
            "core": ["src/core", "core", "src"],
            "database": ["db", "database", "migrations", "models"],
            "util": ["utils", "tools", "helpers", "src/utils"],
            "service": ["services", "service", "src/services"],
            "component": ["components", "src/components", "src/views"],
            "api": ["api", "src/api", "routes", "src/routes"],
            "script": ["scripts", "script", "bin"],
            "static": ["static", "public", "assets"],
        }

        for keyword, folders in english_keywords.items():
            if keyword in desc_lower:
                for folder in folders:
                    if (self.working_dir / folder).exists():
                        logger.debug(f"通过英文关键词 '{keyword}' 检测到目录: {folder}")
                        return folder

        file_type_folders = {
            ".py": ["src", "lib", "app", "backend"],
            ".js": ["src", "frontend", "web", "client", "app"],
            ".ts": ["src", "frontend", "web", "client", "app"],
            ".jsx": ["src", "frontend", "web", "client", "components"],
            ".tsx": ["src", "frontend", "web", "client", "components"],
            ".vue": ["src", "frontend", "web", "client", "views"],
            ".html": ["templates", "public", "static", "web"],
            ".css": ["styles", "css", "static", "src/styles"],
            ".sql": ["db", "database", "migrations", "sql"],
            ".md": ["docs", "doc", "documentation"],
        }

        for ext, folders in file_type_folders.items():
            if ext in desc_lower:
                for folder in folders:
                    if (self.working_dir / folder).exists():
                        logger.debug(f"通过文件类型 '{ext}' 检测到目录: {folder}")
                        return folder

        framework_patterns = {
            "react": ["src", "src/components", "src/pages", "client"],
            "vue": ["src", "src/components", "src/views", "frontend"],
            "angular": ["src", "src/app", "frontend"],
            "django": ["backend", "app", "src", "api"],
            "flask": ["app", "src", "backend", "api"],
            "fastapi": ["app", "src", "backend", "api"],
            "express": ["src", "server", "api", "backend"],
            "next": ["src", "app", "pages", "frontend"],
            "nuxt": ["src", "app", "pages", "frontend"],
        }

        for framework, folders in framework_patterns.items():
            if framework in desc_lower:
                for folder in folders:
                    if (self.working_dir / folder).exists():
                        logger.debug(f"通过框架 '{framework}' 检测到目录: {folder}")
                        return folder

        common_dirs = ["src", "app", "lib", "backend", "frontend", "server", "client", "web"]
        for dir_name in common_dirs:
            dir_path = self.working_dir / dir_name
            if dir_path.exists() and dir_path.is_dir():
                try:
                    file_count = sum(1 for _ in dir_path.rglob("*") if _.is_file())
                    if file_count > 5:
                        logger.debug(f"通过项目结构分析检测到主目录: {dir_name}")
                        return dir_name
                except Exception:
                    pass

        logger.debug(f"未能从描述中检测到目标目录: {description[:50]}...")
        return None

    # ==================== Agent 管理 ====================

    async def _get_agent(self) -> FoxCodeAgent | None:
        """
        获取或创建 FoxCodeAgent 实例
        
        延迟初始化 Agent，只在需要时创建。
        如果没有提供 foxcode_config，返回 None。
        
        Returns:
            FoxCodeAgent 实例，或 None（如果无法创建）
        """
        if self._agent is not None:
            logger.info("[WORK] 使用已存在的 Agent 实例")
            return self._agent

        if self._foxcode_config is None:
            logger.warning("[WORK] 未提供 FoxCode 配置，无法创建 Agent")
            return None

        try:
            from foxcode.core.agent import FoxCodeAgent

            logger.info("[WORK] 正在创建 FoxCodeAgent 实例...")
            logger.info(f"[WORK] 模型配置: {self._foxcode_config.model.model_name}")

            self._agent = FoxCodeAgent(
                config=self._foxcode_config,
                force_mode="coder",  # 使用编码模式
            )

            logger.info("[WORK] 正在初始化 Agent...")
            await self._agent.initialize()

            logger.info("[WORK] FoxCodeAgent 已初始化成功")
            return self._agent

        except Exception as e:
            logger.error(f"[WORK] 创建 FoxCodeAgent 失败: {e}", exc_info=True)
            return None

    async def _get_orchestrator(self) -> MultiAgentOrchestrator | None:
        """
        获取或创建 MultiAgentOrchestrator 实例
        
        延迟初始化多代理协调器，只在需要时创建。
        
        Returns:
            MultiAgentOrchestrator 实例，或 None（如果无法创建）
        """
        if self._orchestrator is not None:
            return self._orchestrator

        agent = await self._get_agent()
        if agent is None:
            return None

        try:
            from foxcode.core.orchestrator import MultiAgentOrchestrator

            self._orchestrator = MultiAgentOrchestrator(
                config=self._foxcode_config,
                session=agent.session,
            )

            logger.info("MultiAgentOrchestrator 已初始化")
            return self._orchestrator

        except Exception as e:
            logger.error(f"创建 MultiAgentOrchestrator 失败: {e}")
            return None

    def set_foxcode_config(self, config: Config) -> None:
        """
        设置 FoxCode 配置
        
        Args:
            config: FoxCode 主配置
        """
        self._foxcode_config = config
        self._agent = None  # 重置 Agent
        self._orchestrator = None  # 重置协调器
        logger.info("FoxCode 配置已更新")

    def set_execution_mode(self, mode: AgentExecutionMode) -> None:
        """
        设置执行模式
        
        Args:
            mode: Agent 执行模式
        """
        self.execution_mode = mode
        logger.info(f"执行模式已切换为: {mode.value}")

    def set_report_callback(self, callback: Callable) -> None:
        """
        设置报告回调函数
        
        Args:
            callback: 回调函数，接收 (task, phase, result) 参数
        """
        self._report_callback = callback

    def get_task(self, task_id: str) -> WorkTask | None:
        """获取工作任务"""
        return self._tasks.get(task_id)

    def list_tasks(
        self,
        status: str | None = None,
        limit: int = 100,
    ) -> list[WorkTask]:
        """
        列出工作任务
        
        Args:
            status: 状态过滤
            limit: 最大返回数量
            
        Returns:
            任务列表
        """
        tasks = list(self._tasks.values())

        if status:
            tasks = [t for t in tasks if t.status == status]

        # 按创建时间排序
        tasks.sort(key=lambda t: t.created_at, reverse=True)

        return tasks[:limit]

    # ==================== 状态和监控 ====================

    def get_status(self) -> dict[str, Any]:
        """
        获取公司模式状态
        
        Returns:
            状态信息字典
        """
        # 更新运行时间
        if self._start_time > 0 and self.state.status == CompanyModeStatus.ENABLED:
            self.state.uptime_seconds = datetime.now().timestamp() - self._start_time

        # 动态计算活动任务（从 _tasks 字典中获取 running 状态的任务）
        running_tasks = [t for t in self._tasks.values() if t.status == "running"]
        self.state.active_tasks = [t.id for t in running_tasks]

        status = self.state.to_dict()

        # 添加 QQbot 统计
        if self._qqbot_service:
            status["qqbot_stats"] = self._qqbot_service.get_stats()

        # 添加安全报告
        if self._security_manager:
            status["security_report"] = self._security_manager.get_security_report()

        # 添加日志统计
        if self._logger:
            status["log_stats"] = self._logger.get_stats()

        return status

    def get_summary_report(self) -> str:
        """
        获取摘要报告
        
        Returns:
            格式化的摘要报告
        """
        lines = [
            "# 公司模式状态报告",
            "",
            f"**状态**: {self.state.status.value}",
            f"**QQbot 状态**: {self.state.qqbot_status.value}",
            f"**运行时间**: {self.state.uptime_seconds:.1f} 秒",
            f"**活动任务**: {len(self.state.active_tasks)}",
            f"**完成任务**: {self.state.completed_tasks}",
            f"**失败任务**: {self.state.failed_tasks}",
            f"**安全事件**: {self.state.security_events}",
            "",
        ]

        # 活动任务
        if self.state.active_tasks:
            lines.append("## 活动任务")
            lines.append("")
            for task_id in self.state.active_tasks:
                task = self._tasks.get(task_id)
                if task:
                    lines.append(f"- {task.id}: {task.description[:50]}... ({task.current_phase})")
            lines.append("")

        # 最近日志摘要
        if self._logger:
            log_summary = self._logger.get_summary_report(hours=1)
            lines.append("## 最近 1 小时日志")
            lines.append("")
            lines.append(f"- 总事件数: {log_summary['total_events']}")
            for event_type, count in log_summary.get("event_distribution", {}).items():
                lines.append(f"  - {event_type}: {count}")
            lines.append("")

        return "\n".join(lines)

    def get_config(self) -> CompanyModeConfig:
        """获取当前配置"""
        return self.config

    def update_config(self, config: CompanyModeConfig) -> None:
        """
        更新配置
        
        Args:
            config: 新配置
        """
        self.config = config
        logger.info("公司模式配置已更新")
