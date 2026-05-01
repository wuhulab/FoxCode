"""
FoxCode 统计模块 - 跟踪使用情况和计算成本

这个文件负责统计和分析FoxCode的使用情况：
1. 工具调用统计（次数、成功率、耗时）
2. API调用统计（token数、成本）
3. 生成使用报告

主要功能：
- 记录每次工具调用的详细信息
- 记录每次API调用的token消耗和成本
- 计算不同模型的成本（基于官方定价）
- 生成统计报告

使用方式：
    from foxcode.utils.statistics import stats_manager
    
    # 记录工具使用
    stats_manager.record_tool_usage(
        tool_name="read_file",
        success=True,
        duration=0.5
    )
    
    # 记录API使用
    cost = stats_manager.record_api_usage(
        model="gpt-4o",
        input_tokens=1000,
        output_tokens=500
    )
    
    # 获取统计报告
    report = stats_manager.get_full_report()

关键特性：
- 自动计算API成本（基于各模型官方定价）
- 参数脱敏（保护敏感信息）
- 支持多种AI模型的定价
- 生成详细的使用报告
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ==================== 模型定价表 ====================
# 各模型的定价（美元/千tokens）
# 数据来源：各模型官方定价页面（2024年价格）
# 
# 定价说明：
# - input: 输入token的价格（提示词）
# - output: 输出token的价格（AI生成的回复）
# - 价格单位：美元/千tokens
#
# 为什么需要定价表？
# 1. 帮助用户了解API使用成本
# 2. 优化提示词以降低成本
# 3. 选择性价比高的模型

MODEL_PRICING = {
    # OpenAI 模型
    # GPT-4o：最新旗舰模型，性价比高
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},

    # Anthropic 模型
    # Claude：擅长长文本和代码
    "claude-sonnet-4-20250514": {"input": 0.003, "output": 0.015},
    "claude-opus-4-20250514": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},

    # DeepSeek 模型
    # DeepSeek：性价比极高，适合大量使用
    "deepseek-chat": {"input": 0.00014, "output": 0.00028},
    "deepseek-coder": {"input": 0.00014, "output": 0.00028},

    # StepFun 模型
    # Step：国产模型，中文能力强
    "step-1-8k": {"input": 0.002, "output": 0.002},
    "step-1-32k": {"input": 0.004, "output": 0.004},
    "step-2-16k": {"input": 0.004, "output": 0.004},
    "step-3.5-flash": {"input": 0.0004, "output": 0.0004},

    # 默认定价（未知模型）
    # 使用保守估计的价格
    "default": {"input": 0.001, "output": 0.002},
}


@dataclass
class ToolUsageRecord:
    """
    工具使用记录 - 记录一次工具调用的详细信息
    
    记录内容：
    - 工具名称和调用时间
    - 执行结果（成功/失败）
    - 执行耗时
    - 错误信息（如果失败）
    - 参数（已脱敏，保护隐私）
    - 结果大小
    
    用途：
    - 分析工具使用频率
    - 识别性能瓶颈
    - 调试失败原因
    """
    tool_name: str                    # 工具名称
    timestamp: float                   # 时间戳
    success: bool                      # 是否成功
    duration: float = 0.0              # 执行时长（秒）
    error: str | None = None           # 错误信息
    params: dict[str, Any] = field(default_factory=dict)  # 参数（脱敏后）
    result_size: int = 0               # 结果大小（字符数）


@dataclass
class APIUsageRecord:
    """
    API使用记录 - 记录一次API调用的详细信息
    
    记录内容：
    - 模型名称和调用时间
    - Token消耗（输入和输出）
    - 成本（美元）
    - 响应时长
    
    用途：
    - 跟踪API使用成本
    - 分析token使用效率
    - 优化提示词降低成本
    """
    model: str                         # 模型名称
    timestamp: float                   # 时间戳
    input_tokens: int                  # 输入tokens
    output_tokens: int                 # 输出tokens
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
    统计管理器 - 跟踪使用情况和计算成本
    
    这是统计系统的核心，负责：
    1. 记录工具调用和API调用
    2. 计算成本（基于模型定价）
    3. 生成统计报告
    4. 参数脱敏（保护隐私）
    
    使用示例：
        # 获取全局实例
        from foxcode.utils.statistics import stats_manager
        
        # 记录工具使用
        stats_manager.record_tool_usage(
            tool_name="read_file",
            success=True,
            duration=0.5
        )
        
        # 记录API使用
        cost = stats_manager.record_api_usage(
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500
        )
        
        # 获取报告
        report = stats_manager.get_full_report()
        print(report)
    
    数据管理：
    - 最多保存1000条记录（避免内存占用过大）
    - 自动清理旧记录
    - 支持重置统计
    """

    def __init__(self, max_records: int = 1000):
        """
        初始化统计管理器
        
        Args:
            max_records: 最大保存的记录数量，超过则删除旧记录
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
        脱敏参数 - 移除敏感信息，保护隐私
        
        为什么需要脱敏？
        1. 参数可能包含API密钥、密码等敏感信息
        2. 日志和统计记录不应暴露敏感信息
        3. 防止敏感信息泄露到报告或日志中
        
        脱敏规则：
        - 敏感字段（api_key、password等）替换为***REDACTED***
        - 长字符串截断（避免日志过长）
        - 递归处理嵌套字典
        
        Args:
            params: 原始参数字典
            
        Returns:
            脱敏后的参数字典
        """
        # 敏感字段的关键词列表
        # 包含这些关键词的字段会被脱敏
        sensitive_keys = {
            "api_key", "apikey", "password", "passwd", "secret",
            "token", "auth", "credential", "private_key",
        }

        sanitized = {}
        for key, value in params.items():
            key_lower = key.lower()
            
            # 检查是否是敏感字段
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                # 递归处理嵌套字典
                sanitized[key] = self._sanitize_params(value)
            elif isinstance(value, str) and len(value) > 100:
                # 截断长字符串，避免日志过长
                sanitized[key] = value[:100] + "..."
            else:
                sanitized[key] = value

        return sanitized


# 全局统计管理器实例
stats_manager = StatisticsManager()
