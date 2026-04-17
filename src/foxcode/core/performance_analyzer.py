"""
FoxCode 性能分析器

提供代码执行时间分析、内存使用追踪和性能瓶颈识别功能。

主要功能：
- 代码执行时间分析
- 内存使用追踪和分析
- 性能瓶颈识别
- 性能报告生成
"""

from __future__ import annotations

import cProfile
import io
import logging
import pstats
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# 尝试导入内存分析模块
try:
    import tracemalloc
    TRACEMALLOC_AVAILABLE = True
except ImportError:
    TRACEMALLOC_AVAILABLE = False


class ProfilingStatus(str, Enum):
    """分析状态"""
    IDLE = "idle"           # 空闲
    RUNNING = "running"     # 运行中
    COMPLETED = "completed" # 已完成
    FAILED = "failed"       # 失败


class BottleneckType(str, Enum):
    """瓶颈类型"""
    CPU = "cpu"             # CPU 密集
    MEMORY = "memory"       # 内存密集
    IO = "io"               # IO 密集
    NETWORK = "network"     # 网络密集
    ALGORITHM = "algorithm" # 算法问题
    LOCK = "lock"           # 锁竞争


@dataclass
class FunctionStats:
    """
    函数统计信息
    
    Attributes:
        name: 函数名
        file: 文件名
        line: 行号
        calls: 调用次数
        total_time: 总时间（秒）
        own_time: 自身时间（秒，不含子调用）
        avg_time: 平均时间
        min_time: 最小时间
        max_time: 最大时间
    """
    name: str
    file: str = ""
    line: int = 0
    calls: int = 0
    total_time: float = 0.0
    own_time: float = 0.0
    avg_time: float = 0.0
    min_time: float = 0.0
    max_time: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "file": self.file,
            "line": self.line,
            "calls": self.calls,
            "total_time": self.total_time,
            "own_time": self.own_time,
            "avg_time": self.avg_time,
            "min_time": self.min_time,
            "max_time": self.max_time,
        }


@dataclass
class MemorySnapshot:
    """
    内存快照
    
    Attributes:
        timestamp: 时间戳
        current_size: 当前内存使用
        peak_size: 峰值内存使用
        block_count: 内存块数量
        top_allocations: 最大的内存分配
    """
    timestamp: datetime = field(default_factory=datetime.now)
    current_size: int = 0
    peak_size: int = 0
    block_count: int = 0
    top_allocations: list[tuple[str, int]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "current_size": self.current_size,
            "peak_size": self.peak_size,
            "block_count": self.block_count,
            "top_allocations": self.top_allocations,
        }


@dataclass
class MemoryReport:
    """
    内存报告
    
    Attributes:
        start_snapshot: 开始快照
        end_snapshot: 结束快照
        memory_delta: 内存变化
        peak_memory: 峰值内存
        leaks: 可能的内存泄漏
    """
    start_snapshot: MemorySnapshot | None = None
    end_snapshot: MemorySnapshot | None = None
    memory_delta: int = 0
    peak_memory: int = 0
    leaks: list[tuple[str, int]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_snapshot": self.start_snapshot.to_dict() if self.start_snapshot else None,
            "end_snapshot": self.end_snapshot.to_dict() if self.end_snapshot else None,
            "memory_delta": self.memory_delta,
            "peak_memory": self.peak_memory,
            "leaks": self.leaks,
        }


@dataclass
class Bottleneck:
    """
    性能瓶颈
    
    Attributes:
        type: 瓶颈类型
        location: 位置
        description: 描述
        impact: 影响程度
        suggestion: 优化建议
        severity: 严重程度
    """
    type: BottleneckType
    location: str
    description: str
    impact: float = 0.0
    suggestion: str = ""
    severity: str = "medium"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "location": self.location,
            "description": self.description,
            "impact": self.impact,
            "suggestion": self.suggestion,
            "severity": self.severity,
        }


@dataclass
class ProfileResult:
    """
    性能分析结果
    
    Attributes:
        status: 分析状态
        total_time: 总执行时间
        function_stats: 函数统计列表
        memory_report: 内存报告
        bottlenecks: 瓶颈列表
        call_count: 总调用次数
        timestamp: 时间戳
        error: 错误信息
        metadata: 元数据
    """
    status: ProfilingStatus = ProfilingStatus.IDLE
    total_time: float = 0.0
    function_stats: list[FunctionStats] = field(default_factory=list)
    memory_report: MemoryReport | None = None
    bottlenecks: list[Bottleneck] = field(default_factory=list)
    call_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "total_time": self.total_time,
            "function_stats": [s.to_dict() for s in self.function_stats],
            "memory_report": self.memory_report.to_dict() if self.memory_report else None,
            "bottlenecks": [b.to_dict() for b in self.bottlenecks],
            "call_count": self.call_count,
            "timestamp": self.timestamp.isoformat(),
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class ComparisonReport:
    """
    比较报告
    
    Attributes:
        baseline_time: 基准时间
        current_time: 当前时间
        time_diff: 时间差异
        time_diff_percent: 时间差异百分比
        improved: 是否改进
        significant_functions: 显著变化的函数
    """
    baseline_time: float = 0.0
    current_time: float = 0.0
    time_diff: float = 0.0
    time_diff_percent: float = 0.0
    improved: bool = True
    significant_functions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_time": self.baseline_time,
            "current_time": self.current_time,
            "time_diff": self.time_diff,
            "time_diff_percent": self.time_diff_percent,
            "improved": self.improved,
            "significant_functions": self.significant_functions,
        }


class PerformanceConfig(BaseModel):
    """
    性能分析配置
    
    Attributes:
        enable_memory_profiling: 是否启用内存分析
        enable_cpu_profiling: 是否启用 CPU 分析
        sample_interval: 采样间隔（秒）
        max_functions: 最大函数数量
        time_threshold: 时间阈值（秒）
        memory_threshold: 内存阈值（字节）
    """
    enable_memory_profiling: bool = True
    enable_cpu_profiling: bool = True
    sample_interval: float = Field(default=0.01, ge=0.001)
    max_functions: int = Field(default=100, ge=10)
    time_threshold: float = Field(default=0.1, ge=0.001)
    memory_threshold: int = Field(default=1024 * 1024)  # 1MB


class PerformanceAnalyzer:
    """
    性能分析器
    
    提供代码执行时间分析、内存使用追踪和性能瓶颈识别功能。
    
    Example:
        >>> analyzer = PerformanceAnalyzer()
        >>> result = await analyzer.profile_function(my_function, arg1, arg2)
        >>> print(f"执行时间: {result.total_time:.3f}s")
    """

    def __init__(self, config: PerformanceConfig | None = None):
        """
        初始化分析器
        
        Args:
            config: 分析器配置
        """
        self.config = config or PerformanceConfig()
        self._memory_tracking = False
        self._memory_snapshots: list[MemorySnapshot] = []
        logger.info("性能分析器初始化完成")

    async def profile_function(
        self,
        func: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> ProfileResult:
        """
        分析函数性能
        
        Args:
            func: 要分析的函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            分析结果
        """
        result = ProfileResult(status=ProfilingStatus.RUNNING)

        # 创建分析器
        profiler = cProfile.Profile()

        # 开始内存追踪
        if self.config.enable_memory_profiling and TRACEMALLOC_AVAILABLE:
            self.start_memory_tracking()

        start_time = time.perf_counter()

        try:
            # 执行分析
            profiler.enable()

            # 执行函数
            if asyncio.iscoroutinefunction(func):
                await func(*args, **kwargs)
            else:
                func(*args, **kwargs)

            profiler.disable()

            end_time = time.perf_counter()
            result.total_time = end_time - start_time
            result.status = ProfilingStatus.COMPLETED

            # 解析分析结果
            result.function_stats = self._parse_profiler_stats(profiler)

            # 获取内存报告
            if self.config.enable_memory_profiling and TRACEMALLOC_AVAILABLE:
                result.memory_report = self.stop_memory_tracking()

            # 识别瓶颈
            result.bottlenecks = self.identify_bottlenecks(result)

        except Exception as e:
            result.status = ProfilingStatus.FAILED
            result.error = f"{type(e).__name__}: {str(e)}"
            result.metadata["traceback"] = traceback.format_exc()
            logger.error(f"性能分析失败: {e}")

        return result

    async def profile_code(
        self,
        code: str,
        globals_dict: dict[str, Any] | None = None,
        locals_dict: dict[str, Any] | None = None,
    ) -> ProfileResult:
        """
        分析代码性能
        
        Args:
            code: 代码字符串
            globals_dict: 全局变量字典
            locals_dict: 局部变量字典
            
        Returns:
            分析结果
        """
        result = ProfileResult(status=ProfilingStatus.RUNNING)

        # 创建分析器
        profiler = cProfile.Profile()

        # 准备执行环境
        exec_globals = globals_dict or {}
        exec_locals = locals_dict or {}

        # 开始内存追踪
        if self.config.enable_memory_profiling and TRACEMALLOC_AVAILABLE:
            self.start_memory_tracking()

        start_time = time.perf_counter()

        try:
            profiler.enable()
            exec(code, exec_globals, exec_locals)
            profiler.disable()

            end_time = time.perf_counter()
            result.total_time = end_time - start_time
            result.status = ProfilingStatus.COMPLETED

            # 解析分析结果
            result.function_stats = self._parse_profiler_stats(profiler)

            # 获取内存报告
            if self.config.enable_memory_profiling and TRACEMALLOC_AVAILABLE:
                result.memory_report = self.stop_memory_tracking()

            # 识别瓶颈
            result.bottlenecks = self.identify_bottlenecks(result)

        except Exception as e:
            result.status = ProfilingStatus.FAILED
            result.error = f"{type(e).__name__}: {str(e)}"
            result.metadata["traceback"] = traceback.format_exc()

        return result

    def _parse_profiler_stats(self, profiler: cProfile.Profile) -> list[FunctionStats]:
        """解析分析器统计信息"""
        stats_stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stats_stream)
        stats.sort_stats(pstats.SortKey.CUMULATIVE)

        function_stats = []

        # 获取原始统计数据
        stats_data = stats.stats

        for key, value in stats_data.items():
            filename, line, func_name = key
            cc, nc, tt, ct, callers = value

            # 计算平均时间
            avg_time = tt / nc if nc > 0 else 0

            stat = FunctionStats(
                name=func_name,
                file=filename,
                line=line,
                calls=nc,
                total_time=ct,
                own_time=tt,
                avg_time=avg_time,
            )
            function_stats.append(stat)

        # 按总时间排序
        function_stats.sort(key=lambda x: x.total_time, reverse=True)

        # 限制数量
        return function_stats[:self.config.max_functions]

    def start_memory_tracking(self) -> None:
        """开始内存追踪"""
        if not TRACEMALLOC_AVAILABLE:
            logger.warning("tracemalloc 不可用，内存追踪功能受限")
            return

        if not self._memory_tracking:
            tracemalloc.start()
            self._memory_tracking = True
            self._memory_snapshots = []
            logger.debug("内存追踪已启动")

    def stop_memory_tracking(self) -> MemoryReport:
        """停止内存追踪"""
        report = MemoryReport()

        if not TRACEMALLOC_AVAILABLE or not self._memory_tracking:
            return report

        try:
            # 获取当前快照
            current_snapshot = tracemalloc.take_snapshot()
            current, peak = tracemalloc.get_traced_memory()

            # 创建结束快照
            report.end_snapshot = MemorySnapshot(
                current_size=current,
                peak_size=peak,
                block_count=len(current_snapshot.traces),
                top_allocations=self._get_top_allocations(current_snapshot),
            )

            # 如果有开始快照
            if self._memory_snapshots:
                report.start_snapshot = self._memory_snapshots[0]
                report.memory_delta = current - report.start_snapshot.current_size

            report.peak_memory = peak

            # 检测可能的内存泄漏
            report.leaks = self._detect_memory_leaks(current_snapshot)

        finally:
            tracemalloc.stop()
            self._memory_tracking = False
            logger.debug("内存追踪已停止")

        return report

    def _get_top_allocations(
        self,
        snapshot: Any,
        limit: int = 10,
    ) -> list[tuple[str, int]]:
        """获取最大的内存分配"""
        top_stats = snapshot.statistics("lineno")[:limit]
        return [(str(stat), stat.size) for stat in top_stats]

    def _detect_memory_leaks(
        self,
        snapshot: Any,
        threshold: int = 1024 * 1024,  # 1MB
    ) -> list[tuple[str, int]]:
        """检测可能的内存泄漏"""
        leaks = []

        for stat in snapshot.statistics("lineno"):
            if stat.size >= threshold:
                leaks.append((str(stat), stat.size))

        return leaks

    def identify_bottlenecks(self, profile_result: ProfileResult) -> list[Bottleneck]:
        """
        识别性能瓶颈
        
        Args:
            profile_result: 分析结果
            
        Returns:
            瓶颈列表
        """
        bottlenecks = []

        # 检查 CPU 瓶颈
        for stat in profile_result.function_stats:
            # 高调用次数
            if stat.calls > 10000:
                bottlenecks.append(Bottleneck(
                    type=BottleneckType.CPU,
                    location=f"{stat.file}:{stat.line}",
                    description=f"函数 {stat.name} 被调用 {stat.calls} 次",
                    impact=stat.total_time,
                    suggestion="考虑缓存结果或优化算法减少调用次数",
                    severity="high" if stat.calls > 100000 else "medium",
                ))

            # 长执行时间
            if stat.own_time > self.config.time_threshold:
                bottlenecks.append(Bottleneck(
                    type=BottleneckType.CPU,
                    location=f"{stat.file}:{stat.line}",
                    description=f"函数 {stat.name} 执行时间过长: {stat.own_time:.3f}s",
                    impact=stat.own_time,
                    suggestion="考虑优化算法或使用更高效的数据结构",
                    severity="high" if stat.own_time > 1.0 else "medium",
                ))

        # 检查内存瓶颈
        if profile_result.memory_report:
            mem_report = profile_result.memory_report

            if mem_report.peak_memory > self.config.memory_threshold * 10:  # 10MB
                bottlenecks.append(Bottleneck(
                    type=BottleneckType.MEMORY,
                    location="全局",
                    description=f"峰值内存使用过高: {mem_report.peak_memory / 1024 / 1024:.2f}MB",
                    impact=mem_report.peak_memory,
                    suggestion="考虑使用生成器、流式处理或分块处理数据",
                    severity="high",
                ))

            for leak, size in mem_report.leaks:
                bottlenecks.append(Bottleneck(
                    type=BottleneckType.MEMORY,
                    location=leak,
                    description=f"可能的内存泄漏: {size / 1024:.2f}KB",
                    impact=size,
                    suggestion="检查对象生命周期，确保正确释放资源",
                    severity="medium",
                ))

        return bottlenecks

    def generate_report(self, profile_result: ProfileResult) -> str:
        """
        生成性能报告
        
        Args:
            profile_result: 分析结果
            
        Returns:
            报告文本
        """
        lines = []
        lines.append("# 性能分析报告")
        lines.append(f"\n**分析时间**: {profile_result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**状态**: {profile_result.status.value}")
        lines.append(f"**总执行时间**: {profile_result.total_time:.4f}s")

        if profile_result.error:
            lines.append(f"\n**错误**: {profile_result.error}")
            return "\n".join(lines)

        # 函数统计
        lines.append("\n## 函数统计 (Top 10)")
        lines.append("\n| 函数 | 调用次数 | 总时间 | 自身时间 | 平均时间 |")
        lines.append("|------|----------|--------|----------|----------|")

        for stat in profile_result.function_stats[:10]:
            lines.append(
                f"| {stat.name[:30]} | {stat.calls} | "
                f"{stat.total_time:.4f}s | {stat.own_time:.4f}s | {stat.avg_time:.6f}s |"
            )

        # 内存报告
        if profile_result.memory_report:
            mem = profile_result.memory_report
            lines.append("\n## 内存分析")
            if mem.end_snapshot:
                lines.append(f"- 当前内存: {mem.end_snapshot.current_size / 1024 / 1024:.2f}MB")
                lines.append(f"- 峰值内存: {mem.peak_memory / 1024 / 1024:.2f}MB")
                lines.append(f"- 内存块数: {mem.end_snapshot.block_count}")

            if mem.leaks:
                lines.append("\n### 可能的内存泄漏")
                for leak, size in mem.leaks[:5]:
                    lines.append(f"- {leak}: {size / 1024:.2f}KB")

        # 瓶颈分析
        if profile_result.bottlenecks:
            lines.append("\n## 性能瓶颈")
            for bn in profile_result.bottlenecks:
                lines.append(f"\n### {bn.type.value.upper()} - {bn.severity}")
                lines.append(f"- **位置**: {bn.location}")
                lines.append(f"- **描述**: {bn.description}")
                lines.append(f"- **建议**: {bn.suggestion}")

        return "\n".join(lines)

    def compare_profiles(
        self,
        baseline: ProfileResult,
        current: ProfileResult,
    ) -> ComparisonReport:
        """
        比较性能分析结果
        
        Args:
            baseline: 基准结果
            current: 当前结果
            
        Returns:
            比较报告
        """
        report = ComparisonReport(
            baseline_time=baseline.total_time,
            current_time=current.total_time,
            time_diff=current.total_time - baseline.total_time,
        )

        if baseline.total_time > 0:
            report.time_diff_percent = (report.time_diff / baseline.total_time) * 100

        report.improved = report.time_diff <= 0

        # 比较函数统计
        baseline_funcs = {f.name: f for f in baseline.function_stats}
        current_funcs = {f.name: f for f in current.function_stats}

        significant_changes = []
        for name, current_stat in current_funcs.items():
            if name in baseline_funcs:
                baseline_stat = baseline_funcs[name]
                time_diff = current_stat.total_time - baseline_stat.total_time

                # 超过 10% 变化视为显著
                if baseline_stat.total_time > 0:
                    percent_change = (time_diff / baseline_stat.total_time) * 100
                    if abs(percent_change) > 10:
                        significant_changes.append({
                            "function": name,
                            "baseline_time": baseline_stat.total_time,
                            "current_time": current_stat.total_time,
                            "change_percent": percent_change,
                        })

        report.significant_functions = significant_changes

        return report

    def get_statistics(self) -> dict[str, Any]:
        """获取分析器统计信息"""
        return {
            "memory_tracking": self._memory_tracking,
            "snapshots_count": len(self._memory_snapshots),
            "config": self.config.model_dump(),
        }


# 创建默认分析器实例
performance_analyzer = PerformanceAnalyzer()


# 导入 asyncio 用于检测协程函数
import asyncio
