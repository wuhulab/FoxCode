"""
FoxCode 上下文桥接模块 - 跨会话传递工作状态

这个文件负责在不同会话之间传递上下文信息：
1. 生成会话摘要（完成的工作、遇到的问题、下一步计划）
2. 保存和加载摘要
3. 检测会话类型（初始化代理 vs 编码代理）
4. 压缩和注入上下文

主要功能：
- 会话摘要：记录工作进度和状态
- 上下文传递：新会话可以继续之前的工作
- 会话类型检测：自动判断是初始化还是编码

使用场景：
- 长时间运行的项目：跨多个会话保持进度
- 上下文重置后恢复：从摘要中恢复关键信息
- 多代理协作：在代理间传递状态

使用方式：
    from foxcode.context.context_bridge import ContextBridge
    
    bridge = ContextBridge(working_dir=Path("."))
    
    # 生成摘要
    summary = bridge.generate_summary(
        session_id="xxx",
        completed_work=["实现登录功能"],
        next_steps=["实现注册功能"]
    )
    
    # 保存摘要
    bridge.save_summary(summary)
    
    # 加载摘要
    summary = bridge.load_summary()

关键特性：
- 支持Markdown格式的摘要
- 自动检测会话类型
- 支持上下文压缩
- 支持摘要历史记录
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SessionType(str, Enum):
    """
    会话类型 - 区分不同的工作阶段
    
    FoxCode有两种主要工作模式：
    - INITIALIZER: 初始化代理，负责创建项目结构、功能列表
    - CODER: 编码代理，负责实现具体功能
    
    为什么需要区分会话类型？
    1. 不同阶段的任务不同
    2. 需要加载不同的上下文
    3. 生成不同的提示词
    
    检测方式：
    - 检查.foxcode/features.md是否存在
    - 存在则为CODER模式，否则为INITIALIZER模式
    """
    INITIALIZER = "initializer"  # 初始化代理：创建项目结构
    CODER = "coder"              # 编码代理：实现功能


class CompressionLevel(str, Enum):
    """
    压缩级别 - 控制上下文压缩的程度
    
    当上下文过长时，需要压缩以节省token。不同级别保留不同数量的细节。
    
    压缩策略：
    - NONE: 不压缩，保留所有细节
    - LIGHT: 轻度压缩，移除冗余信息
    - MEDIUM: 中度压缩，保留关键信息
    - AGGRESSIVE: 激进压缩，只保留核心要点
    
    为什么需要压缩？
    1. 上下文窗口有限（通常128k tokens）
    2. 长上下文增加API成本
    3. 过多细节可能干扰AI判断
    """
    NONE = "none"        # 不压缩
    LIGHT = "light"      # 轻度压缩
    MEDIUM = "medium"    # 中度压缩
    AGGRESSIVE = "aggressive"  # 激进压缩


@dataclass
class SessionSummary:
    """
    会话摘要 - 记录一个会话的关键信息
    
    这是跨会话传递状态的核心数据结构，包含：
    - 完成的工作：已实现的功能
    - 未完成的工作：待办事项
    - 遇到的问题：错误、障碍
    - 下一步建议：后续计划
    - 关键决策：重要的技术选择
    - 文件变更：修改了哪些文件
    
    使用场景：
    1. 会话结束时保存状态
    2. 新会话开始时恢复状态
    3. 上下文重置后注入关键信息
    
    格式转换：
    - to_markdown(): 转换为Markdown格式，便于阅读
    - from_markdown(): 从Markdown解析，便于加载
    """
    session_id: str                           # 会话ID
    session_type: SessionType                 # 会话类型
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())  # 时间戳

    # 完成的工作
    completed_work: list[str] = field(default_factory=list)

    # 未完成的工作
    incomplete_work: list[str] = field(default_factory=list)

    # 遇到的问题
    issues: list[str] = field(default_factory=list)

    # 下一步建议
    next_steps: list[str] = field(default_factory=list)

    # 关键决策
    decisions: list[str] = field(default_factory=list)

    # 文件变更摘要
    file_changes: list[str] = field(default_factory=list)

    # 备注
    notes: str = ""

    def to_markdown(self) -> str:
        """
        转换为 Markdown 格式
        
        Returns:
            Markdown 格式的摘要
        """
        lines = [
            "# 会话摘要",
            "",
            "## 会话信息",
            f"- 会话ID: {self.session_id}",
            f"- 时间: {self.timestamp}",
            f"- 模式: {self.session_type.value}",
            "",
            "## 完成的工作",
        ]

        if self.completed_work:
            for work in self.completed_work:
                lines.append(f"- {work}")
        else:
            lines.append("- 无")

        lines.extend(["", "## 未完成的工作"])

        if self.incomplete_work:
            for work in self.incomplete_work:
                lines.append(f"- {work}")
        else:
            lines.append("- 无")

        lines.extend(["", "## 遇到的问题"])

        if self.issues:
            for issue in self.issues:
                lines.append(f"- {issue}")
        else:
            lines.append("- 无")

        lines.extend(["", "## 下一步建议"])

        if self.next_steps:
            for i, step in enumerate(self.next_steps, 1):
                lines.append(f"{i}. {step}")
        else:
            lines.append("1. 暂无")

        if self.decisions:
            lines.extend(["", "## 关键决策"])
            for decision in self.decisions:
                lines.append(f"- {decision}")

        if self.file_changes:
            lines.extend(["", "## 文件变更"])
            for change in self.file_changes:
                lines.append(f"- {change}")

        if self.notes:
            lines.extend(["", "## 备注", self.notes])

        lines.append("")
        return "\n".join(lines)

    @classmethod
    def from_markdown(cls, content: str) -> SessionSummary:
        """
        从 Markdown 格式解析
        
        Args:
            content: Markdown 内容
            
        Returns:
            解析后的会话摘要
        """
        lines = content.split("\n")

        summary_data: dict[str, Any] = {
            "session_id": "",
            "session_type": SessionType.CODER,
            "completed_work": [],
            "incomplete_work": [],
            "issues": [],
            "next_steps": [],
            "decisions": [],
            "file_changes": [],
            "notes": "",
        }

        current_section = ""

        for line in lines:
            line = line.rstrip()

            # 识别章节
            if line.startswith("## "):
                current_section = line[3:].strip().lower()
                continue

            # 解析会话信息
            if current_section == "会话信息":
                if line.startswith("- 会话ID:"):
                    summary_data["session_id"] = line.split(":", 1)[1].strip()
                elif line.startswith("- 时间:"):
                    summary_data["timestamp"] = line.split(":", 1)[1].strip()
                elif line.startswith("- 模式:"):
                    mode = line.split(":", 1)[1].strip()
                    summary_data["session_type"] = SessionType(mode)

            # 解析列表内容
            elif line.startswith("- ") and len(line) > 2:
                item = line[2:].strip()

                if current_section == "完成的工作":
                    summary_data["completed_work"].append(item)
                elif current_section == "未完成的工作":
                    summary_data["incomplete_work"].append(item)
                elif current_section == "遇到的问题":
                    summary_data["issues"].append(item)
                elif current_section == "关键决策":
                    summary_data["decisions"].append(item)
                elif current_section == "文件变更":
                    summary_data["file_changes"].append(item)

            # 解析下一步建议
            elif current_section == "下一步建议":
                match = re.match(r"\d+\. (.+)", line)
                if match:
                    summary_data["next_steps"].append(match.group(1).strip())

            # 解析备注
            elif current_section == "备注" and line.strip():
                if summary_data["notes"]:
                    summary_data["notes"] += "\n" + line
                else:
                    summary_data["notes"] = line

        return cls(**summary_data)

    def get_brief(self, max_items: int = 3) -> str:
        """
        获取简要摘要（用于注入系统提示词）
        
        Args:
            max_items: 每个部分最多显示的项目数
            
        Returns:
            简要摘要文本
        """
        lines = [f"[会话 {self.session_id} 摘要]"]

        if self.completed_work:
            lines.append(f"完成: {', '.join(self.completed_work[:max_items])}")

        if self.incomplete_work:
            lines.append(f"待办: {', '.join(self.incomplete_work[:max_items])}")

        if self.next_steps:
            lines.append(f"下一步: {self.next_steps[0]}")

        return " | ".join(lines)


@dataclass
class ContextInfo:
    """
    上下文信息数据结构
    
    包含跨会话传递的所有上下文信息
    """
    # 进度摘要
    progress_summary: str = ""

    # 待处理功能
    pending_features: list[str] = field(default_factory=list)

    # 当前功能
    current_feature: str = ""

    # 最近会话摘要
    recent_summaries: list[SessionSummary] = field(default_factory=list)

    # 项目上下文
    project_context: str = ""

    # 关键文件
    key_files: list[str] = field(default_factory=list)

    def to_prompt_context(self) -> str:
        """
        转换为可注入系统提示词的上下文
        
        Returns:
            格式化的上下文文本
        """
        lines = ["## 当前项目上下文"]

        if self.progress_summary:
            lines.append(f"\n### 进度概要\n{self.progress_summary}")

        if self.current_feature:
            lines.append(f"\n### 当前功能\n{self.current_feature}")

        if self.pending_features:
            lines.append("\n### 待处理功能")
            for feature in self.pending_features[:5]:
                lines.append(f"- {feature}")

        if self.recent_summaries:
            lines.append("\n### 最近会话")
            for summary in self.recent_summaries[-2:]:
                lines.append(summary.get_brief())

        if self.key_files:
            lines.append("\n### 关键文件")
            for file in self.key_files[:5]:
                lines.append(f"- {file}")

        return "\n".join(lines)


class ContextBridge:
    """
    上下文桥接管理器
    
    管理跨会话上下文传递，支持摘要生成、上下文注入和压缩
    """

    DEFAULT_SUMMARY_FILE = ".foxcode/summary.md"
    DEFAULT_CONTEXT_THRESHOLD = 4000  # 上下文压缩阈值（字符数）

    def __init__(
        self,
        working_dir: Path,
        summary_file: str | None = None,
        compression_threshold: int = DEFAULT_CONTEXT_THRESHOLD,
    ):
        """
        初始化上下文桥接管理器
        
        Args:
            working_dir: 工作目录
            summary_file: 摘要文件路径（相对于工作目录）
            compression_threshold: 上下文压缩阈值
        """
        self.working_dir = Path(working_dir)
        self.summary_file = self.working_dir / (summary_file or self.DEFAULT_SUMMARY_FILE)
        self.compression_threshold = compression_threshold

        # 确保目录存在
        self._ensure_directory()

        logger.debug(f"上下文桥接管理器初始化完成，摘要文件: {self.summary_file}")

    def _ensure_directory(self) -> None:
        """确保摘要文件目录存在"""
        try:
            self.summary_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"创建摘要文件目录失败: {e}")
            raise

    def generate_summary(
        self,
        session_id: str,
        session_type: SessionType,
        completed_work: list[str] | None = None,
        incomplete_work: list[str] | None = None,
        issues: list[str] | None = None,
        next_steps: list[str] | None = None,
        decisions: list[str] | None = None,
        file_changes: list[str] | None = None,
        notes: str = "",
    ) -> SessionSummary:
        """
        生成会话摘要
        
        Args:
            session_id: 会话 ID
            session_type: 会话类型
            completed_work: 完成的工作列表
            incomplete_work: 未完成的工作列表
            issues: 遇到的问题列表
            next_steps: 下一步建议列表
            decisions: 关键决策列表
            file_changes: 文件变更列表
            notes: 备注
            
        Returns:
            生成的会话摘要
        """
        summary = SessionSummary(
            session_id=session_id,
            session_type=session_type,
            completed_work=completed_work or [],
            incomplete_work=incomplete_work or [],
            issues=issues or [],
            next_steps=next_steps or [],
            decisions=decisions or [],
            file_changes=file_changes or [],
            notes=notes,
        )

        logger.info(f"已生成会话摘要: {session_id}")
        return summary

    def save_summary(self, summary: SessionSummary) -> None:
        """
        保存摘要到文件
        
        Args:
            summary: 会话摘要
        """
        try:
            content = summary.to_markdown()
            self.summary_file.write_text(content, encoding="utf-8")
            logger.info(f"会话摘要已保存: {self.summary_file}")
        except Exception as e:
            logger.error(f"保存会话摘要失败: {e}")
            raise

    def load_summary(self) -> SessionSummary | None:
        """
        加载摘要文件
        
        Returns:
            加载的会话摘要，如果文件不存在则返回 None
        """
        if not self.summary_file.exists():
            logger.debug("摘要文件不存在")
            return None

        try:
            content = self.summary_file.read_text(encoding="utf-8")
            summary = SessionSummary.from_markdown(content)
            logger.info(f"已加载会话摘要: {summary.session_id}")
            return summary
        except Exception as e:
            logger.error(f"加载会话摘要失败: {e}")
            return None

    def append_summary(self, summary: SessionSummary) -> None:
        """
        追加摘要到历史文件
        
        Args:
            summary: 会话摘要
        """
        history_file = self.summary_file.parent / "summary_history.md"

        try:
            # 如果历史文件存在，读取现有内容
            if history_file.exists():
                existing = history_file.read_text(encoding="utf-8")
            else:
                existing = "# 会话摘要历史\n\n"

            # 追加新摘要
            new_content = existing + "\n---\n\n" + summary.to_markdown()
            history_file.write_text(new_content, encoding="utf-8")

            logger.info(f"已追加摘要到历史文件: {history_file}")
        except Exception as e:
            logger.error(f"追加摘要失败: {e}")
            raise

    def inject_context(
        self,
        system_prompt: str,
        context_info: ContextInfo,
    ) -> str:
        """
        将上下文注入系统提示词
        
        Args:
            system_prompt: 原始系统提示词
            context_info: 上下文信息
            
        Returns:
            注入上下文后的系统提示词
        """
        context_text = context_info.to_prompt_context()

        # 检查是否需要压缩
        if len(context_text) > self.compression_threshold:
            context_text = self.compress_context(context_text)

        # 在系统提示词末尾注入上下文
        injected_prompt = f"{system_prompt}\n\n{context_text}"

        logger.debug(f"已注入上下文，长度: {len(context_text)}")
        return injected_prompt

    def compress_context(
        self,
        context: str,
        level: CompressionLevel = CompressionLevel.MEDIUM,
    ) -> str:
        """
        压缩上下文
        
        Args:
            context: 原始上下文
            level: 压缩级别
            
        Returns:
            压缩后的上下文
        """
        if level == CompressionLevel.NONE:
            return context

        lines = context.split("\n")
        compressed_lines: list[str] = []

        # 根据压缩级别保留不同数量的内容
        keep_ratios = {
            CompressionLevel.LIGHT: 0.8,
            CompressionLevel.MEDIUM: 0.5,
            CompressionLevel.AGGRESSIVE: 0.3,
        }

        keep_ratio = keep_ratios.get(level, 0.5)
        target_lines = int(len(lines) * keep_ratio)

        # 优先保留重要行（标题、关键信息）
        important_patterns = [
            r"^#+",  # 标题
            r"^当前",  # 当前状态
            r"^待办",  # 待办事项
            r"^下一步",  # 下一步
            r"^功能",  # 功能相关
        ]

        important_lines: list[str] = []
        other_lines: list[str] = []

        for line in lines:
            is_important = any(re.match(p, line) for p in important_patterns)
            if is_important:
                important_lines.append(line)
            else:
                other_lines.append(line)

        # 先添加重要行
        compressed_lines.extend(important_lines)

        # 再添加其他行直到达到目标
        remaining = target_lines - len(important_lines)
        if remaining > 0:
            compressed_lines.extend(other_lines[:remaining])

        compressed = "\n".join(compressed_lines)

        # 如果仍然太长，截断
        if len(compressed) > self.compression_threshold:
            compressed = compressed[:self.compression_threshold] + "\n... (已压缩)"

        logger.info(f"上下文已压缩: {len(context)} -> {len(compressed)} 字符")
        return compressed

    def get_context_for_new_session(
        self,
        progress_summary: str = "",
        pending_features: list[str] | None = None,
        current_feature: str = "",
    ) -> ContextInfo:
        """
        获取新会话所需的上下文
        
        Args:
            progress_summary: 进度摘要
            pending_features: 待处理功能列表
            current_feature: 当前功能
            
        Returns:
            上下文信息
        """
        context_info = ContextInfo(
            progress_summary=progress_summary,
            pending_features=pending_features or [],
            current_feature=current_feature,
        )

        # 加载最近的摘要
        summary = self.load_summary()
        if summary:
            context_info.recent_summaries = [summary]

        return context_info

    def detect_session_type(self) -> SessionType:
        """
        检测当前会话类型
        
        Returns:
            会话类型（初始化代理或编码代理）
        """
        # 检查是否存在进度文件
        progress_file = self.working_dir / ".foxcode" / "progress.md"
        features_file = self.working_dir / ".foxcode" / "features.md"

        # 如果进度文件或功能列表不存在，则为初始化代理
        if not progress_file.exists() or not features_file.exists():
            logger.info("检测到初始化代理模式")
            return SessionType.INITIALIZER

        logger.info("检测到编码代理模式")
        return SessionType.CODER

    def create_initializer_context(self, project_description: str = "") -> ContextInfo:
        """
        创建初始化代理的上下文
        
        Args:
            project_description: 项目描述
            
        Returns:
            上下文信息
        """
        return ContextInfo(
            progress_summary="首次会话 - 需要初始化项目环境",
            project_context=project_description,
            pending_features=[
                "分析项目需求",
                "创建功能需求列表",
                "设置项目环境",
                "创建初始化脚本",
                "生成进度文件",
            ],
        )

    # ==================== 异步方法 ====================

    async def async_save_summary(self, summary: SessionSummary) -> None:
        """
        异步保存摘要
        
        Args:
            summary: 会话摘要
        """
        await asyncio.to_thread(self.save_summary, summary)

    async def async_load_summary(self) -> SessionSummary | None:
        """
        异步加载摘要
        
        Returns:
            加载的会话摘要
        """
        return await asyncio.to_thread(self.load_summary)

    async def async_get_context_for_new_session(
        self,
        progress_summary: str = "",
        pending_features: list[str] | None = None,
        current_feature: str = "",
    ) -> ContextInfo:
        """
        异步获取新会话所需的上下文
        
        Returns:
            上下文信息
        """
        return await asyncio.to_thread(
            self.get_context_for_new_session,
            progress_summary=progress_summary,
            pending_features=pending_features,
            current_feature=current_feature,
        )


# ==================== 便捷函数 ====================

def create_context_bridge(
    working_dir: Path | str,
    summary_file: str | None = None,
    compression_threshold: int = ContextBridge.DEFAULT_CONTEXT_THRESHOLD,
) -> ContextBridge:
    """
    创建上下文桥接管理器的便捷函数
    
    Args:
        working_dir: 工作目录
        summary_file: 摘要文件路径
        compression_threshold: 压缩阈值
        
    Returns:
        上下文桥接管理器实例
    """
    return ContextBridge(
        working_dir=Path(working_dir),
        summary_file=summary_file,
        compression_threshold=compression_threshold,
    )


def generate_session_summary(
    session_id: str,
    session_type: SessionType,
    completed_work: list[str] | None = None,
    incomplete_work: list[str] | None = None,
    next_steps: list[str] | None = None,
) -> SessionSummary:
    """
    生成会话摘要的便捷函数
    
    Args:
        session_id: 会话 ID
        session_type: 会话类型
        completed_work: 完成的工作
        incomplete_work: 未完成的工作
        next_steps: 下一步建议
        
    Returns:
        会话摘要
    """
    bridge = ContextBridge(working_dir=Path.cwd())
    return bridge.generate_summary(
        session_id=session_id,
        session_type=session_type,
        completed_work=completed_work,
        incomplete_work=incomplete_work,
        next_steps=next_steps,
    )
