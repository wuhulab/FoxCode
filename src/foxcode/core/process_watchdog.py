"""
FoxCode 进程看门狗模块 - 进程监控、性能统计和自动恢复

这个文件提供进程级别的监控和保护:
1. 进程监控：监控内存和 CPU 使用情况
2. 性能统计：记录请求响应时间等性能指标
3. 异常检测：自动检测进程异常（内存泄漏、CPU 飙高等）
4. 自动恢复：检测到异常时触发恢复操作
5. 健康报告：提供进程健康状态报告

健康状态:
- HEALTHY: 一切正常
- WARNING: 需要关注（如内存使用率偏高）
- CRITICAL: 需要立即处理（如内存即将耗尽）

使用方式:
    from foxcode.core.process_watchdog import init_watchdog

    watchdog = init_watchdog(config)
    watchdog.start()
    health = watchdog.get_health_status()
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import psutil

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class PerformanceMetrics:
    """
    性能指标数据类
    
    记录进程的资源使用和请求性能
    """
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time_ms: float = 0.0
    min_response_time_ms: float = float('inf')
    max_response_time_ms: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_percent: float = 0.0
    consecutive_errors: int = 0
    last_error: str | None = None
    last_error_time: datetime | None = None
    start_time: datetime = field(default_factory=datetime.now)

    @property
    def uptime_seconds(self) -> float:
        """获取运行时间（秒）"""
        return (datetime.now() - self.start_time).total_seconds()

    @property
    def success_rate(self) -> float:
        """获取成功率"""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100


@dataclass
class RequestRecord:
    """请求记录"""
    request_id: str
    start_time: float
    end_time: float | None = None
    response_time_ms: float | None = None
    success: bool = False
    error: str | None = None


class ProcessWatchdog:
    """
    进程看门狗
    
    监控进程健康状态，记录性能指标，支持自动恢复
    
    功能：
    - 定期检查内存和 CPU 使用
    - 记录请求性能指标
    - 检测异常情况并触发回调
    - 支持自动恢复机制
    """

    def __init__(
        self,
        check_interval: float = 30.0,
        memory_threshold_mb: float = 512.0,
        cpu_threshold_percent: float = 90.0,
        max_consecutive_errors: int = 5,
        metrics_history_size: int = 100,
        enable_auto_recovery: bool = True,
        health_check_port: int | None = None,
    ):
        """
        初始化进程看门狗
        
        Args:
            check_interval: 检查间隔（秒）
            memory_threshold_mb: 内存阈值（MB）
            cpu_threshold_percent: CPU 阈值（百分比）
            max_consecutive_errors: 最大连续错误次数
            metrics_history_size: 指标历史记录大小
            enable_auto_recovery: 是否启用自动恢复
            health_check_port: 健康检查端口（None 表示不启用）
        """
        self.check_interval = check_interval
        self.memory_threshold_mb = memory_threshold_mb
        self.cpu_threshold_percent = cpu_threshold_percent
        self.max_consecutive_errors = max_consecutive_errors
        self.metrics_history_size = metrics_history_size
        self.enable_auto_recovery = enable_auto_recovery
        self.health_check_port = health_check_port

        self._is_running = False
        self._monitor_task: asyncio.Task | None = None
        self._request_counter = 0
        self._pending_requests: dict[str, RequestRecord] = {}
        self._metrics_history: list[PerformanceMetrics] = []
        self._current_metrics = PerformanceMetrics()

        self._process = psutil.Process(os.getpid())

        self._on_memory_warning: Callable[[float], None] | None = None
        self._on_cpu_warning: Callable[[float], None] | None = None
        self._on_error_threshold_reached: Callable[[int], None] | None = None
        self._on_auto_recovery_triggered: Callable[[], None] | None = None

        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        """检查看门狗是否正在运行"""
        return self._is_running

    def set_callbacks(
        self,
        on_memory_warning: Callable[[float], None] | None = None,
        on_cpu_warning: Callable[[float], None] | None = None,
        on_error_threshold_reached: Callable[[int], None] | None = None,
        on_auto_recovery_triggered: Callable[[], None] | None = None,
    ) -> None:
        """
        设置事件回调函数
        
        Args:
            on_memory_warning: 内存超限回调
            on_cpu_warning: CPU 超限回调
            on_error_threshold_reached: 错误达限回调
            on_auto_recovery_triggered: 自动恢复触发回调
        """
        self._on_memory_warning = on_memory_warning
        self._on_cpu_warning = on_cpu_warning
        self._on_error_threshold_reached = on_error_threshold_reached
        self._on_auto_recovery_triggered = on_auto_recovery_triggered

        logger.debug("看门狗回调函数已设置")

    async def start(self) -> None:
        """
        启动看门狗监控
        
        开始定期检查进程健康状态
        """
        if self._is_running:
            logger.warning("看门狗已在运行")
            return

        self._is_running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())

        logger.info(
            f"进程看门狗已启动 (检查间隔: {self.check_interval}s, "
            f"内存阈值: {self.memory_threshold_mb}MB, "
            f"CPU 阈值: {self.cpu_threshold_percent}%)"
        )

    async def stop(self) -> None:
        """
        停止看门狗监控
        
        清理资源并停止监控任务
        """
        if not self._is_running:
            return

        self._is_running = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None

        logger.info("进程看门狗已停止")

    def record_request_start(self) -> str:
        """
        记录请求开始
        
        Returns:
            请求 ID
        """
        with self._lock:
            self._request_counter += 1
            request_id = f"req_{self._request_counter}_{time.time_ns()}"

            self._pending_requests[request_id] = RequestRecord(
                request_id=request_id,
                start_time=time.time()
            )

            self._current_metrics.total_requests += 1

            return request_id

    def record_request_success(
        self,
        request_id: str,
        response_time_ms: float,
    ) -> None:
        """
        记录请求成功
        
        Args:
            request_id: 请求 ID
            response_time_ms: 响应时间（毫秒）
        """
        with self._lock:
            if request_id not in self._pending_requests:
                logger.warning(f"未找到请求记录: {request_id}")
                return

            record = self._pending_requests.pop(request_id)
            record.end_time = time.time()
            record.response_time_ms = response_time_ms
            record.success = True

            metrics = self._current_metrics
            metrics.successful_requests += 1
            metrics.consecutive_errors = 0

            if response_time_ms < metrics.min_response_time_ms:
                metrics.min_response_time_ms = response_time_ms
            if response_time_ms > metrics.max_response_time_ms:
                metrics.max_response_time_ms = response_time_ms

            total = metrics.successful_requests + metrics.failed_requests
            if total > 0:
                metrics.avg_response_time_ms = (
                    (metrics.avg_response_time_ms * (total - 1) + response_time_ms) / total
                )

    def record_request_failure(
        self,
        request_id: str,
        error: Exception,
        response_time_ms: float,
    ) -> None:
        """
        记录请求失败
        
        Args:
            request_id: 请求 ID
            error: 错误对象
            response_time_ms: 响应时间（毫秒）
        """
        with self._lock:
            if request_id not in self._pending_requests:
                logger.warning(f"未找到请求记录: {request_id}")
                return

            record = self._pending_requests.pop(request_id)
            record.end_time = time.time()
            record.response_time_ms = response_time_ms
            record.success = False
            record.error = str(error)

            metrics = self._current_metrics
            metrics.failed_requests += 1
            metrics.consecutive_errors += 1
            metrics.last_error = str(error)
            metrics.last_error_time = datetime.now()

            logger.warning(
                f"请求失败 [{request_id}]: {error} "
                f"(连续错误: {metrics.consecutive_errors}/{self.max_consecutive_errors})"
            )

            if metrics.consecutive_errors >= self.max_consecutive_errors:
                self._handle_error_threshold(metrics.consecutive_errors)

    def get_current_metrics(self) -> PerformanceMetrics:
        """
        获取当前性能指标
        
        Returns:
            当前性能指标副本
        """
        with self._lock:
            self._update_resource_metrics()
            return PerformanceMetrics(
                total_requests=self._current_metrics.total_requests,
                successful_requests=self._current_metrics.successful_requests,
                failed_requests=self._current_metrics.failed_requests,
                avg_response_time_ms=self._current_metrics.avg_response_time_ms,
                min_response_time_ms=self._current_metrics.min_response_time_ms,
                max_response_time_ms=self._current_metrics.max_response_time_ms,
                memory_usage_mb=self._current_metrics.memory_usage_mb,
                cpu_percent=self._current_metrics.cpu_percent,
                consecutive_errors=self._current_metrics.consecutive_errors,
                last_error=self._current_metrics.last_error,
                last_error_time=self._current_metrics.last_error_time,
                start_time=self._current_metrics.start_time,
            )

    def get_health_status(self) -> dict[str, Any]:
        """
        获取健康状态报告
        
        Returns:
            健康状态字典
        """
        metrics = self.get_current_metrics()

        if metrics.consecutive_errors >= self.max_consecutive_errors:
            status = HealthStatus.CRITICAL
        elif (
            metrics.memory_usage_mb > self.memory_threshold_mb or
            metrics.cpu_percent > self.cpu_threshold_percent or
            metrics.consecutive_errors >= 3
        ):
            status = HealthStatus.WARNING
        else:
            status = HealthStatus.HEALTHY

        uptime = metrics.uptime_seconds
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        seconds = int(uptime % 60)
        uptime_str = f"{hours}h {minutes}m {seconds}s"

        return {
            "status": status.value,
            "uptime": uptime_str,
            "watchdog_active": self._is_running,
            "history_count": len(self._metrics_history),
            "metrics": {
                "total_requests": metrics.total_requests,
                "successful_requests": metrics.successful_requests,
                "failed_requests": metrics.failed_requests,
                "success_rate": metrics.success_rate,
                "avg_response_time_ms": metrics.avg_response_time_ms,
                "memory_usage_mb": metrics.memory_usage_mb,
                "cpu_percent": metrics.cpu_percent,
                "consecutive_errors": metrics.consecutive_errors,
            },
            "thresholds": {
                "memory_mb": self.memory_threshold_mb,
                "cpu_percent": self.cpu_threshold_percent,
                "max_errors": self.max_consecutive_errors,
            },
        }

    def export_metrics_to_file(self, file_path: Path) -> None:
        """
        导出性能指标到文件
        
        Args:
            file_path: 目标文件路径
        """
        try:
            metrics = self.get_current_metrics()

            data = {
                "timestamp": datetime.now().isoformat(),
                "metrics": {
                    "total_requests": metrics.total_requests,
                    "successful_requests": metrics.successful_requests,
                    "failed_requests": metrics.failed_requests,
                    "success_rate": metrics.success_rate,
                    "avg_response_time_ms": metrics.avg_response_time_ms,
                    "min_response_time_ms": metrics.min_response_time_ms if metrics.min_response_time_ms != float('inf') else 0,
                    "max_response_time_ms": metrics.max_response_time_ms,
                    "memory_usage_mb": metrics.memory_usage_mb,
                    "cpu_percent": metrics.cpu_percent,
                    "consecutive_errors": metrics.consecutive_errors,
                    "uptime_seconds": metrics.uptime_seconds,
                },
                "last_error": metrics.last_error,
                "last_error_time": metrics.last_error_time.isoformat() if metrics.last_error_time else None,
            }

            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"性能指标已导出到: {file_path}")

        except Exception as e:
            logger.error(f"导出性能指标失败: {e}")

    def _update_resource_metrics(self) -> None:
        """更新资源使用指标"""
        try:
            memory_info = self._process.memory_info()
            self._current_metrics.memory_usage_mb = memory_info.rss / (1024 * 1024)

            self._current_metrics.cpu_percent = self._process.cpu_percent(interval=0.1)

        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.warning(f"无法获取进程资源信息: {e}")

    async def _monitor_loop(self) -> None:
        """监控循环"""
        while self._is_running:
            try:
                await self._check_health()

                self._save_metrics_snapshot()

                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"监控循环错误: {e}\n{traceback.format_exc()}")
                await asyncio.sleep(5)

    async def _check_health(self) -> None:
        """检查健康状态"""
        with self._lock:
            self._update_resource_metrics()

            metrics = self._current_metrics

            if metrics.memory_usage_mb > self.memory_threshold_mb:
                logger.warning(
                    f"内存使用超限: {metrics.memory_usage_mb:.1f}MB > {self.memory_threshold_mb}MB"
                )
                if self._on_memory_warning:
                    try:
                        self._on_memory_warning(metrics.memory_usage_mb)
                    except Exception as e:
                        logger.error(f"内存警告回调失败: {e}")

            if metrics.cpu_percent > self.cpu_threshold_percent:
                logger.warning(
                    f"CPU 使用超限: {metrics.cpu_percent:.1f}% > {self.cpu_threshold_percent}%"
                )
                if self._on_cpu_warning:
                    try:
                        self._on_cpu_warning(metrics.cpu_percent)
                    except Exception as e:
                        logger.error(f"CPU 警告回调失败: {e}")

    def _handle_error_threshold(self, error_count: int) -> None:
        """
        处理错误达限
        
        Args:
            error_count: 连续错误次数
        """
        logger.critical(f"连续错误次数达到上限: {error_count}")

        if self._on_error_threshold_reached:
            try:
                self._on_error_threshold_reached(error_count)
            except Exception as e:
                logger.error(f"错误达限回调失败: {e}")

        if self.enable_auto_recovery and self._on_auto_recovery_triggered:
            logger.info("触发自动恢复机制...")
            try:
                self._on_auto_recovery_triggered()
            except Exception as e:
                logger.error(f"自动恢复回调失败: {e}")

    def _save_metrics_snapshot(self) -> None:
        """保存指标快照"""
        snapshot = self.get_current_metrics()
        self._metrics_history.append(snapshot)

        while len(self._metrics_history) > self.metrics_history_size:
            self._metrics_history.pop(0)


_watchdog_instance: ProcessWatchdog | None = None


def init_watchdog(
    check_interval: float = 30.0,
    memory_threshold_mb: float = 512.0,
    cpu_threshold_percent: float = 90.0,
    max_consecutive_errors: int = 5,
    metrics_history_size: int = 100,
    enable_auto_recovery: bool = True,
    health_check_port: int | None = None,
) -> ProcessWatchdog:
    """
    初始化全局看门狗实例
    
    Args:
        check_interval: 检查间隔（秒）
        memory_threshold_mb: 内存阈值（MB）
        cpu_threshold_percent: CPU 阈值（百分比）
        max_consecutive_errors: 最大连续错误次数
        metrics_history_size: 指标历史记录大小
        enable_auto_recovery: 是否启用自动恢复
        health_check_port: 健康检查端口
    
    Returns:
        看门狗实例
    """
    global _watchdog_instance

    if _watchdog_instance is not None:
        logger.warning("看门狗实例已存在，返回现有实例")
        return _watchdog_instance

    _watchdog_instance = ProcessWatchdog(
        check_interval=check_interval,
        memory_threshold_mb=memory_threshold_mb,
        cpu_threshold_percent=cpu_threshold_percent,
        max_consecutive_errors=max_consecutive_errors,
        metrics_history_size=metrics_history_size,
        enable_auto_recovery=enable_auto_recovery,
        health_check_port=health_check_port,
    )

    logger.info("全局看门狗实例已创建")

    return _watchdog_instance


def get_watchdog() -> ProcessWatchdog | None:
    """
    获取全局看门狗实例
    
    Returns:
        看门狗实例，如果未初始化则返回 None
    """
    return _watchdog_instance
