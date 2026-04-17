"""
FoxCode 统计模块

提供工具使用统计和 API 成本计算功能
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# 各模型的定价（美元/千 tokens）
# 数据来源：各模型官方定价页面（2024年价格）
MODEL_PRICING = {
    # OpenAI 模型
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},

    # Anthropic 模型
    "claude-sonnet-4-20250514": {"input": 0.003, "output": 0.015},
    "claude-opus-4-20250514": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},

    # DeepSeek 模型
    "deepseek-chat": {"input": 0.00014, "output": 0.00028},
    "deepseek-coder": {"input": 0.00014, "output": 0.00028},

    # StepFun 模型
    "step-1-8k": {"input": 0.002, "output": 0.002},
    "step-1-32k": {"input": 0.004, "output": 0.004},
    "step-2-16k": {"input": 0.004, "output": 0.004},
    "step-3.5-flash": {"input": 0.0004, "output": 0.0004},

    # 默认定价（未知模型）
    "default": {"input": 0.001, "output": 0.002},
}


@dataclass
class ToolUsageRecord:
    """工具使用记录"""
    tool_name: str                    # 工具名称
    timestamp: float                   # 时间戳
    success: bool                      # 是否成功
    duration: float = 0.0              # 执行时长（秒）
    error: str | None = None           # 错误信息
    params: dict[str, Any] = field(default_factory=dict)  # 参数（脱敏后）
    result_size: int = 0               # 结果大小（字符数）


@dataclass
class APIUsageRecord:
    """API 使用记录"""
    model: str                         # 模型名称
    timestamp: float                   # 时间戳
    input_tokens: int                  # 输入 tokens
    output_tokens: int                 # 输出 tokens
    cost: float                        # 成本（美元）
    duration: float = 0.0              # 响应时长（秒）


@dataclass
class SessionStats:
    """会话统计"""
    # 工具统计
    tool_calls: int = 0                # 工具调用次数
    tool_success: int = 0              # 成功次数
    tool_failures: int = 0             # 失败次数
    tool_total_duration: float = 0.0   # 总执行时长

    # API 统计
    api_calls: int = 0                 # API 调用次数
    total_input_tokens: int = 0        # 总输入 tokens
    total_output_tokens: int = 0       # 总输出 tokens
    total_cost: float = 0.0            # 总成本（美元）
    api_total_duration: float = 0.0    # API 总响应时长

    # 详细记录
    tool_records: list[ToolUsageRecord] = field(default_factory=list)
    api_records: list[APIUsageRecord] = field(default_factory=list)

    # 按工具名称统计
    tool_usage_by_name: dict[str, int] = field(default_factory=lambda: defaultdict(int))


class StatisticsManager:
    """
    统计管理器
    
    跟踪工具使用和 API 调用情况，计算成本
    """

    def __init__(self, max_records: int = 1000):
        """
        初始化统计管理器
        
        Args:
            max_records: 最大保存的记录数量
        """
        self._session_stats = SessionStats()
        self._max_records = max_records
        self._start_time = time.time()

    def record_tool_usage(
        self,
        tool_name: str,
        success: bool,
        duration: float = 0.0,
        error: str | None = None,
        params: dict[str, Any] | None = None,
        result_size: int = 0,
    ) -> None:
        """
        记录工具使用
        
        Args:
            tool_name: 工具名称
            success: 是否成功
            duration: 执行时长
            error: 错误信息
            params: 参数（会被脱敏）
            result_size: 结果大小
        """
        # 脱敏参数（移除敏感信息）
        sanitized_params = self._sanitize_params(params or {})

        record = ToolUsageRecord(
            tool_name=tool_name,
            timestamp=time.time(),
            success=success,
            duration=duration,
            error=error,
            params=sanitized_params,
            result_size=result_size,
        )

        # 更新统计
        self._session_stats.tool_calls += 1
        self._session_stats.tool_total_duration += duration
        self._session_stats.tool_usage_by_name[tool_name] += 1

        if success:
            self._session_stats.tool_success += 1
        else:
            self._session_stats.tool_failures += 1

        # 添加记录
        self._session_stats.tool_records.append(record)

        # 清理旧记录
        if len(self._session_stats.tool_records) > self._max_records:
            self._session_stats.tool_records = self._session_stats.tool_records[-self._max_records:]

        logger.debug(f"记录工具使用: {tool_name}, 成功: {success}, 耗时: {duration:.2f}s")

    def record_api_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        duration: float = 0.0,
    ) -> float:
        """
        记录 API 使用
        
        Args:
            model: 模型名称
            input_tokens: 输入 tokens
            output_tokens: 输出 tokens
            duration: 响应时长
            
        Returns:
            计算的成本
        """
        # 计算成本
        cost = self.calculate_cost(model, input_tokens, output_tokens)

        record = APIUsageRecord(
            model=model,
            timestamp=time.time(),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            duration=duration,
        )

        # 更新统计
        self._session_stats.api_calls += 1
        self._session_stats.total_input_tokens += input_tokens
        self._session_stats.total_output_tokens += output_tokens
        self._session_stats.total_cost += cost
        self._session_stats.api_total_duration += duration

        # 添加记录
        self._session_stats.api_records.append(record)

        # 清理旧记录
        if len(self._session_stats.api_records) > self._max_records:
            self._session_stats.api_records = self._session_stats.api_records[-self._max_records:]

        logger.debug(
            f"记录 API 使用: {model}, "
            f"输入: {input_tokens}, 输出: {output_tokens}, "
            f"成本: ${cost:.6f}"
        )

        return cost

    @staticmethod
    def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
        """
        计算成本
        
        Args:
            model: 模型名称
            input_tokens: 输入 tokens
            output_tokens: 输出 tokens
            
        Returns:
            成本（美元）
        """
        # 获取定价
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])

        # 计算成本（价格是每千 tokens）
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]

        return input_cost + output_cost

    @staticmethod
    def get_model_pricing(model: str) -> dict[str, float]:
        """
        获取模型定价
        
        Args:
            model: 模型名称
            
        Returns:
            定价信息
        """
        return MODEL_PRICING.get(model, MODEL_PRICING["default"])

    def get_session_stats(self) -> dict[str, Any]:
        """
        获取会话统计
        
        Returns:
            统计信息字典
        """
        session_duration = time.time() - self._start_time

        return {
            # 会话信息
            "session_duration": round(session_duration, 2),

            # 工具统计
            "tool_calls": self._session_stats.tool_calls,
            "tool_success": self._session_stats.tool_success,
            "tool_failures": self._session_stats.tool_failures,
            "tool_success_rate": (
                self._session_stats.tool_success / self._session_stats.tool_calls * 100
                if self._session_stats.tool_calls > 0 else 0
            ),
            "tool_total_duration": round(self._session_stats.tool_total_duration, 2),
            "tool_avg_duration": (
                round(self._session_stats.tool_total_duration / self._session_stats.tool_calls, 2)
                if self._session_stats.tool_calls > 0 else 0
            ),
            "tool_usage_by_name": dict(self._session_stats.tool_usage_by_name),

            # API 统计
            "api_calls": self._session_stats.api_calls,
            "total_input_tokens": self._session_stats.total_input_tokens,
            "total_output_tokens": self._session_stats.total_output_tokens,
            "total_tokens": self._session_stats.total_input_tokens + self._session_stats.total_output_tokens,
            "total_cost": round(self._session_stats.total_cost, 6),
            "api_total_duration": round(self._session_stats.api_total_duration, 2),
            "api_avg_duration": (
                round(self._session_stats.api_total_duration / self._session_stats.api_calls, 2)
                if self._session_stats.api_calls > 0 else 0
            ),
        }

    def get_tool_usage_report(self) -> str:
        """
        获取工具使用报告
        
        Returns:
            格式化的报告字符串
        """
        stats = self.get_session_stats()

        lines = [
            "📊 工具使用统计",
            "═" * 40,
            f"总调用次数: {stats['tool_calls']}",
            f"成功次数: {stats['tool_success']}",
            f"失败次数: {stats['tool_failures']}",
            f"成功率: {stats['tool_success_rate']:.1f}%",
            f"总耗时: {stats['tool_total_duration']}s",
            f"平均耗时: {stats['tool_avg_duration']}s",
            "",
            "工具使用分布:",
        ]

        # 按使用次数排序
        sorted_tools = sorted(
            stats["tool_usage_by_name"].items(),
            key=lambda x: x[1],
            reverse=True,
        )

        for tool_name, count in sorted_tools:
            lines.append(f"  • {tool_name}: {count} 次")

        return "\n".join(lines)

    def get_api_usage_report(self) -> str:
        """
        获取 API 使用报告
        
        Returns:
            格式化的报告字符串
        """
        stats = self.get_session_stats()

        lines = [
            "💰 API 使用统计",
            "═" * 40,
            f"API 调用次数: {stats['api_calls']}",
            f"总输入 tokens: {stats['total_input_tokens']:,}",
            f"总输出 tokens: {stats['total_output_tokens']:,}",
            f"总 tokens: {stats['total_tokens']:,}",
            f"总成本: ${stats['total_cost']:.4f}",
            f"API 总耗时: {stats['api_total_duration']}s",
            f"平均响应时间: {stats['api_avg_duration']}s",
        ]

        return "\n".join(lines)

    def get_full_report(self) -> str:
        """
        获取完整报告
        
        Returns:
            格式化的完整报告字符串
        """
        stats = self.get_session_stats()

        lines = [
            "📈 FoxCode 会话统计报告",
            "═" * 50,
            f"会话时长: {stats['session_duration']}s",
            "",
            self.get_tool_usage_report(),
            "",
            self.get_api_usage_report(),
            "",
            "═" * 50,
        ]

        return "\n".join(lines)

    def reset(self) -> None:
        """重置统计"""
        self._session_stats = SessionStats()
        self._start_time = time.time()
        logger.info("统计已重置")

    def _sanitize_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        脱敏参数
        
        移除敏感信息，如 API key、密码等
        
        Args:
            params: 原始参数
            
        Returns:
            脱敏后的参数
        """
        sensitive_keys = {
            "api_key", "apikey", "password", "passwd", "secret",
            "token", "auth", "credential", "private_key",
        }

        sanitized = {}
        for key, value in params.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_params(value)
            elif isinstance(value, str) and len(value) > 100:
                # 截断长字符串
                sanitized[key] = value[:100] + "..."
            else:
                sanitized[key] = value

        return sanitized


# 全局统计管理器实例
stats_manager = StatisticsManager()
