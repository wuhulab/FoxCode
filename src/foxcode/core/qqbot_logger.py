"""
FoxCode QQbot 日志记录模块

提供 QQbot 交互行为的日志记录功能：
- 消息收发日志
- 安全事件日志
- 操作审计日志
- 日志轮转和归档
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from foxcode.core.company_mode_config import QQbotLogConfig

logger = logging.getLogger(__name__)


class LogEventType(str, Enum):
    """日志事件类型枚举"""
    # 消息事件
    MESSAGE_RECEIVED = "message_received"       # 收到消息
    MESSAGE_SENT = "message_sent"               # 发送消息
    MESSAGE_FILTERED = "message_filtered"       # 消息被过滤
    MESSAGE_BLOCKED = "message_blocked"         # 消息被阻止
    
    # 安全事件
    SECURITY_WARNING = "security_warning"       # 安全警告
    SECURITY_BLOCK = "security_block"           # 安全阻止
    AUTHENTICATION_SUCCESS = "auth_success"     # 认证成功
    AUTHENTICATION_FAILURE = "auth_failure"     # 认证失败
    RATE_LIMIT_EXCEEDED = "rate_limit"          # 速率限制
    
    # 操作事件
    COMMAND_EXECUTED = "command_executed"       # 命令执行
    API_CALL = "api_call"                       # API 调用
    ERROR = "error"                             # 错误
    
    # 连接事件
    CONNECTED = "connected"                     # 已连接
    DISCONNECTED = "disconnected"               # 已断开
    RECONNECTED = "reconnected"                 # 已重连
    
    # 工作模式事件
    WORK_MODE_STARTED = "work_mode_started"     # 工作模式启动
    WORK_MODE_STOPPED = "work_mode_stopped"     # 工作模式停止
    TASK_STARTED = "task_started"               # 任务开始
    TASK_COMPLETED = "task_completed"           # 任务完成
    TASK_FAILED = "task_failed"                 # 任务失败
    PHASE_REPORT = "phase_report"               # 阶段报告


@dataclass
class LogEntry:
    """日志条目"""
    timestamp: str                             # 时间戳
    event_type: LogEventType                   # 事件类型
    source: str                                # 来源（用户 ID、系统等）
    content: str                               # 内容
    severity: str = "INFO"                     # 严重程度: DEBUG, INFO, WARNING, ERROR, CRITICAL
    metadata: dict[str, Any] = field(default_factory=dict)  # 元数据
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "source": self.source,
            "content": self.content,
            "severity": self.severity,
            "metadata": self.metadata,
        }
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    def to_csv_row(self) -> list[str]:
        """转换为 CSV 行"""
        return [
            self.timestamp,
            self.event_type.value,
            self.source,
            self.content[:500],  # 限制内容长度
            self.severity,
            json.dumps(self.metadata, ensure_ascii=False)[:1000],
        ]


class QQbotLogger:
    """
    QQbot 日志记录器
    
    记录所有 QQbot 交互行为和安全事件
    """
    
    CSV_HEADERS = ["timestamp", "event_type", "source", "content", "severity", "metadata"]
    
    def __init__(self, config: QQbotLogConfig, working_dir: Path | None = None):
        """
        初始化日志记录器
        
        Args:
            config: 日志配置
            working_dir: 工作目录
        """
        self.config = config
        self.working_dir = working_dir or Path.cwd()
        
        # 日志目录
        self.log_dir = self.working_dir / config.log_dir
        self._ensure_log_dir()
        
        # 当前日志文件
        self._current_log_file: Path | None = None
        self._current_log_date: str = ""
        
        # 内存中的日志缓存
        self._log_cache: list[LogEntry] = []
        self._max_cache_size = 1000
        
        # 统计信息
        self._stats: dict[str, int] = defaultdict(int)
        
        # 敏感字段模式
        self._sensitive_patterns = [
            re.compile(rf'\b{field}\b\s*[=:]\s*\S+', re.IGNORECASE)
            for field in config.sensitive_fields
        ]
        
        logger.info(f"QQbot 日志记录器初始化完成，日志目录: {self.log_dir}")
    
    def _ensure_log_dir(self) -> None:
        """确保日志目录存在"""
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"创建日志目录失败: {e}")
            raise
    
    def _get_log_file_path(self, date_str: str | None = None) -> Path:
        """
        获取日志文件路径
        
        Args:
            date_str: 日期字符串，格式 YYYY-MM-DD
            
        Returns:
            日志文件路径
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
        
        return self.log_dir / f"qqbot_{date_str}.jsonl"
    
    def _rotate_log_file(self) -> None:
        """轮转日志文件"""
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        if current_date != self._current_log_date:
            self._current_log_date = current_date
            self._current_log_file = self._get_log_file_path(current_date)
            logger.debug(f"日志文件轮转: {self._current_log_file}")
    
    def _mask_sensitive_data(self, content: str) -> str:
        """
        脱敏敏感数据
        
        Args:
            content: 原始内容
            
        Returns:
            脱敏后的内容
        """
        if not self.config.mask_sensitive_data:
            return content
        
        masked = content
        for pattern in self._sensitive_patterns:
            masked = pattern.sub("[REDACTED]", masked)
        
        return masked
    
    def log(
        self,
        event_type: LogEventType,
        source: str,
        content: str,
        severity: str = "INFO",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        记录日志
        
        Args:
            event_type: 事件类型
            source: 来源
            content: 内容
            severity: 严重程度
            metadata: 元数据
        """
        if not self.config.enable_logging:
            return
        
        # 脱敏处理
        masked_content = self._mask_sensitive_data(content)
        
        # 创建日志条目
        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            event_type=event_type,
            source=source,
            content=masked_content,
            severity=severity,
            metadata=metadata or {},
        )
        
        # 更新统计
        self._stats[event_type.value] += 1
        self._stats["total"] += 1
        
        # 添加到缓存
        self._log_cache.append(entry)
        if len(self._log_cache) > self._max_cache_size:
            self._flush_cache()
        
        # 写入文件
        self._write_entry(entry)
        
        # 记录到系统日志
        log_method = getattr(logger, severity.lower(), logger.info)
        log_method(f"[{event_type.value}] {source}: {masked_content[:100]}")
    
    def _write_entry(self, entry: LogEntry) -> None:
        """
        写入日志条目到文件
        
        Args:
            entry: 日志条目
        """
        try:
            self._rotate_log_file()
            
            if self._current_log_file:
                with open(self._current_log_file, "a", encoding="utf-8") as f:
                    f.write(entry.to_json() + "\n")
                    
        except Exception as e:
            logger.error(f"写入日志文件失败: {e}")
    
    def _flush_cache(self) -> None:
        """刷新缓存到文件"""
        if not self._log_cache:
            return
        
        try:
            self._rotate_log_file()
            
            if self._current_log_file:
                with open(self._current_log_file, "a", encoding="utf-8") as f:
                    for entry in self._log_cache:
                        f.write(entry.to_json() + "\n")
                
                self._log_cache.clear()
                
        except Exception as e:
            logger.error(f"刷新日志缓存失败: {e}")
    
    # ==================== 便捷日志方法 ====================
    
    def log_message_received(
        self,
        message_id: str,
        channel_id: str,
        author_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """记录收到消息"""
        self.log(
            event_type=LogEventType.MESSAGE_RECEIVED,
            source=author_id,
            content=f"收到消息 [{message_id}]: {content[:100]}",
            severity="INFO",
            metadata={
                "message_id": message_id,
                "channel_id": channel_id,
                **(metadata or {}),
            },
        )
    
    def log_message_sent(
        self,
        channel_id: str,
        content: str,
        success: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """记录发送消息"""
        self.log(
            event_type=LogEventType.MESSAGE_SENT,
            source="system",
            content=f"发送消息到 [{channel_id}]: {content[:100]}",
            severity="INFO" if success else "ERROR",
            metadata={
                "channel_id": channel_id,
                "success": success,
                **(metadata or {}),
            },
        )
    
    def log_message_filtered(
        self,
        author_id: str,
        content: str,
        filter_reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """记录消息被过滤"""
        self.log(
            event_type=LogEventType.MESSAGE_FILTERED,
            source=author_id,
            content=f"消息被过滤: {filter_reason}",
            severity="WARNING",
            metadata={
                "filter_reason": filter_reason,
                "original_content_preview": content[:100],
                **(metadata or {}),
            },
        )
    
    def log_message_blocked(
        self,
        author_id: str,
        content: str,
        block_reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """记录消息被阻止"""
        self.log(
            event_type=LogEventType.MESSAGE_BLOCKED,
            source=author_id,
            content=f"消息被阻止: {block_reason}",
            severity="WARNING",
            metadata={
                "block_reason": block_reason,
                "original_content_preview": content[:100],
                **(metadata or {}),
            },
        )
    
    def log_security_event(
        self,
        event_type: str,
        severity: str,
        source: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """记录安全事件"""
        log_type = (
            LogEventType.SECURITY_BLOCK
            if severity in ["ERROR", "CRITICAL"]
            else LogEventType.SECURITY_WARNING
        )
        
        self.log(
            event_type=log_type,
            source=source,
            content=f"安全事件 [{event_type}]: {content}",
            severity=severity,
            metadata={
                "security_event_type": event_type,
                **(metadata or {}),
            },
        )
    
    def log_authentication(
        self,
        success: bool,
        user_id: str,
        method: str = "token",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """记录认证事件"""
        self.log(
            event_type=(
                LogEventType.AUTHENTICATION_SUCCESS
                if success
                else LogEventType.AUTHENTICATION_FAILURE
            ),
            source=user_id,
            content=f"认证{'成功' if success else '失败'} [{method}]",
            severity="INFO" if success else "WARNING",
            metadata={
                "method": method,
                "success": success,
                **(metadata or {}),
            },
        )
    
    def log_rate_limit(
        self,
        identifier: str,
        limit_type: str,
        current_count: int,
        max_count: int,
    ) -> None:
        """记录速率限制"""
        self.log(
            event_type=LogEventType.RATE_LIMIT_EXCEEDED,
            source=identifier,
            content=f"速率限制: {limit_type} ({current_count}/{max_count})",
            severity="WARNING",
            metadata={
                "limit_type": limit_type,
                "current_count": current_count,
                "max_count": max_count,
            },
        )
    
    def log_command_executed(
        self,
        user_id: str,
        command: str,
        success: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """记录命令执行"""
        self.log(
            event_type=LogEventType.COMMAND_EXECUTED,
            source=user_id,
            content=f"执行命令: {command}",
            severity="INFO" if success else "ERROR",
            metadata={
                "command": command,
                "success": success,
                **(metadata or {}),
            },
        )
    
    def log_api_call(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        duration_ms: float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """记录 API 调用"""
        self.log(
            event_type=LogEventType.API_CALL,
            source="api",
            content=f"API 调用: {method} {endpoint} [{status_code}]",
            severity="INFO" if status_code < 400 else "WARNING",
            metadata={
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
                "duration_ms": duration_ms,
                **(metadata or {}),
            },
        )
    
    def log_error(
        self,
        error_type: str,
        message: str,
        source: str = "system",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """记录错误"""
        self.log(
            event_type=LogEventType.ERROR,
            source=source,
            content=f"错误 [{error_type}]: {message}",
            severity="ERROR",
            metadata={
                "error_type": error_type,
                **(metadata or {}),
            },
        )
    
    def log_connection(
        self,
        event_type: LogEventType,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """记录连接事件"""
        self.log(
            event_type=event_type,
            source="connection",
            content=f"连接状态变更: {event_type.value}",
            severity="INFO",
            metadata=metadata,
        )
    
    def log_work_mode(
        self,
        event_type: LogEventType,
        task_id: str | None = None,
        content: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """记录工作模式事件"""
        self.log(
            event_type=event_type,
            source="work_mode",
            content=content,
            severity="INFO",
            metadata={
                "task_id": task_id,
                **(metadata or {}),
            },
        )
    
    def log_phase_report(
        self,
        task_id: str,
        phase: str,
        status: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """记录阶段报告"""
        self.log(
            event_type=LogEventType.PHASE_REPORT,
            source="work_mode",
            content=f"阶段报告 [{task_id}] {phase}: {status}",
            severity="INFO",
            metadata={
                "task_id": task_id,
                "phase": phase,
                "status": status,
                "report_content": content,
                **(metadata or {}),
            },
        )
    
    # ==================== 日志查询方法 ====================
    
    def get_logs(
        self,
        event_type: LogEventType | None = None,
        source: str | None = None,
        severity: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[LogEntry]:
        """
        查询日志
        
        Args:
            event_type: 事件类型过滤
            source: 来源过滤
            severity: 严重程度过滤
            start_time: 开始时间
            end_time: 结束时间
            limit: 最大返回数量
            
        Returns:
            日志条目列表
        """
        results: list[LogEntry] = []
        
        # 从缓存中查询
        for entry in self._log_cache:
            if self._match_entry(entry, event_type, source, severity, start_time, end_time):
                results.append(entry)
        
        # 从文件中查询
        if len(results) < limit:
            # 确定要查询的文件
            if start_time and end_time:
                dates = self._get_date_range(start_time, end_time)
            else:
                dates = [datetime.now().strftime("%Y-%m-%d")]
            
            for date_str in dates:
                log_file = self._get_log_file_path(date_str)
                if log_file.exists():
                    file_entries = self._read_log_file(log_file)
                    for entry in file_entries:
                        if self._match_entry(entry, event_type, source, severity, start_time, end_time):
                            results.append(entry)
                            if len(results) >= limit:
                                break
                
                if len(results) >= limit:
                    break
        
        # 按时间排序
        results.sort(key=lambda e: e.timestamp, reverse=True)
        
        return results[:limit]
    
    def _match_entry(
        self,
        entry: LogEntry,
        event_type: LogEventType | None,
        source: str | None,
        severity: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> bool:
        """检查日志条目是否匹配条件"""
        if event_type and entry.event_type != event_type:
            return False
        if source and entry.source != source:
            return False
        if severity and entry.severity != severity:
            return False
        if start_time or end_time:
            try:
                entry_time = datetime.fromisoformat(entry.timestamp)
                if start_time and entry_time < start_time:
                    return False
                if end_time and entry_time > end_time:
                    return False
            except ValueError:
                pass
        return True
    
    def _get_date_range(self, start: datetime, end: datetime) -> list[str]:
        """获取日期范围列表"""
        dates = []
        current = start.date()
        end_date = end.date()
        
        while current <= end_date:
            dates.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)
        
        return dates
    
    def _read_log_file(self, file_path: Path) -> list[LogEntry]:
        """读取日志文件"""
        entries = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            entries.append(LogEntry(
                                timestamp=data["timestamp"],
                                event_type=LogEventType(data["event_type"]),
                                source=data["source"],
                                content=data["content"],
                                severity=data["severity"],
                                metadata=data.get("metadata", {}),
                            ))
                        except (json.JSONDecodeError, KeyError, ValueError):
                            continue
        except Exception as e:
            logger.error(f"读取日志文件失败 {file_path}: {e}")
        
        return entries
    
    # ==================== 日志管理方法 ====================
    
    def cleanup_old_logs(self) -> int:
        """
        清理过期日志
        
        Returns:
            清理的文件数量
        """
        if self.config.max_log_files <= 0:
            return 0
        
        try:
            # 获取所有日志文件
            log_files = sorted(
                self.log_dir.glob("qqbot_*.jsonl"),
                key=lambda f: f.name,
                reverse=True,
            )
            
            # 删除超出数量的文件
            deleted = 0
            for log_file in log_files[self.config.max_log_files:]:
                log_file.unlink()
                deleted += 1
                logger.debug(f"删除过期日志文件: {log_file}")
            
            if deleted:
                logger.info(f"清理了 {deleted} 个过期日志文件")
            
            return deleted
            
        except Exception as e:
            logger.error(f"清理日志文件失败: {e}")
            return 0
    
    def export_logs(
        self,
        output_path: Path,
        format: str = "json",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> bool:
        """
        导出日志
        
        Args:
            output_path: 输出路径
            format: 导出格式 (json, csv)
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            是否成功
        """
        try:
            entries = self.get_logs(
                start_time=start_time,
                end_time=end_time,
                limit=10000,
            )
            
            if format == "json":
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(
                        [e.to_dict() for e in entries],
                        f,
                        ensure_ascii=False,
                        indent=2,
                    )
            elif format == "csv":
                with open(output_path, "w", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(self.CSV_HEADERS)
                    for entry in entries:
                        writer.writerow(entry.to_csv_row())
            else:
                raise ValueError(f"不支持的导出格式: {format}")
            
            logger.info(f"导出 {len(entries)} 条日志到 {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"导出日志失败: {e}")
            return False
    
    def get_stats(self) -> dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        return {
            "total_logs": self._stats["total"],
            "by_event_type": {
                k: v for k, v in self._stats.items()
                if k != "total"
            },
            "cache_size": len(self._log_cache),
            "log_dir": str(self.log_dir),
        }
    
    def get_summary_report(self, hours: int = 24) -> dict[str, Any]:
        """
        获取摘要报告
        
        Args:
            hours: 统计最近多少小时
            
        Returns:
            摘要报告字典
        """
        start_time = datetime.now() - timedelta(hours=hours)
        
        # 获取最近日志
        recent_logs = self.get_logs(start_time=start_time, limit=10000)
        
        # 统计
        event_counts: dict[str, int] = defaultdict(int)
        severity_counts: dict[str, int] = defaultdict(int)
        source_counts: dict[str, int] = defaultdict(int)
        
        for entry in recent_logs:
            event_counts[entry.event_type.value] += 1
            severity_counts[entry.severity] += 1
            source_counts[entry.source] += 1
        
        return {
            "period_hours": hours,
            "total_events": len(recent_logs),
            "event_distribution": dict(event_counts),
            "severity_distribution": dict(severity_counts),
            "top_sources": dict(sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
            "errors": [
                e.to_dict() for e in recent_logs
                if e.severity in ["ERROR", "CRITICAL"]
            ][:10],
        }
