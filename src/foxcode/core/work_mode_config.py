"""
FoxCode Work模式配置模块

定义Work模式相关的配置模型，简化版本，专注于代码编写任务记录。

功能：
- Work模式状态管理
- 任务记录保存
- 执行模式配置
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class WorkModeStatus(str, Enum):
    """Work模式状态枚举"""
    DISABLED = "disabled"       # 已禁用
    ENABLED = "enabled"         # 已启用
    STARTING = "starting"       # 启动中
    STOPPING = "stopping"       # 停止中
    ERROR = "error"             # 错误状态


class AgentExecutionMode(str, Enum):
    """Agent 执行模式枚举"""
    SIMULATION = "simulation"     # 模拟模式（默认，不调用真实 AI）
    SINGLE_AGENT = "single_agent" # 单代理模式（使用 FoxCodeAgent）
    MULTI_AGENT = "multi_agent"   # 多代理模式（使用 MultiAgentOrchestrator）


class WorkModeConfig(BaseModel):
    """
    Work模式配置
    
    简化的配置模型，专注于代码编写任务管理
    """
    # 模式状态
    enabled: bool = Field(default=True, description="是否启用Work模式（默认启用）")
    status: WorkModeStatus = Field(
        default=WorkModeStatus.ENABLED,
        description="Work模式状态"
    )
    
    # 执行模式
    execution_mode: AgentExecutionMode = Field(
        default=AgentExecutionMode.SINGLE_AGENT,
        description="Agent执行模式"
    )
    
    # 任务配置
    long_work_mode: bool = Field(default=True, description="是否启用长期工作模式")
    report_interval: int = Field(default=1, ge=1, description="报告间隔（每个流程完成后）")
    max_concurrent_tasks: int = Field(default=3, ge=1, le=10, description="最大并发任务数")
    
    # 目标子文件夹配置
    target_subfolders: list[str] = Field(
        default_factory=list,
        description="目标子文件夹列表"
    )
    auto_detect_subfolders: bool = Field(
        default=True,
        description="是否自动检测子文件夹"
    )
    
    # 记录保存配置
    save_records: bool = Field(default=True, description="是否保存任务记录")
    records_dir: str = Field(default=".foxcode/work_records", description="记录保存目录")
    max_records: int = Field(default=100, ge=1, description="最大保存记录数")
    
    def is_enabled(self) -> bool:
        """检查Work模式是否启用"""
        return self.enabled and self.status == WorkModeStatus.ENABLED
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "enabled": self.enabled,
            "status": self.status.value,
            "execution_mode": self.execution_mode.value,
            "long_work_mode": self.long_work_mode,
            "report_interval": self.report_interval,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "target_subfolders": self.target_subfolders,
            "auto_detect_subfolders": self.auto_detect_subfolders,
            "save_records": self.save_records,
            "records_dir": self.records_dir,
            "max_records": self.max_records,
        }
