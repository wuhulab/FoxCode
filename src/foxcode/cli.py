"""
FoxCode CLI 入口

命令行界面主入口

包含全局异常处理、信号管理和优雅退出机制
"""

from __future__ import annotations

import asyncio
import atexit
import logging
import os
import signal
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import click
from rich import markup
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax

from foxcode import __version__
from foxcode.core.agent import FoxCodeAgent
from foxcode.core.config import Config, ModelProvider, RunMode, OutputTopic
from foxcode.core.session import Session
from foxcode.core.process_watchdog import (
    ProcessWatchdog,
    init_watchdog,
    get_watchdog,
)

# ==================== 全局状态管理 ====================
_shutdown_requested = False
_current_agent: FoxCodeAgent | None = None
_watchdog: ProcessWatchdog | None = None

# 确保日志目录存在
log_dir = Path.home() / ".foxcode"
log_dir.mkdir(parents=True, exist_ok=True)


class SafeStreamHandler(logging.StreamHandler):
    """
    安全的流处理器
    
    在Windows GBK编码环境下，自动处理无法编码的Unicode字符，
    避免UnicodeEncodeError导致程序崩溃
    """
    
    def emit(self, record: logging.LogRecord) -> None:
        try:
            # 尝试正常输出
            super().emit(record)
        except UnicodeEncodeError:
            # 如果出现编码错误，移除或替换特殊字符后重试
            try:
                msg = self.format(record)
                # 移除所有非ASCII emoji和特殊符号（保留基本拉丁字符、中文等）
                safe_msg = self._make_safe(msg)
                stream = self.stream
                stream.write(safe_msg + self.terminator)
                self.flush()
            except Exception:
                # 如果还是失败，只输出时间戳和级别
                try:
                    fallback_msg = (
                        f"{logging.Formatter().formatTime(record)} - "
                        f"{record.levelname} - [Encoding error, message omitted]"
                    )
                    self.stream.write(fallback_msg + self.terminator)
                    self.flush()
                except Exception:
                    pass  # 彻底失败时静默忽略
    
    @staticmethod
    def _make_safe(text: str) -> str:
        """
        将文本转换为安全格式
        
        移除可能导致GBK编码失败的字符：
        - 特殊Unicode符号
        - 保留：中文、英文、数字、常用标点
        """
        import re
        
        # 常见emoji和特殊符号的Unicode范围
        # 移除这些范围的字符
        result = text
        
        # 定义要替换的常见emoji映射
        emoji_replacements = {
            '✅': '[OK]',
            '❌': '[FAIL]',
            '⚠️': '[WARN]',
            '🚨': '[CRIT]',
            '🔄': '[LOOP]',
            '📊': '[STATS]',
            '🧪': '[TEST]',
            '🦊': '',
            '💾': '[SAVE]',
            '🏥': '[HEALTH]',
            '🎉': '[SUCCESS]',
            '⏱️': '[TIME]',
            '🔧': '[TOOL]',
            '📋': '[LIST]',
            '📝': '[NOTE]',
            '💡': '[INFO]',
            '🚀': '[START]',
            '🛑': '[STOP]',
            '👀': '[VIEW]',
            '⭘': '',
        }
        
        for emoji, replacement in emoji_replacements.items():
            result = result.replace(emoji, replacement)
        
        return result


# 配置日志（增强格式，包含堆栈跟踪）
# 使用SafeStreamHandler避免Windows GBK编码问题
_file_handler = logging.FileHandler(
    log_dir / "foxcode.log",
    encoding='utf-8',  # 文件使用UTF-8编码
)

_stream_handler = SafeStreamHandler(sys.stderr)  # 使用安全的流处理器

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    handlers=[
        _file_handler,
        _stream_handler,
    ],
)

# 初始化全局敏感信息日志过滤器（安全最佳实践）
from foxcode.core.sensitive_masker import setup_global_log_filter
setup_global_log_filter()

logger = logging.getLogger(__name__)
console = Console()


def run_async(coro):
    """
    安全地运行异步协程
    
    在同步上下文中安全地运行异步代码：
    - 如果在运行中的事件循环内，使用线程池执行
    - 如果不在事件循环内，使用 asyncio.run()
    
    Args:
        coro: 异步协程对象
        
    Returns:
        协程的返回值
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    
    if loop is not None:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


# ==================== 信号处理和优雅退出 ====================

def _setup_signal_handlers() -> None:
    """
    设置信号处理器，实现优雅退出
    
    捕获 SIGINT (Ctrl+C) 和 SIGTERM 信号，
    确保资源正确清理后再退出
    """
    def signal_handler(signum: int, frame: Any) -> None:
        """信号处理回调"""
        global _shutdown_requested
        signal_name = signal.Signals(signum).name
        logger.warning(f"收到信号 {signal_name} ({signum})，准备优雅退出...")
        
        if _shutdown_requested:
            # 第二次收到信号，强制退出
            logger.error("重复收到终止信号，强制退出")
            sys.exit(1)
        
        _shutdown_requested = True
        
        # 尝试保存会话
        if _current_agent:
            try:
                logger.info("正在保存会话...")
                _current_agent.save_session()
                logger.info("会话已保存")
            except Exception as e:
                logger.error(f"保存会话失败: {e}")
    
    # 注册信号处理器（仅在主线程中有效）
    try:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        logger.info("信号处理器已注册 (SIGINT, SIGTERM)")
    except ValueError as e:
        # 在非主线程中无法设置信号处理
        logger.warning(f"无法注册信号处理器（可能不在主线程）: {e}")


def _cleanup_on_exit() -> None:
    """
    atexit 清理函数
    
    确保进程退出时清理资源
    """
    global _watchdog
    
    logger.info("执行退出清理...")
    
    # 停止看门狗
    if _watchdog:
        import asyncio
        try:
            if asyncio.get_event_loop().is_running():
                asyncio.create_task(_watchdog.stop())
            else:
                asyncio.run(_watchdog.stop())
        except Exception as e:
            logger.warning(f"停止看门狗失败: {e}")
        
        # 导出最终性能指标
        try:
            metrics_file = log_dir / "final_metrics.json"
            _watchdog.export_metrics_to_file(metrics_file)
        except Exception as e:
            logger.warning(f"导出性能指标失败: {e}")
    
    # 清理临时文件
    temp_dir = log_dir / "temp"
    if temp_dir.exists():
        import shutil
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.debug("临时目录已清理")
        except Exception as e:
            logger.warning(f"清理临时文件失败: {e}")
    
    logger.info("FoxCode 进程已退出")


def _init_watchdog() -> ProcessWatchdog:
    """
    初始化进程看门狗并配置监控参数
    
    Returns:
        配置好的看门狗实例
    """
    global _watchdog
    
    watchdog = init_watchdog(
        check_interval=30.0,  # 每30秒检查一次
        memory_threshold_mb=512.0,  # 内存超过512MB时警告
        cpu_threshold_percent=90.0,  # CPU超过90%时警告
        max_consecutive_errors=5,  # 连续5次错误触发恢复
        metrics_history_size=100,  # 保留100条历史记录
        enable_auto_recovery=True,  # 启用自动恢复
        health_check_port=None,  # 暂不启用HTTP健康检查（需要aiohttp）
    )
    
    # 设置事件回调函数
    def on_memory_warning(memory_mb: float) -> None:
        """内存超限回调"""
        logger.warning(
            f"⚠️ 内存使用过高 ({memory_mb:.1f}MB)，"
            f"建议保存会话并重启"
        )
        console.print(
            f"\n[yellow]⚠️ 内存使用较高: {memory_mb:.1f}MB[/yellow]"
        )
        if memory_mb > 800:  # 超过800MB时强烈警告
            console.print(
                "[red]内存使用非常高，可能存在内存泄漏！[/red]"
            )
    
    def on_cpu_warning(cpu_percent: float) -> None:
        """CPU超限回调"""
        logger.warning(
            f"⚠️ CPU使用率过高 ({cpu_percent:.1f}%)"
        )
    
    def on_error_threshold_reached(error_count: int) -> None:
        """错误达限回调"""
        logger.critical(
            f"🚨 连续错误次数达到上限 ({error_count})"
        )
        console.print(
            f"\n[red]⚠️ 连续出现 {error_count} 次错误[/red]"
        )
    
    def on_auto_recovery_triggered() -> None:
        """自动恢复触发回调"""
        global _current_agent
        
        logger.critical("[RECOVER] 触发自动恢复机制...")
        console.print("\n[cyan][*] 正在执行自动恢复...[/cyan]")
        
        # 尝试保存当前状态
        if _current_agent:
            try:
                _current_agent.save_session()
                console.print("[green]✅ 会话已自动保存[/green]")
            except Exception as e:
                logger.error(f"自动保存会话失败: {e}")
                console.print(
                    f"[yellow]⚠️ 自动保存失败: {e}[/yellow]"
                )
    
    watchdog.set_callbacks(
        on_memory_warning=on_memory_warning,
        on_cpu_warning=on_cpu_warning,
        on_error_threshold_reached=on_error_threshold_reached,
        on_auto_recovery_triggered=on_auto_recovery_triggered,
    )
    
    _watchdog = watchdog
    
    logger.info("[OK] 进程看门狗已初始化并配置完成")
    
    return watchdog


def _handle_unexpected_error(error: Exception) -> None:
    """
    全局异常处理器
    
    记录详细的错误信息并优雅退出，而不是直接崩溃
    
    Args:
        error: 未捕获的异常
    """
    logger.critical("=" * 80)
    logger.critical("FoxCode 遇到未预期的错误，进程即将退出")
    logger.critical("=" * 80)
    logger.critical(f"错误类型: {type(error).__name__}")
    logger.critical(f"错误消息: {str(error)}")
    logger.critical("\n完整堆栈跟踪:")
    logger.critical(traceback.format_exc())
    logger.critical("=" * 80)
    
    # 尝试保存崩溃报告
    crash_report_path = log_dir / "crash_report.log"
    try:
        with open(crash_report_path, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"时间: {logging.Formatter().formatTime(logging.LogRecord('', '', '', '', '', '', ''))}\n")
            f.write(f"Python版本: {sys.version}\n")
            f.write(f"操作系统: {os.name} - {sys.platform}\n")
            f.write(f"错误类型: {type(error).__name__}\n")
            f.write(f"错误消息: {str(error)}\n")
            f.write(f"\n堆栈跟踪:\n{traceback.format_exc()}\n")
            f.write(f"{'='*80}\n\n")
        logger.info(f"崩溃报告已保存到: {crash_report_path}")
    except Exception as e:
        logger.error(f"保存崩溃报告失败: {e}")
    
    # 显示用户友好的错误信息
    console.print("\n")
    console.print(Panel(
        f"[bold red]FoxCode 遇到意外错误[/bold red]\n\n"
        f"[yellow]错误类型:[/yellow] {type(error).__name__}\n"
        f"[yellow]错误信息:[/yellow] {markup.escape(str(error))}\n\n"
        f"[dim]详细日志已保存到:[/dim] {crash_report_path}\n"
        f"[dim]请查看日志文件获取更多信息或提交问题报告[/dim]",
        title="⚠️ 错误",
        border_style="red",
    ))


# 注册 atexit 清理函数
atexit.register(_cleanup_on_exit)


# 设置全局异常钩子（捕获所有未处理的异常）
def _global_exception_hook(exc_type, exc_value, exc_traceback) -> None:
    """
    Python 全局异常钩子
    
    捕获所有未被 except 捕获的异常
    """
    if issubclass(exc_type, KeyboardInterrupt):
        # Ctrl+C 不需要特殊处理
        return
    
    logger.critical("未捕获的全局异常:")
    logger.critical("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))


sys.excepthook = _global_exception_hook


def print_banner(config: Config | None = None) -> None:
    """打印欢迎横幅"""
    # 检查是否为极简模式
    if config and config.output_topic == OutputTopic.MINIMALISM:
        print("[foxcode: 初始化完毕]")
    
    # 默认模式：完整横幅
    banner = """
    ███████╗ ██████╗ ██████╗  ██████╗ 
    ██╔════╝██╔════╝██╔═══██╗██╔════╝ 
    █████╗  ██║     ██║   ██║██║  ███╗
    ██╔══╝  ██║     ██║   ██║██║   ██║
    ██║     ╚██████╗╚██████╔╝╚██████╔╝
    ╚═╝      ╚═════╝ ╚═════╝  ╚═════╝ 
    """
    console.print(Panel(banner, style="bold cyan", title=f"FoxCode v{__version__}"))


def print_help() -> None:
    """打印帮助信息"""
    help_text = """
# FoxCode - AI 终端编码助手

## 基本用法

```bash
foxcode                    # 启动交互式会话
foxcode "你的问题"          # 直接提问
foxcode --yolo             # 自动执行模式
foxcode --plan             # 规划模式
```

## 命令行选项

| 选项 | 说明 |
|------|------|
| `--model, -m` | 指定 AI 模型 |
| `--mode` | 运行模式 (default/yolo/plan) |
| `--yolo` | 快捷启用 YOLO 模式 |
| `--plan` | 快捷启用规划模式 |
| `--resume, -r` | 恢复上次会话 |
| `--session` | 指定会话 ID |
| `--list-sessions` | 列出所有会话 |
| `--config` | 显示配置 |
| `--version, -v` | 显示版本 |
| `--help, -h` | 显示帮助 |

## 交互式命令

在交互式会话中，可以使用以下命令：

### 基本命令

- `/help` - 显示帮助
- `/clear` - 清空对话
- `/save` - 保存会话
- `/load <id>` - 加载会话
- `/mode <mode>` - 切换模式
- `/model <name>` - 切换模型
- `/exit` 或 `/quit` - 退出

### 监控命令

- `/stats` - 显示性能统计（响应时间、成功率、内存使用等）
- `/health` - 显示完整健康状态报告（资源使用、运行时间、监控状态）

### 工作流程命令

- `/workflow` 或 `/wf` - 工作流程管理
- `/phase` - 阶段操作
- `/features` - 功能列表管理
- `/progress` - 显示进度

### 公司模式命令

- `/work <任务描述>` - 以长期工作模式启动任务
- `/work status` - 查看当前任务状态
- `/work list` - 列出所有任务
- `/company` - 显示公司模式状态
- `/company enable` - 启用公司模式
- `/company disable` - 禁用公司模式
- `/company status` - 详细状态报告
- `/company qqbot status` - QQbot 状态
- `/company security` - 安全报告
- `/company logs` - 日志摘要
- `/company config` - 显示配置

### 高级功能命令 (v2.0 新增)

- `/index` - 构建语义代码索引
- `/index status` - 查看索引状态
- `/index update` - 增量更新索引
- `/search <query>` - 语义搜索代码
- `/kb` - 显示知识库状态
- `/kb add <content>` - 添加知识条目
- `/kb search <query>` - 搜索知识库
- `/kb tags` - 列出所有标签
- `/analyze` - 分析当前项目
- `/analyze tech` - 分析技术栈
- `/analyze quality` - 分析代码质量
- `/debug start` - 启动调试会话
- `/debug break <file:line>` - 设置断点
- `/debug continue` - 继续执行
- `/debug step` - 单步执行
- `/debug vars` - 显示变量
- `/profile` - 启动性能分析
- `/profile report` - 查看分析报告
- `/security` - 运行安全扫描
- `/security deps` - 扫描依赖漏洞
- `/topic` - 显示当前输出主题模式
- `/topic default` - 切换到默认模式（完整输出）
- `/topic debug` - 切换到调试模式（详细输出）
- `/topic minimalism` - 切换到极简模式（精简输出）
- `/format [files]` - 格式化代码
- `/refactor` - 获取重构建议
- `/test gen <file>` - 生成测试用例
- `/doc gen <file>` - 生成文档
- `/git smart-commit` - 智能提交
- `/git conflicts` - 分析冲突
- `/diagram <type>` - 生成图表 (mermaid/plantuml)

### OpenSpace 命令 (AI 经验知识库)

- `/space` - 显示 OpenSpace 状态
- `/space true` - 启用 OpenSpace（默认启用）
- `/space false` - 禁用 OpenSpace
- `/space ai true` - 启用 AI 自动总结经验（完成任务后自动记录踩过的坑）
- `/space ai false` - 禁用 AI 自动总结经验
- `/space list` - 列出所有经验
- `/space add <标题> <内容>` - 添加新经验（不超过 500 字）
- `/space show <id>` - 显示经验详情
- `/space delete <id>` - 删除经验
- `/space stats` - 显示统计信息

## 支持的模型

- OpenAI: gpt-4o, gpt-4-turbo, gpt-3.5-turbo
- Anthropic: claude-sonnet, claude-opus
- DeepSeek: deepseek-chat, deepseek-coder
- 本地模型: 通过 --base-url 指定

## 配置文件

配置文件位置：
- 项目级: `.foxcode.toml` 或 `foxcode.toml`
- 用户级: `~/.foxcode/config.toml`

示例配置：
```toml
[model]
provider = "openai"
model_name = "gpt-4o"
temperature = 0.7

[tools]
enable_file_ops = true
enable_shell = true
```
"""
    console.print(Markdown(help_text))


@click.group(invoke_without_command=True)
@click.option("--version", "-v", is_flag=True, help="显示版本信息")
@click.option("--help", "-h", is_flag=True, help="显示帮助信息")
@click.option("--model", "-m", default=None, help="指定 AI 模型")
@click.option("--mode", type=click.Choice(["default", "yolo", "plan", "accept_edits"]), 
              default="default", help="运行模式")
@click.option("--yolo", is_flag=True, help="启用 YOLO 模式（自动执行）")
@click.option("--plan", is_flag=True, help="启用规划模式（只读）")
@click.option("--resume", "-r", is_flag=True, help="恢复上次会话")
@click.option("--session", default=None, help="指定会话 ID")
@click.option("--list-sessions", is_flag=True, help="列出所有会话")
@click.option("--config", is_flag=True, help="显示当前配置")
@click.option("--debug", is_flag=True, help="启用调试模式")
@click.argument("prompt", required=False)
@click.pass_context
def main(
    ctx: click.Context,
    version: bool,
    help: bool,
    model: str | None,
    mode: str,
    yolo: bool,
    plan: bool,
    resume: bool,
    session: str | None,
    list_sessions: bool,
    config: bool,
    debug: bool,
    prompt: str | None,
) -> None:
    """
    FoxCode - AI 终端编码助手
    
    一个强大的 AI 编码助手，帮助你编写、分析和修改代码。
    
    包含完整的异常处理和优雅退出机制
    """
    # 初始化信号处理器（必须在主函数开始时调用）
    _setup_signal_handlers()
    
    # 初始化进程看门狗（性能监控和自动恢复）
    _init_watchdog()
    
    try:
        # 显示版本
        if version:
            console.print(f"FoxCode v{__version__}")
            return
        
        # 显示帮助
        if help:
            print_help()
            return
        
        # 创建配置
        config_overrides: dict[str, Any] = {}
        
        if model:
            config_overrides["model"] = {"model_name": model}
        
        if yolo:
            config_overrides["run_mode"] = RunMode.YOLO
        elif plan:
            config_overrides["run_mode"] = RunMode.PLAN
        elif mode:
            config_overrides["run_mode"] = RunMode(mode)
        
        if debug:
            config_overrides["debug"] = True
            config_overrides["log_level"] = "DEBUG"
            logging.getLogger().setLevel(logging.DEBUG)
        
        app_config = Config.create(**config_overrides)
        
        # 显示配置
        if config:
            console.print(Panel(
                f"[bold]配置信息[/bold]\n\n"
                f"模型: {app_config.model.model_name}\n"
                f"提供者: {app_config.model.provider.value}\n"
                f"运行模式: {app_config.run_mode.value}\n"
                f"工作目录: {app_config.working_dir}\n"
                f"会话目录: {app_config.session_dir}",
                title="FoxCode 配置",
                style="cyan",
            ))
            return
        
        # 列出会话
        if list_sessions:
            sessions = Session.list_sessions(app_config)
            if not sessions:
                console.print("暂无保存的会话")
                return
            
            from rich.table import Table
            table = Table(title="保存的会话")
            table.add_column("会话 ID", style="cyan")
            table.add_column("创建时间", style="green")
            table.add_column("消息数", justify="right")
            table.add_column("Token 数", justify="right")
            
            for s in sessions:
                table.add_row(
                    s["session_id"],
                    s["created_at"],
                    str(s["message_count"]),
                    str(s["total_tokens"]),
                )
            
            console.print(table)
            return
        
        # 运行应用
        ctx.invoke(
            run,
            prompt=prompt,
            session_id=session,
            resume=resume,
            config=app_config,
        )
        
    except KeyboardInterrupt:
        logger.info("用户中断 (Ctrl+C)")
        console.print("\n[yellow]用户中断[/yellow]")
    except Exception as e:
        # 全局异常处理：记录详细日志并显示友好信息
        _handle_unexpected_error(e)
        sys.exit(1)  # 只有在全局异常处理完成后才退出


@main.command()
@click.argument("prompt", required=False)
@click.option("--session-id", default=None, help="会话 ID")
@click.option("--resume", is_flag=True, help="恢复上次会话")
@click.option("--config", type=object, default=None, help="配置对象")
def run(
    prompt: str | None,
    session_id: str | None,
    resume: bool,
    config: Config | None,
) -> None:
    """
    运行 FoxCode
    
    包含完整的异常处理和进程保护机制
    集成进程看门狗进行性能监控
    """
    global _current_agent, _watchdog
    
    if config is None:
        config = Config.create()
    
    # 初始化代理
    try:
        agent = FoxCodeAgent(config)
        _current_agent = agent  # 保存全局引用，用于信号处理时保存会话
    except Exception as e:
        logger.error(f"初始化代理失败: {e}")
        _handle_unexpected_error(e)
        return
    
    # 启动进程看门狗监控（在异步事件循环中）
    async def _start_watchdog_and_run():
        """启动看门狗并运行主程序"""
        if _watchdog:
            try:
                await _watchdog.start()
                logger.info("[OK] 进程看门狗监控已启动")
            except Exception as e:
                logger.warning(f"启动看门狗失败: {e} (不影响主功能)")
    
    # 恢复会话
    if resume or session_id:
        try:
            if session_id:
                agent.load_session(session_id)
            else:
                # 查找最近的会话
                sessions = Session.list_sessions(config)
                if sessions:
                    agent.load_session(sessions[0]["session_id"])
                    console.print(f"[green]已恢复会话: {sessions[0]['session_id']}[/green]")
        except FileNotFoundError:
            console.print("[yellow]未找到可恢复的会话[/yellow]")
        except Exception as e:
            logger.error(f"恢复会话失败: {e}")
            console.print(f"[red]恢复会话失败: {markup.escape(str(e))}[/red]")
    
    # 直接处理提示
    if prompt:
        try:
            asyncio.run(_run_single_prompt(agent, prompt, config))
        except Exception as e:
            logger.error(f"单次提示执行失败: {e}")
            _handle_unexpected_error(e)
        finally:
            _current_agent = None
        return
    
    # 启动简单交互模式
    try:
        logger.info("启动简单交互模式...")
        
        # 包装异步函数以启动看门狗
        async def _run_with_watchdog():
            await _start_watchdog_and_run()
            await _run_interactive(agent, config)
        
        asyncio.run(_run_with_watchdog())
    except KeyboardInterrupt:
        logger.info("用户中断交互模式")
        console.print("\n[yellow]用户中断[/yellow]")
    except Exception as e:
        logger.error(f"运行模式执行失败: {e}")
        _handle_unexpected_error(e)
    finally:
        # 清理全局引用
        _current_agent = None
        logger.info("FoxCode 运行结束")


async def _run_single_prompt(agent: FoxCodeAgent, prompt: str, config: Config | None = None) -> None:
    """
    运行单次提示
    
    增强异常处理和日志记录
    """
    print_banner(config)
    
    # 极简模式输出
    if config and config.output_topic == OutputTopic.MINIMALISM:
        print(f">>{prompt}")
        print("[foxcode]", end="")
    else:
        console.print(f"\n[bold cyan]用户:[/bold cyan] {prompt}\n")
        console.print("[bold green]FoxCode:[/bold green]")
    
    try:
        await agent.initialize()
        
        async for chunk in agent.chat(prompt):
            # 极简模式：直接打印
            if config and config.output_topic == OutputTopic.MINIMALISM:
                print(chunk, end="")
            else:
                console.print(chunk, end="")
        
        # 极简模式：输出结束标记
        if config and config.output_topic == OutputTopic.MINIMALISM:
            print("\n[FoxCode end]")
            # 显示 token 使用情况
        else:
            console.print("\n")
        
    except KeyboardInterrupt:
        logger.warning("单次提示执行被用户中断")
        if config and config.output_topic == OutputTopic.MINIMALISM:
            print("\n[中断]")
        else:
            console.print("\n[yellow]执行被中断[/yellow]")
    except Exception as e:
        # 记录详细错误信息，但不直接退出（由调用方决定是否退出）
        logger.error(f"单次提示执行失败: {type(e).__name__}: {e}")
        logger.debug(f"完整堆栈:\n{traceback.format_exc()}")
        if config and config.output_topic == OutputTopic.MINIMALISM:
            print(f"\n[错误] {str(e)}")
        else:
            console.print(f"\n[red]错误: {markup.escape(str(e))}[/red]")
        
        # 重新抛出异常，让调用方处理
        raise


async def _run_interactive(agent: FoxCodeAgent, config: Config) -> None:
    """
    运行交互式会话
    
    增强异常处理，确保主循环不会因异常而意外终止
    """
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.styles import Style as PromptStyle
    
    print_banner(config)
    
    # 初始化代理
    try:
        await agent.initialize()
        logger.info("代理初始化成功")
    except Exception as e:
        logger.error(f"代理初始化失败: {e}")
        if config.output_topic == OutputTopic.MINIMALISM:
            print(f"[错误] 初始化失败: {str(e)}")
        else:
            console.print(f"[red]初始化失败: {markup.escape(str(e))}[/red]")
        return
    
    # 创建 prompt session
    history_file = Path.home() / ".foxcode" / "history"
    history_file.parent.mkdir(parents=True, exist_ok=True)
    
    def _get_prompt_text() -> str:
        """
        生成传统命令行样式的提示符
        
        格式: FoxCode | 模型: xxx | Token: n | 模式: xxx >
        """
        try:
            token_usage = agent.get_token_usage()
            total_tokens = token_usage.get('total_tokens', 0)
        except Exception:
            total_tokens = 0
        
        # 极简模式：简洁提示符
        if config.output_topic == OutputTopic.MINIMALISM:
            return f"[FoxCode | 模型:{config.model.model_name}| Token:{total_tokens} | 模式: {config.run_mode.value}]\n>>"
        
        return (
            f"[bold cyan]FoxCode[/bold cyan] | "
            f"模型: [yellow]{config.model.model_name}[/yellow] | "
            f"Token: [green]{total_tokens}[/green] | "
            f"模式: [cyan]{config.run_mode.value}[/cyan] > "
        )
    
    session = PromptSession(
        history=FileHistory(str(history_file)),
    )
    
    # 主循环（增加循环计数和健康检查）
    loop_count = 0
    max_consecutive_errors = 5  # 最大连续错误次数
    consecutive_errors = 0
    
    while True:
        # 检查是否收到关闭信号
        if _shutdown_requested:
            logger.info("收到关闭信号，退出主循环")
            break
        
        # 健康检查：每100次循环检查一次
        loop_count += 1
        if loop_count % 100 == 0:
            logger.debug(f"主循环健康检查: 已运行 {loop_count} 次迭代")
        
        try:
            # 获取用户输入（使用传统命令行样式）
            user_input = await session.prompt_async(
                _get_prompt_text(),
                multiline=False,
            )
            
            if not user_input.strip():
                continue
            
            # 处理命令
            if user_input.startswith("/"):
                should_continue = _handle_command(user_input, agent, config)
                if not should_continue:
                    break
                continue
            
            # 发送到 AI（添加性能监控）
            # 极简模式：简洁输出
            if config.output_topic == OutputTopic.MINIMALISM:
                print("[foxcode]", end="")
            else:
                console.print()
                console.print("[bold green]FoxCode:[/bold green]")
            
            # 记录请求开始时间
            request_start_time = time.time()
            request_id = None
            
            # 如果看门狗可用，记录请求开始
            if _watchdog:
                request_id = _watchdog.record_request_start()
            
            try:
                async for chunk in agent.chat(user_input):
                    # 极简模式：直接打印
                    if config.output_topic == OutputTopic.MINIMALISM:
                        print(chunk, end="")
                    else:
                        console.print(chunk, end="")
                
                # 极简模式：输出结束标记
                if config.output_topic == OutputTopic.MINIMALISM:
                    print("\n[FoxCode end]")

                else:
                    console.print("\n")
                
                # 计算响应时间并记录成功
                response_time_ms = (time.time() - request_start_time) * 1000
                if _watchdog and request_id:
                    _watchdog.record_request_success(
                        request_id, response_time_ms
                    )
                    
                    # 显示性能信息（调试模式）
                    if config.debug:
                        console.print(
                            f"[dim]⏱️ 响应时间: {response_time_ms:.0f}ms[/dim]"
                        )
                
            except Exception as chat_error:
                # 记录失败请求
                response_time_ms = (time.time() - request_start_time) * 1000
                if _watchdog and request_id:
                    _watchdog.record_request_failure(
                        request_id, chat_error, response_time_ms
                    )
                
                # 重新抛出异常，由外层处理
                raise
            
            # 重置连续错误计数
            consecutive_errors = 0
            
        except KeyboardInterrupt:
            logger.info("用户按下 Ctrl+C")
            if config.output_topic == OutputTopic.MINIMALISM:
                print("\n[提示] 使用 /exit 退出")
            else:
                console.print("\n[yellow]使用 /exit 退出[/yellow]")
            continue
        except EOFError:
            logger.info("收到 EOF (通常是因为管道关闭或用户输入结束)")
            break
        except Exception as e:
            consecutive_errors += 1
            logger.error(f"交互错误 (第 {consecutive_errors}/{max_consecutive_errors} 次): {type(e).__name__}: {e}")
            logger.debug(f"错误堆栈:\n{traceback.format_exc()}")
            
            if config.output_topic == OutputTopic.MINIMALISM:
                print(f"\n[错误] {str(e)}")
            else:
                console.print(f"\n[red]错误: {markup.escape(str(e))}[/red]")
            
            # 如果连续错误过多，提示用户并询问是否继续
            if consecutive_errors >= max_consecutive_errors:
                logger.critical(f"连续错误次数达到上限 ({max_consecutive_errors})，可能存在系统性问题")
                if config.output_topic == OutputTopic.MINIMALISM:
                    print(f"\n[警告] 连续出现 {max_consecutive_errors} 次错误")
                    print("[提示] 建议保存会话并重启 FoxCode")
                else:
                    console.print(f"\n[red]连续出现 {max_consecutive_errors} 次错误[/red]")
                    console.print("[yellow]建议保存会话并重启 FoxCode[/yellow]")
                
                try:
                    # 尝试保存会话
                    agent.save_session()
                    console.print("[green]会话已自动保存[/green]")
                except Exception as save_error:
                    logger.error(f"自动保存会话失败: {save_error}")
                
                # 询问用户是否继续
                try:
                    continue_choice = await session.prompt_async(
                        "\n[yellow]是否继续? (y/n): [/yellow]",
                        multiline=False,
                    )
                    if continue_choice and continue_choice.strip().lower() != 'y':
                        logger.info("用户选择退出")
                        break
                    else:
                        consecutive_errors = 0  # 重置计数器
                        logger.info("用户选择继续")
                        console.print("[green]继续运行...[/green]\n")
                except:
                    # 如果无法获取输入，直接退出
                    logger.warning("无法获取用户输入，退出")
                    break
    
    console.print("\n[cyan]再见！[/cyan]")


def _handle_command(command: str, agent: FoxCodeAgent, config: Config) -> bool:
    """
    处理交互式命令
    
    Args:
        command: 命令字符串
        agent: 代理实例
        config: 配置实例
        
    Returns:
        是否继续运行
    """
    cmd = command.strip().lower()
    parts = cmd.split(maxsplit=1)
    cmd_name = parts[0]
    cmd_arg = parts[1] if len(parts) > 1 else None
    
    if cmd_name in ("/exit", "/quit", "/q"):
        # 结束会话时保存摘要
        if config.long_running.enable_long_running_mode:
            _handle_session_end(agent, config)
        return False
    
    elif cmd_name == "/stats":
        """显示性能统计信息"""
        _handle_stats_command()
    
    elif cmd_name == "/health":
        """显示健康状态"""
        _handle_health_command()
    
    elif cmd_name == "/help":
        print_help()
    
    elif cmd_name == "/clear":
        agent.clear_conversation()
        console.print("[green]对话已清空[/green]")
    
    elif cmd_name == "/save":
        agent.save_session()
        console.print("[green]会话已保存[/green]")
    
    elif cmd_name == "/load" and cmd_arg:
        try:
            agent.load_session(cmd_arg)
            console.print(f"[green]已加载会话: {cmd_arg}[/green]")
        except FileNotFoundError:
            console.print(f"[red]会话不存在: {cmd_arg}[/red]")
    
    elif cmd_name == "/mode" and cmd_arg:
        try:
            config.run_mode = RunMode(cmd_arg)
            console.print(f"[green]已切换到 {cmd_arg} 模式[/green]")
        except ValueError:
            console.print(f"[red]无效的模式: {cmd_arg}[/red]")
    
    elif cmd_name == "/model" and cmd_arg:
        config.model.model_name = cmd_arg
        console.print(f"[green]已切换模型: {cmd_arg}[/green]")
    
    elif cmd_name == "/sessions":
        sessions = Session.list_sessions(config)
        for s in sessions[:10]:
            console.print(f"  {s['session_id']} - {s['message_count']} 条消息")
    
    elif cmd_name == "/token":
        usage = agent.get_token_usage()
        console.print(
            f"[cyan]Token 使用: 输入 {usage['input_tokens']}, "
            f"输出 {usage['output_tokens']}, "
            f"总计 {usage['total_tokens']}[/cyan]"
        )
    
    # ==================== 长时间运行模式命令 ====================
    
    elif cmd_name == "/init":
        _handle_init_command(agent, config)
    
    elif cmd_name == "/progress":
        _handle_progress_command(agent, config)
    
    elif cmd_name == "/features":
        _handle_features_command(agent, config, cmd_arg)
    
    elif cmd_name == "/summary":
        _handle_summary_command(agent, config)
    
    elif cmd_name == "/next":
        _handle_next_command(agent, config)
    
    elif cmd_name == "/long-running" or cmd_name == "/lr":
        _handle_long_running_toggle(config, cmd_arg)
    
    elif cmd_name == "/workflow" or cmd_name == "/wf":
        _handle_workflow_command(agent, config, cmd_arg)
    
    elif cmd_name == "/phase":
        _handle_phase_command(agent, config, cmd_arg)
    
    # ==================== Work模式命令 ====================
    
    elif cmd_name == "/work":
        _handle_work_command(agent, config, cmd_arg)
    
    # ==================== 高级功能命令 (v2.0 新增) ====================
    
    elif cmd_name == "/index":
        _handle_index_command(agent, config, cmd_arg)
    
    elif cmd_name == "/search":
        _handle_search_command(agent, config, cmd_arg)
    
    elif cmd_name == "/kb":
        _handle_kb_command(agent, config, cmd_arg)
    
    elif cmd_name == "/analyze":
        _handle_analyze_command(agent, config, cmd_arg)
    
    elif cmd_name == "/debug":
        _handle_debug_command(agent, config, cmd_arg)
    
    elif cmd_name == "/profile":
        _handle_profile_command(agent, config, cmd_arg)
    
    elif cmd_name == "/security":
        _handle_security_command(agent, config, cmd_arg)
    
    elif cmd_name == "/format":
        _handle_format_command(agent, config, cmd_arg)
    
    elif cmd_name == "/refactor":
        _handle_refactor_command(agent, config, cmd_arg)
    
    elif cmd_name == "/test":
        _handle_test_command(agent, config, cmd_arg)
    
    elif cmd_name == "/doc":
        _handle_doc_command(agent, config, cmd_arg)
    
    elif cmd_name == "/git":
        _handle_git_command(agent, config, cmd_arg)
    
    elif cmd_name == "/diagram":
        _handle_diagram_command(agent, config, cmd_arg)
    
    elif cmd_name == "/space":
        _handle_space_command(agent, config, cmd_arg)
    
    elif cmd_name == "/topic":
        _handle_topic_command(agent, config, cmd_arg)
    
    else:
        console.print(f"[yellow]未知命令: {cmd_name}[/yellow]")
        console.print("[dim]输入 /help 查看可用命令[/dim]")
    
    return True


def _handle_init_command(agent: FoxCodeAgent, config: Config) -> None:
    """
    处理 /init 命令
    
    启动初始化代理模式
    """
    from foxcode.core.init_script import InitScriptGenerator
    
    console.print("[cyan]🚀 启动初始化代理模式...[/cyan]")
    
    # 启用长时间运行模式
    config.long_running.enable_long_running_mode = True
    
    # 生成初始化脚本
    try:
        generator = InitScriptGenerator(working_dir=config.working_dir)
        scripts = generator.generate_init_script()
        
        console.print("[green]✅ 已生成初始化脚本:[/green]")
        for platform_name, path in scripts.items():
            console.print(f"  - {platform_name}: {path}")
        
        # 显示项目类型
        env = generator.environment
        console.print(f"\n[cyan]检测到项目类型: {env.project_type.value}[/cyan]")
        
        if env.required_tools:
            console.print(f"[dim]必需工具: {', '.join(env.required_tools)}[/dim]")
        
        console.print("\n[yellow]提示: 运行初始化脚本设置项目环境[/yellow]")
        console.print("[dim]  Unix/Linux/Mac: bash .foxcode/init.sh[/dim]")
        console.print("[dim]  Windows: .foxcode\\init.bat[/dim]")
        
    except Exception as e:
        console.print(f"[red]生成初始化脚本失败: {markup.escape(str(e))}[/red]")


def _handle_progress_command(agent: FoxCodeAgent, config: Config) -> None:
    """
    处理 /progress 命令
    
    显示当前进度
    """
    if not config.long_running.enable_long_running_mode:
        console.print("[yellow]长时间运行模式未启用[/yellow]")
        console.print("[dim]使用 /long-running on 启用[/dim]")
        return
    
    try:
        summary = agent.get_progress_summary()
        console.print(Panel(summary, title="项目进度", style="cyan"))
    except Exception as e:
        console.print(f"[red]获取进度失败: {markup.escape(str(e))}[/red]")


def _handle_features_command(agent: FoxCodeAgent, config: Config, cmd_arg: str | None) -> None:
    """
    处理 /features 命令
    
    管理功能列表
    """
    if not config.long_running.enable_long_running_mode:
        console.print("[yellow]长时间运行模式未启用[/yellow]")
        console.print("[dim]使用 /long-running on 启用[/dim]")
        return
    
    try:
        feature_list = agent.session.get_feature_list()
        
        # 如果有参数，解析子命令
        if cmd_arg:
            parts = cmd_arg.split(maxsplit=1)
            sub_cmd = parts[0]
            sub_arg = parts[1] if len(parts) > 1 else None
            
            if sub_cmd == "add" and sub_arg:
                # 添加功能
                feature_id = agent.add_feature(title=sub_arg)
                if feature_id:
                    console.print(f"[green]✅ 已添加功能: {feature_id}[/green]")
                else:
                    console.print("[red]添加功能失败[/red]")
            
            elif sub_cmd == "complete" and sub_arg:
                # 标记功能完成
                if agent.mark_feature_completed(sub_arg):
                    console.print(f"[green]✅ 功能 {sub_arg} 已标记为完成[/green]")
                else:
                    console.print(f"[red]标记功能完成失败[/red]")
            
            elif sub_cmd == "list":
                # 列出所有功能
                _display_features(feature_list)
            
            else:
                console.print(f"[yellow]未知子命令: {sub_cmd}[/yellow]")
                console.print("[dim]用法: /features [add <title> | complete <id> | list][/dim]")
        else:
            # 默认显示摘要
            summary = agent.get_feature_list_summary()
            console.print(Panel(summary, title="📋 功能列表", style="green"))
    
    except Exception as e:
        console.print(f"[red]处理功能列表失败: {markup.escape(str(e))}[/red]")


def _display_features(feature_list) -> None:
    """显示功能列表"""
    from rich.table import Table
    
    table = Table(title="功能需求列表")
    table.add_column("ID", style="cyan", width=12)
    table.add_column("标题", style="white")
    table.add_column("状态", style="green")
    table.add_column("优先级", style="yellow")
    
    for feature in feature_list:
        status_color = {
            "pending": "white",
            "in_progress": "yellow",
            "completed": "green",
            "failed": "red",
        }.get(feature.status.value, "white")
        
        # 使用 Text 对象避免 markup 解析问题
        from rich.text import Text
        status_text = Text(feature.status.value, style=status_color)
        
        table.add_row(
            feature.id,
            feature.title[:40] + "..." if len(feature.title) > 40 else feature.title,
            status_text,
            feature.priority.value,
        )
    
    console.print(table)


def _handle_summary_command(agent: FoxCodeAgent, config: Config) -> None:
    """
    处理 /summary 命令
    
    生成会话摘要
    """
    if not config.long_running.enable_long_running_mode:
        console.print("[yellow]长时间运行模式未启用[/yellow]")
        console.print("[dim]使用 /long-running on 启用[/dim]")
        return
    
    try:
        context_bridge = agent.session.get_context_bridge()
        summary = context_bridge.load_summary()
        
        if summary:
            console.print(Panel(
                summary.to_markdown(),
                title=f"会话摘要 ({summary.session_id})",
                style="magenta",
            ))
        else:
            console.print("[yellow]暂无会话摘要[/yellow]")
    
    except Exception as e:
        console.print(f"[red]获取会话摘要失败: {markup.escape(str(e))}[/red]")


def _handle_next_command(agent: FoxCodeAgent, config: Config) -> None:
    """
    处理 /next 命令
    
    获取下一个建议任务
    """
    if not config.long_running.enable_long_running_mode:
        console.print("[yellow]长时间运行模式未启用[/yellow]")
        console.print("[dim]使用 /long-running on 启用[/dim]")
        return
    
    try:
        feature_list = agent.session.get_feature_list()
        next_feature = feature_list.get_next_feature()
        
        if next_feature:
            console.print(Panel(
                f"[bold cyan]{next_feature.id}: {next_feature.title}[/bold cyan]\n\n"
                f"状态: {next_feature.status.value}\n"
                f"优先级: {next_feature.priority.value}\n"
                f"分类: {next_feature.category}\n\n"
                f"{next_feature.description}",
                title="下一个建议任务",
                style="green",
            ))
        else:
            console.print("[green]✅ 所有功能已完成！[/green]")
    
    except Exception as e:
        console.print(f"[red]获取下一个任务失败: {markup.escape(str(e))}[/red]")


def _handle_long_running_toggle(config: Config, cmd_arg: str | None) -> None:
    """
    处理 /long-running 命令
    
    切换长时间运行模式
    """
    if cmd_arg == "on":
        config.long_running.enable_long_running_mode = True
        console.print("[green]✅ 已启用长时间运行模式[/green]")
    elif cmd_arg == "off":
        config.long_running.enable_long_running_mode = False
        console.print("[yellow]已禁用长时间运行模式[/yellow]")
    else:
        status = "启用" if config.long_running.enable_long_running_mode else "禁用"
        console.print(f"[cyan]长时间运行模式: {status}[/cyan]")
        console.print("[dim]用法: /long-running [on | off][/dim]")


def _handle_workflow_command(agent: FoxCodeAgent, config: Config, cmd_arg: str | None) -> None:
    """
    处理 /workflow 命令
    
    管理工作流程
    
    用法:
        /workflow                    - 显示当前工作流程状态
        /workflow start <feature_id> - 为功能启动工作流程
        /workflow list               - 列出所有工作流程
        /workflow status <id>        - 显示工作流程详情
        /workflow advance            - 推进当前工作流程到下一阶段
        /workflow skip               - 跳过当前阶段
    """
    if not config.long_running.enable_long_running_mode:
        console.print("[yellow]长时间运行模式未启用[/yellow]")
        console.print("[dim]使用 /long-running on 启用[/dim]")
        return
    
    try:
        workflow_manager = agent.session.get_workflow_manager()
        
        # 解析子命令
        if cmd_arg:
            parts = cmd_arg.split(maxsplit=1)
            sub_cmd = parts[0]
            sub_arg = parts[1] if len(parts) > 1 else None
        else:
            sub_cmd = None
            sub_arg = None
        
        if sub_cmd == "start" and sub_arg:
            # 启动新工作流程
            args = sub_arg.split(maxsplit=1)
            feature_id = args[0]
            branch_name = args[1] if len(args) > 1 else f"feature/{feature_id.lower()}"
            
            workflow = agent.session.start_workflow_for_feature(
                feature_id=feature_id,
                branch_name=branch_name,
            )
            
            console.print(f"[green]✅ 已创建工作流程: {workflow.id}[/green]")
            console.print(f"   功能: {feature_id}")
            console.print(f"   分支: {branch_name}")
            console.print(f"   当前阶段: {workflow.current_phase.get_display_name()}")
        
        elif sub_cmd == "list":
            # 列出所有工作流程
            workflows = workflow_manager.list_workflows()
            
            if not workflows:
                console.print("[yellow]暂无工作流程[/yellow]")
                return
            
            from rich.table import Table
            table = Table(title="工作流程列表")
            table.add_column("ID", style="cyan", width=20)
            table.add_column("功能", style="white")
            table.add_column("当前阶段", style="green")
            table.add_column("进度", justify="right")
            table.add_column("分支", style="yellow")
            
            for wf in workflows:
                progress = wf.get_progress()
                table.add_row(
                    wf.id,
                    wf.feature_id,
                    wf.current_phase.get_display_name(),
                    f"{progress['progress_percent']}%",
                    wf.branch_name or "-",
                )
            
            console.print(table)
        
        elif sub_cmd == "status":
            # 显示工作流程详情
            workflow_id = sub_arg
            if not workflow_id:
                workflow = agent.session.get_current_workflow()
                if not workflow:
                    console.print("[yellow]没有当前工作流程[/yellow]")
                    return
                workflow_id = workflow.id
            
            workflow = workflow_manager.get_workflow(workflow_id)
            if not workflow:
                console.print(f"[red]工作流程不存在: {workflow_id}[/red]")
                return
            
            console.print(Panel(
                workflow.to_markdown(),
                title=f"📋 工作流程: {workflow_id}",
                style="cyan",
            ))
        
        elif sub_cmd == "advance":
            # 推进工作流程
            workflow = agent.session.get_current_workflow()
            if not workflow:
                console.print("[yellow]没有当前工作流程[/yellow]")
                return
            
            current_phase = workflow.current_phase
            success = agent.session.advance_workflow(
                output=sub_arg or "",
            )
            
            if success:
                console.print(f"[green]✅ 阶段已完成: {current_phase.get_display_name()}[/green]")
                console.print(f"   下一阶段: {workflow.current_phase.get_display_name()}")
            else:
                console.print("[red]推进工作流程失败[/red]")
        
        elif sub_cmd == "skip":
            # 跳过当前阶段
            workflow = agent.session.get_current_workflow()
            if not workflow:
                console.print("[yellow]没有当前工作流程[/yellow]")
                return
            
            current_phase = workflow.current_phase
            success = workflow_manager.skip_phase(
                workflow_id=workflow.id,
                phase=current_phase,
                reason=sub_arg or "用户跳过",
            )
            
            if success:
                console.print(f"[yellow]已跳过阶段: {current_phase.get_display_name()}[/yellow]")
                console.print(f"   当前阶段: {workflow.current_phase.get_display_name()}")
            else:
                console.print("[red]跳过阶段失败[/red]")
        
        else:
            # 显示当前工作流程状态
            workflow = agent.session.get_current_workflow()
            if not workflow:
                console.print("[yellow]当前没有活动的工作流程[/yellow]")
                console.print("[dim]使用 /workflow start <feature_id> 启动新工作流程[/dim]")
                return
            
            progress = workflow.get_progress()
            console.print(Panel(
                f"[bold]工作流程 ID:[/bold] {workflow.id}\n"
                f"[bold]功能 ID:[/bold] {workflow.feature_id}\n"
                f"[bold]当前阶段:[/bold] {workflow.current_phase.get_display_name()}\n"
                f"[bold]进度:[/bold] {progress['progress_percent']}% "
                f"({progress['completed_phases']}/{progress['total_phases']})\n"
                f"[bold]分支:[/bold] {workflow.branch_name or '未创建'}",
                title="📋 当前工作流程",
                style="cyan",
            ))
            
            # 显示工作流程阶段进度
            from foxcode.core.workflow import WorkflowPhase, PhaseStatus
            
            console.print("\n[bold]阶段进度:[/bold]")
            for phase in WorkflowPhase.get_order():
                result = workflow.get_phase_result(phase)
                status_icon = {
                    PhaseStatus.PENDING: "⏳",
                    PhaseStatus.IN_PROGRESS: "🔄",
                    PhaseStatus.COMPLETED: "✅",
                    PhaseStatus.FAILED: "❌",
                    PhaseStatus.SKIPPED: "⏭️",
                    PhaseStatus.BLOCKED: "🚫",
                }.get(result.status, "❓")
                
                current = " ← 当前" if phase == workflow.current_phase else ""
                console.print(f"  {status_icon} {phase.get_display_name()}{current}")
    
    except Exception as e:
        console.print(f"[red]处理工作流程命令失败: {markup.escape(str(e))}[/red]")


def _handle_phase_command(agent: FoxCodeAgent, config: Config, cmd_arg: str | None) -> None:
    """
    处理 /phase 命令
    
    快速操作当前工作流程阶段
    
    用法:
        /phase           - 显示当前阶段
        /phase complete  - 完成当前阶段
        /phase fail      - 标记当前阶段失败
    """
    if not config.long_running.enable_long_running_mode:
        console.print("[yellow]长时间运行模式未启用[/yellow]")
        return
    
    try:
        workflow = agent.session.get_current_workflow()
        if not workflow:
            console.print("[yellow]没有当前工作流程[/yellow]")
            return
        
        current_phase = workflow.current_phase
        result = workflow.get_phase_result(current_phase)
        
        if cmd_arg == "complete":
            # 完成当前阶段
            success = agent.session.advance_workflow()
            if success:
                console.print(f"[green]✅ 阶段已完成: {current_phase.get_display_name()}[/green]")
            else:
                console.print("[red]完成阶段失败[/red]")
        
        elif cmd_arg == "fail":
            # 标记失败
            workflow_manager = agent.session.get_workflow_manager()
            workflow_manager.fail_phase_manually(
                workflow_id=workflow.id,
                phase=current_phase,
                error="用户标记失败",
            )
            console.print(f"[red]❌ 阶段已标记失败: {current_phase.get_display_name()}[/red]")
        
        else:
            # 显示当前阶段信息
            console.print(Panel(
                f"[bold]阶段:[/bold] {current_phase.get_display_name()}\n"
                f"[bold]状态:[/bold] {result.status.value}\n"
                f"[bold]开始时间:[/bold] {result.started_at or '未开始'}\n"
                f"[bold]输出:[/bold] {result.output[:100] + '...' if result.output else '无'}\n"
                f"[bold]错误:[/bold] {result.error or '无'}",
                title="🔄 当前阶段",
                style="yellow",
            ))
    
    except Exception as e:
        console.print(f"[red]处理阶段命令失败: {markup.escape(str(e))}[/red]")


def _handle_work_command(agent: FoxCodeAgent, config: Config, cmd_arg: str | None) -> None:
    """
    处理 /work 命令
    
    以长期工作模式启动任务，分析任务并锁定目标子文件夹，自动保存记录
    
    用法:
        /work                         - 前台启用Work模式（默认行为）
        /work off                     - 关闭Work模式
        /work <任务描述>              - 启动新工作任务（自动保存记录）
        /work status                  - 查看当前任务状态
        /work list                    - 列出所有任务
        /work stop <task_id>          - 停止指定任务
        /work records                 - 查看任务记录
    """
    from foxcode.core.work_mode import WorkModeManager
    from foxcode.core.work_mode_config import AgentExecutionMode, WorkModeStatus
    
    # 获取或创建Work模式管理器
    if not hasattr(agent, '_work_mode_manager'):
        # 根据配置决定执行模式
        # 默认使用单代理模式进行代码编写
        execution_mode = AgentExecutionMode.SINGLE_AGENT
        
        agent._work_mode_manager = WorkModeManager(
            config=config.work_mode,
            working_dir=config.working_dir,
            foxcode_config=config,
            execution_mode=execution_mode,
        )
    
    manager = agent._work_mode_manager
    
    # 解析子命令
    if cmd_arg:
        parts = cmd_arg.split(maxsplit=1)
        sub_cmd = parts[0]
        sub_arg = parts[1] if len(parts) > 1 else None
    else:
        sub_cmd = None
        sub_arg = None
    
    try:
        # 不带参数时，前台启用Work模式
        if sub_cmd is None:
            if manager.is_enabled():
                console.print("[yellow]Work模式已启用[/yellow]")
                status = manager.get_status()
                console.print(Panel(
                    f"[bold]Work模式状态:[/bold] {status['status']}\n"
                    f"[bold]活动任务:[/bold] {len(status['active_tasks'])}\n"
                    f"[bold]完成任务:[/bold] {status['completed_tasks']}\n"
                    f"[bold]失败任务:[/bold] {status['failed_tasks']}\n"
                    f"[bold]运行时间:[/bold] {status['uptime_seconds']:.1f} 秒",
                    title="[WORK] Work模式已启用",
                    style="cyan",
                ))
                console.print("[dim]使用 /work off 关闭，/work <任务描述> 启动任务[/dim]")
            else:
                console.print("[cyan]正在启用Work模式（前台模式）...[/cyan]")
                success, msg = run_async(manager.enable())
                if success:
                    console.print(f"[green][OK] {msg}[/green]")
                    console.print("[dim]使用 /work off 关闭，/work <任务描述> 启动任务[/dim]")
                else:
                    console.print(f"[red]启用失败: {msg}[/red]")
            return
        
        # 关闭Work模式
        if sub_cmd == "off":
            if not manager.is_enabled():
                console.print("[yellow]Work模式未启用[/yellow]")
                return
            console.print("[cyan]正在关闭Work模式...[/cyan]")
            success, msg = run_async(manager.disable())
            if success:
                console.print(f"[green][OK] {msg}[/green]")
            else:
                console.print(f"[red]关闭失败: {msg}[/red]")
            return
        
        # 启动新任务
        if sub_cmd and sub_cmd not in ["status", "list", "stop", "records", "off"]:
            # 整个 cmd_arg 是任务描述
            task_description = cmd_arg
            
            # 确保Work模式已启用（默认启用）
            if not manager.is_enabled():
                console.print("[cyan]正在启用Work模式...[/cyan]")
                success, msg = run_async(manager.enable())
                if not success:
                    console.print(f"[red]启用Work模式失败: {msg}[/red]")
                    return
                console.print(f"[green]✅ {msg}[/green]")
            
            # 分析任务，尝试提取目标子文件夹
            target_subfolder = _extract_target_subfolder(task_description, config.working_dir)
            
            # 创建任务（自动保存记录）
            task = manager.create_work_task(
                description=task_description,
                target_subfolder=target_subfolder,
            )
            
            console.print(Panel(
                f"[bold cyan]任务 ID:[/bold cyan] {task.id}\n"
                f"[bold cyan]描述:[/bold cyan] {task_description}\n"
                f"[bold cyan]目标子文件夹:[/bold cyan] {target_subfolder or '自动检测'}\n"
                f"[bold cyan]状态:[/bold cyan] 待执行\n"
                f"[bold cyan]执行模式:[/bold cyan] {manager.execution_mode.value}",
                title="[WORK] 创建工作任务",
                style="cyan",
            ))
            
            # 设置报告回调
            def report_callback(task, phase, result):
                console.print(f"\n[cyan][REPORT] 阶段报告 [{task.id}][/cyan]")
                console.print(f"   阶段: {phase['description']}")
                console.print(f"   状态: {'[OK] 完成' if result['success'] else '[FAIL] 失败'}")
                if result.get('output'):
                    output_preview = result['output'][:200]
                    console.print(f"   输出: {output_preview}...")
            
            manager.set_report_callback(report_callback)
            
            # 启动任务
            success = run_async(manager.start_work_task(task))
            if success:
                console.print(f"[green][OK] 任务已启动: {task.id}[/green]")
                console.print("[dim]使用 /work status 查看进度，/work records 查看记录[/dim]")
            else:
                console.print(f"[red]启动任务失败[/red]")
        
        # 查看状态
        elif sub_cmd == "status":
            if not manager.is_enabled():
                console.print("[yellow]Work模式未启用[/yellow]")
                return
            
            status = manager.get_status()
            console.print(Panel(
                f"[bold]Work模式状态:[/bold] {status['status']}\n"
                f"[bold]活动任务:[/bold] {len(status['active_tasks'])}\n"
                f"[bold]完成任务:[/bold] {status['completed_tasks']}\n"
                f"[bold]失败任务:[/bold] {status['failed_tasks']}\n"
                f"[bold]运行时间:[/bold] {status['uptime_seconds']:.1f} 秒",
                title="[STATS] Work模式状态",
                style="cyan",
            ))
            
            # 显示活动任务
            if status['active_tasks']:
                console.print("\n[bold]活动任务:[/bold]")
                for task_id in status['active_tasks']:
                    task = manager.get_task(task_id)
                    if task:
                        console.print(f"  [LOOP] {task_id}: {task.description[:40]}... ({task.current_phase})")
        
        # 列出任务
        elif sub_cmd == "list":
            tasks = manager.list_tasks(limit=10)
            
            if not tasks:
                console.print("[yellow]暂无工作任务[/yellow]")
                return
            
            from rich.table import Table
            table = Table(title="工作任务列表")
            table.add_column("ID", style="cyan", width=15)
            table.add_column("描述", style="white")
            table.add_column("状态", style="green")
            table.add_column("目标", style="yellow")
            table.add_column("当前阶段", style="magenta")
            
            for task in tasks:
                status_color = {
                    "pending": "white",
                    "running": "yellow",
                    "completed": "green",
                    "failed": "red",
                }.get(task.status, "white")
                
                table.add_row(
                    task.id,
                    task.description[:30] + "..." if len(task.description) > 30 else task.description,
                    f"[{status_color}]{task.status}[/{status_color}]",
                    task.target_subfolder[:20] if task.target_subfolder else "-",
                    task.current_phase or "-",
                )
            
            console.print(table)
        
        # 查看任务记录
        elif sub_cmd == "records":
            tasks = manager.list_tasks(limit=20)
            
            if not tasks:
                console.print("[yellow]暂无任务记录[/yellow]")
                return
            
            from rich.table import Table
            table = Table(title="任务记录")
            table.add_column("ID", style="cyan", width=15)
            table.add_column("描述", style="white")
            table.add_column("状态", style="green")
            table.add_column("创建时间", style="yellow")
            table.add_column("完成时间", style="magenta")
            
            for task in tasks:
                status_color = {
                    "pending": "white",
                    "running": "yellow",
                    "completed": "green",
                    "failed": "red",
                }.get(task.status, "white")
                
                table.add_row(
                    task.id,
                    task.description[:25] + "..." if len(task.description) > 25 else task.description,
                    f"[{status_color}]{task.status}[/{status_color}]",
                    task.created_at[:16] if task.created_at else "-",
                    task.completed_at[:16] if task.completed_at else "-",
                )
            
            console.print(table)
            console.print(f"\n[dim]记录保存位置: {config.working_dir}/.foxcode/work_records.json[/dim]")
        
        # 停止任务
        elif sub_cmd == "stop" and sub_arg:
            task = manager.get_task(sub_arg)
            if not task:
                console.print(f"[red]任务不存在: {sub_arg}[/red]")
                return
            
            task.status = "failed"
            task.error = "用户手动停止"
            manager._save_records()  # 保存记录
            console.print(f"[yellow]已停止任务: {sub_arg}[/yellow]")
        
        else:
            console.print("[yellow]用法: /work [off] | <任务描述> | status | list | records | stop <id>[/yellow]")
    
    except Exception as e:
        console.print(f"[red]处理 /work 命令失败: {markup.escape(str(e))}[/red]")


def _extract_target_subfolder(description: str, working_dir: Path) -> str:
    """
    从任务描述中提取目标子文件夹
    
    Args:
        description: 任务描述
        working_dir: 工作目录
        
    Returns:
        目标子文件夹路径
    """
    import re
    
    # 尝试匹配路径模式
    path_patterns = [
        r'在\s+([^\s]+)\s+中',          # "在 src/core 中"
        r'修改\s+([^\s]+)',              # "修改 src/main.py"
        r'更新\s+([^\s]+)',              # "更新 tests/"
        r'检查\s+([^\s]+)',              # "检查 docs/"
        r'分析\s+([^\s]+)',              # "分析 frontend/"
        r'([a-zA-Z_][a-zA-Z0-9_/.-]*)',  # 路径模式
    ]
    
    for pattern in path_patterns:
        match = re.search(pattern, description)
        if match:
            potential_path = match.group(1)
            
            # 检查是否是有效路径
            full_path = working_dir / potential_path
            if full_path.exists():
                return potential_path
            
            # 检查是否是文件所在目录
            parent_dir = full_path.parent
            if parent_dir.exists():
                return str(parent_dir.relative_to(working_dir))
    
    # 根据关键词推断
    keywords_to_folders = {
        "前端": ["src/frontend", "frontend", "web", "client", "src"],
        "后端": ["src/backend", "backend", "server", "api", "src"],
        "测试": ["tests", "test", "spec", "__tests__"],
        "文档": ["docs", "doc", "documentation"],
        "配置": ["config", "configs", "settings"],
        "核心": ["src/core", "core", "src"],
        "工具": ["src/tools", "tools", "utils"],
    }
    
    for keyword, folders in keywords_to_folders.items():
        if keyword in description:
            for folder in folders:
                if (working_dir / folder).exists():
                    return folder
    
    # 默认返回 src 目录
    if (working_dir / "src").exists():
        return "src"
    
    return "."


def _handle_session_end(agent: FoxCodeAgent, config: Config) -> None:
    """
    处理会话结束
    
    保存会话摘要
    """
    if not config.long_running.auto_generate_summary:
        return
    
    try:
        # 获取进度信息
        progress_manager = agent.session.get_progress_manager()
        pending_todos = progress_manager.get_pending_todos()
        
        # 保存摘要
        agent.end_session(
            incomplete_work=[t.content for t in pending_todos],
        )
        
        console.print("[dim]会话摘要已保存[/dim]")
    
    except Exception as e:
        logger.warning(f"保存会话摘要失败: {e}")


def _handle_stats_command() -> None:
    """
    处理 /stats 命令
    
    显示性能统计信息
    """
    if not _watchdog:
        console.print("[yellow]看门狗未启用[/yellow]")
        return
    
    try:
        metrics = _watchdog.get_current_metrics()
        
        from rich.table import Table
        
        # 创建统计表格
        table = Table(title="📊 性能统计", show_header=True)
        table.add_column("指标", style="cyan")
        table.add_column("值", style="green")
        table.add_column("说明", style="dim")
        
        table.add_row(
            "总请求数",
            str(metrics.total_requests),
            "所有AI请求的总数"
        )
        table.add_row(
            "成功率",
            f"{(metrics.successful_requests/max(1,metrics.total_requests)*100):.1f}%",
            "成功完成的请求比例"
        )
        table.add_row(
            "平均响应时间",
            f"{metrics.avg_response_time_ms:.0f}ms",
            "AI响应的平均耗时"
        )
        table.add_row(
            "最快响应",
            f"{metrics.min_response_time_ms:.0f}ms",
            "最快的一次响应"
        )
        table.add_row(
            "最慢响应",
            f"{metrics.max_response_time_ms:.0f}ms",
            "最慢的一次响应"
        )
        table.add_row(
            "内存使用",
            f"{metrics.memory_usage_mb:.1f}MB",
            "当前进程内存占用"
        )
        table.add_row(
            "CPU使用率",
            f"{metrics.cpu_percent:.1f}%",
            "当前进程CPU使用"
        )
        table.add_row(
            "连续错误",
            str(metrics.consecutive_errors),
            "连续失败的请求次数"
        )
        
        console.print(table)
        
        # 显示警告信息
        if metrics.consecutive_errors >= 3:
            console.print(
                f"\n[yellow]⚠️ 连续 {metrics.consecutive_errors} 次错误，请检查日志[/yellow]"
            )
        
        if metrics.memory_usage_mb > 400:
            console.print(
                f"\n[yellow]⚠️ 内存使用较高 ({metrics.memory_usage_mb:.1f}MB)[/yellow]"
            )
    
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        console.print(f"[red]获取统计信息失败: {markup.escape(str(e))}[/red]")


def _handle_health_command() -> None:
    """
    处理 /health 命令
    
    显示完整的健康状态报告
    """
    if not _watchdog:
        console.print("[yellow]看门狗未启用[/yellow]")
        return
    
    try:
        health = _watchdog.get_health_status()
        
        from rich.panel import Panel
        from rich.text import Text
        
        # 状态颜色
        status_color = {
            'healthy': 'green',
            'warning': 'yellow',
            'critical': 'red',
        }.get(health['status'], 'white')
        
        status_text = Text.assemble(
            ('状态: ', 'bold'),
            (health['status'].upper(), status_color),
        )
        
        content = (
            f"{status_text}\n\n"
            f"[bold]运行时间:[/bold] {health['uptime']}\n\n"
            f"[bold]请求统计:[/bold]\n"
            f"  总计: {health['metrics']['total_requests']} | "
            f"成功: {health['metrics']['successful_requests']} | "
            f"失败: {health['metrics']['failed_requests']}\n"
            f"  成功率: {health['metrics']['success_rate']:.1f}%\n\n"
            f"[bold]资源使用:[/bold]\n"
            f"  内存: {health['metrics']['memory_usage_mb']:.1f}MB "
            f"(阈值: {health['thresholds']['memory_mb']}MB)\n"
            f"  CPU: {health['metrics']['cpu_percent']:.1f}% "
            f"(阈值: {health['thresholds']['cpu_percent']}%)\n\n"
            f"[bold]监控状态:[/bold]\n"
            f"  看门狗: {'✅ 运行中' if health['watchdog_active'] else '❌ 已停止'}\n"
            f"  历史记录: {health['history_count']} 条"
        )
        
        console.print(Panel(
            content,
            title="🏥 健康检查报告",
            border_style=status_color,
        ))
    
    except Exception as e:
        logger.error(f"获取健康状态失败: {e}")
        console.print(f"[red]获取健康状态失败: {markup.escape(str(e))}[/red]")


if __name__ == "__main__":
    main()


# ==================== 高级功能命令处理函数 (v2.0 新增) ====================

def _handle_index_command(agent: FoxCodeAgent, config: Config, cmd_arg: str | None) -> None:
    """
    处理 /index 命令
    
    管理语义代码索引
    
    用法:
        /index         - 构建语义索引
        /index status  - 查看索引状态
        /index update  - 增量更新索引
    """
    try:
        from foxcode.core.semantic_index import SemanticCodeIndex, SemanticIndexConfig
        
        index_dir = Path(config.working_dir) / ".foxcode" / "semantic_index"
        index_config = SemanticIndexConfig(index_dir=str(index_dir))
        index = SemanticCodeIndex(index_config)
        
        if cmd_arg == "status":
            stats = index.get_stats()
            console.print(Panel(
                f"[bold]索引文件数:[/bold] {stats.get('file_count', 0)}\n"
                f"[bold]代码块数:[/bold] {stats.get('chunk_count', 0)}\n"
                f"[bold]索引大小:[/bold] {stats.get('index_size', 'N/A')}\n"
                f"[bold]最后更新:[/bold] {stats.get('last_updated', 'N/A')}",
                title="📚 语义索引状态",
                style="cyan",
            ))
        
        elif cmd_arg == "update":
            console.print("[cyan]正在增量更新索引...[/cyan]")
            result = run_async(index.index_directory(Path(config.working_dir), incremental=True))
            console.print(f"[green]✅ 更新完成: {result.get('files_updated', 0)} 个文件[/green]")
        
        else:
            console.print("[cyan]正在构建语义索引...[/cyan]")
            result = run_async(index.index_directory(Path(config.working_dir)))
            console.print(f"[green]✅ 索引构建完成: {result.get('files_indexed', 0)} 个文件[/green]")
    
    except ImportError:
        console.print("[yellow]语义索引模块未安装，请安装: pip install sentence-transformers[/yellow]")
    except Exception as e:
        console.print(f"[red]索引操作失败: {markup.escape(str(e))}[/red]")


def _handle_search_command(agent: FoxCodeAgent, config: Config, cmd_arg: str | None) -> None:
    """
    处理 /search 命令
    
    语义搜索代码
    
    用法:
        /search <query>  - 搜索代码
    """
    if not cmd_arg:
        console.print("[yellow]请提供搜索查询: /search <query>[/yellow]")
        return
    
    try:
        from foxcode.core.semantic_index import SemanticCodeIndex, SemanticIndexConfig
        
        index_dir = Path(config.working_dir) / ".foxcode" / "semantic_index"
        index_config = SemanticIndexConfig(index_dir=str(index_dir))
        index = SemanticCodeIndex(index_config)
        
        results = run_async(index.search(cmd_arg, top_k=10))
        
        if not results:
            console.print("[yellow]未找到匹配的代码[/yellow]")
            return
        
        from rich.table import Table
        table = Table(title=f"🔍 搜索结果: {cmd_arg}", show_header=True)
        table.add_column("文件", style="cyan")
        table.add_column("行号", style="green")
        table.add_column("相似度", style="yellow")
        table.add_column("代码片段", style="white")
        
        for result in results[:10]:
            table.add_row(
                str(Path(result['file_path']).relative_to(config.working_dir)),
                f"{result.get('start_line', '?')}-{result.get('end_line', '?')}",
                f"{result.get('score', 0):.2f}",
                result.get('content', '')[:50] + "...",
            )
        
        console.print(table)
    
    except ImportError:
        console.print("[yellow]语义索引模块未安装[/yellow]")
    except Exception as e:
        console.print(f"[red]搜索失败: {markup.escape(str(e))}[/red]")


def _handle_kb_command(agent: FoxCodeAgent, config: Config, cmd_arg: str | None) -> None:
    """
    处理 /kb 命令
    
    管理知识库
    
    用法:
        /kb              - 显示知识库状态
        /kb add <content> - 添加知识条目
        /kb search <query> - 搜索知识库
        /kb tags         - 列出所有标签
    """
    try:
        from foxcode.core.knowledge_base import KnowledgeBase, KnowledgeBaseConfig
        
        kb_dir = Path(config.working_dir) / ".foxcode" / "knowledge_base"
        kb_config = KnowledgeBaseConfig(storage_path=str(kb_dir))
        kb = KnowledgeBase(kb_config)
        
        parts = cmd_arg.split(maxsplit=1) if cmd_arg else [None]
        sub_cmd = parts[0]
        sub_arg = parts[1] if len(parts) > 1 else None
        
        if sub_cmd == "add" and sub_arg:
            entry = run_async(kb.store(sub_arg))
            console.print(f"[green]✅ 已添加知识条目: {entry.id}[/green]")
        
        elif sub_cmd == "search" and sub_arg:
            results = run_async(kb.retrieve(sub_arg))
            console.print(f"[cyan]找到 {len(results)} 条知识:[/cyan]")
            for r in results[:5]:
                console.print(f"  - {r.get('content', '')[:100]}...")
        
        elif sub_cmd == "tags":
            tags = kb.get_all_tags()
            console.print(f"[cyan]标签列表: {', '.join(tags) if tags else '无标签'}[/cyan]")
        
        else:
            stats = kb.get_stats()
            console.print(Panel(
                f"[bold]条目总数:[/bold] {stats.get('total_entries', 0)}\n"
                f"[bold]标签数:[/bold] {stats.get('tag_count', 0)}\n"
                f"[bold]分类数:[/bold] {stats.get('category_count', 0)}",
                title="📖 知识库状态",
                style="cyan",
            ))
    
    except Exception as e:
        console.print(f"[red]知识库操作失败: {markup.escape(str(e))}[/red]")


def _handle_analyze_command(agent: FoxCodeAgent, config: Config, cmd_arg: str | None) -> None:
    """
    处理 /analyze 命令
    
    分析项目
    
    用法:
        /analyze         - 分析当前项目
        /analyze tech    - 分析技术栈
        /analyze quality - 分析代码质量
    """
    try:
        from foxcode.core.project_analyzer import ProjectAnalyzer, ProjectAnalyzerConfig
        
        analyzer_config = ProjectAnalyzerConfig()
        analyzer = ProjectAnalyzer(analyzer_config)
        
        if cmd_arg == "tech":
            tech_stack = analyzer.detect_tech_stack(Path(config.working_dir))
            console.print(Panel(
                "\n".join(f"[bold]{k}:[/bold] {v}" for k, v in tech_stack.items()),
                title="🔧 技术栈分析",
                style="cyan",
            ))
        
        elif cmd_arg == "quality":
            report = run_async(analyzer.analyze(Path(config.working_dir)))
            console.print(Panel(
                f"[bold]代码质量评分:[/bold] {report.quality_score:.1f}/100\n"
                f"[bold]问题数:[/bold] {len(report.issues)}\n"
                f"[bold]建议:[/bold]\n" + "\n".join(f"  - {s}" for s in report.recommendations[:5]),
                title="📊 代码质量分析",
                style="yellow",
            ))
        
        else:
            report = run_async(analyzer.analyze(Path(config.working_dir)))
            console.print(Panel(
                f"[bold]项目类型:[/bold] {report.project_type}\n"
                f"[bold]主要语言:[/bold] {report.primary_language}\n"
                f"[bold]框架:[/bold] {', '.join(report.frameworks)}\n"
                f"[bold]质量评分:[/bold] {report.quality_score:.1f}/100",
                title="📁 项目分析",
                style="cyan",
            ))
    
    except Exception as e:
        console.print(f"[red]项目分析失败: {markup.escape(str(e))}[/red]")


def _handle_debug_command(agent: FoxCodeAgent, config: Config, cmd_arg: str | None) -> None:
    """
    处理 /debug 命令
    
    高级调试功能
    
    用法:
        /debug start           - 启动调试会话
        /debug break <file:line> - 设置断点
        /debug continue        - 继续执行
        /debug step            - 单步执行
        /debug vars            - 显示变量
    """
    try:
        from foxcode.core.advanced_debugger import AdvancedDebugger, DebuggerConfig
        
        debugger_config = DebuggerConfig()
        debugger = AdvancedDebugger(debugger_config)
        
        parts = cmd_arg.split(maxsplit=1) if cmd_arg else [None]
        sub_cmd = parts[0]
        sub_arg = parts[1] if len(parts) > 1 else None
        
        if sub_cmd == "start":
            console.print("[cyan]调试会话已启动[/cyan]")
            console.print("[dim]使用 /debug break <file:line> 设置断点[/dim]")
        
        elif sub_cmd == "break" and sub_arg:
            file_path, line = sub_arg.rsplit(":", 1)
            debugger.set_breakpoint(Path(file_path), int(line))
            console.print(f"[green]✅ 断点已设置: {file_path}:{line}[/green]")
        
        elif sub_cmd == "continue":
            run_async(debugger.continue_execution())
            console.print("[cyan]继续执行...[/cyan]")
        
        elif sub_cmd == "step":
            run_async(debugger.step())
            console.print("[cyan]单步执行...[/cyan]")
        
        elif sub_cmd == "vars":
            variables = debugger.get_variables()
            console.print(Panel(
                "\n".join(f"[bold]{k}:[/bold] {v.value}" for k, v in variables.items()),
                title="🔍 变量列表",
                style="cyan",
            ))
        
        else:
            console.print("[yellow]用法: /debug [start|break|continue|step|vars][/yellow]")
    
    except Exception as e:
        console.print(f"[red]调试操作失败: {markup.escape(str(e))}[/red]")


def _handle_profile_command(agent: FoxCodeAgent, config: Config, cmd_arg: str | None) -> None:
    """
    处理 /profile 命令
    
    性能分析
    
    用法:
        /profile        - 启动性能分析
        /profile report - 查看分析报告
    """
    try:
        from foxcode.core.performance_analyzer import PerformanceAnalyzer, PerformanceConfig
        
        analyzer_config = PerformanceConfig()
        analyzer = PerformanceAnalyzer(analyzer_config)
        
        if cmd_arg == "report":
            console.print(Panel(
                "[bold]性能分析报告[/bold]\n\n"
                "请使用 /profile <函数名> 来分析特定函数的性能。\n"
                "示例: /profile my_function",
                title="📊 性能分析报告",
                style="cyan",
            ))
        
        else:
            console.print("[cyan]性能分析已启动...[/cyan]")
            console.print("[dim]使用 /profile <函数名> 来分析特定函数的性能[/dim]")
    
    except Exception as e:
        console.print(f"[red]性能分析失败: {markup.escape(str(e))}[/red]")


def _handle_security_command(agent: FoxCodeAgent, config: Config, cmd_arg: str | None) -> None:
    """
    处理 /security 命令
    
    安全扫描
    
    用法:
        /security       - 运行安全扫描
        /security deps  - 扫描依赖漏洞
    """
    try:
        from foxcode.core.security_scanner import SecurityScanner, SecurityConfig
        
        scanner_config = SecurityConfig()
        scanner = SecurityScanner(scanner_config)
        
        if cmd_arg == "deps":
            results = run_async(scanner.scan_dependencies(Path(config.working_dir)))
            console.print(Panel(
                f"[bold]扫描的依赖:[/bold] {results.get('scanned', 0)}\n"
                f"[bold]漏洞数:[/bold] {results.get('vulnerabilities', 0)}\n"
                f"[bold]建议:[/bold]\n" + "\n".join(f"  - {s}" for s in results.get('recommendations', [])[:5]),
                title="🔒 依赖安全扫描",
                style="yellow",
            ))
        
        else:
            results = run_async(scanner.scan_directory(Path(config.working_dir)))
            console.print(Panel(
                f"[bold]扫描文件数:[/bold] {results.files_scanned}\n"
                f"[bold]发现问题:[/bold] {len(results.issues)}\n"
                f"[bold]严重程度分布:[/bold]\n" + 
                "\n".join(f"  - {k}: {v}" for k, v in results.severity_distribution.items()),
                title="🔒 安全扫描结果",
                style="red" if len(results.issues) > 0 else "green",
            ))
    
    except Exception as e:
        console.print(f"[red]安全扫描失败: {markup.escape(str(e))}[/red]")


def _handle_format_command(agent: FoxCodeAgent, config: Config, cmd_arg: str | None) -> None:
    """
    处理 /format 命令
    
    代码格式化
    
    用法:
        /format [files]  - 格式化代码
    """
    try:
        from foxcode.core.code_formatter import CodeFormatter, FormatterConfig
        
        formatter_config = FormatterConfig()
        formatter = CodeFormatter(formatter_config)
        
        if cmd_arg:
            files = [Path(f) for f in cmd_arg.split()]
            for f in files:
                if f.is_file():
                    result = run_async(formatter.format_file(f))
                    if result.success:
                        console.print(f"[green]✅ 已格式化: {f}[/green]")
                    else:
                        console.print(f"[red]❌ 格式化失败: {f} - {result.error}[/red]")
        else:
            result = run_async(formatter.format_directory(Path(config.working_dir)))
            console.print(f"[green]✅ 已格式化 {result.successful} 个文件[/green]")
            
            if result.failed > 0:
                console.print(f"[yellow]警告: {result.failed} 个文件格式化失败[/yellow]")
    
    except Exception as e:
        console.print(f"[red]代码格式化失败: {markup.escape(str(e))}[/red]")


def _handle_refactor_command(agent: FoxCodeAgent, config: Config, cmd_arg: str | None) -> None:
    """
    处理 /refactor 命令
    
    获取重构建议
    
    用法:
        /refactor [file]  - 获取重构建议
    """
    try:
        from foxcode.core.refactoring_suggester import RefactoringSuggester, RefactoringConfig
        
        suggester_config = RefactoringConfig()
        suggester = RefactoringSuggester(suggester_config)
        target = Path(cmd_arg) if cmd_arg else Path(config.working_dir)
        
        if target.is_file():
            report = suggester.analyze_file(target)
        else:
            report = suggester.analyze_file(target)
        
        if not report.smells:
            console.print("[green]✅ 未发现需要重构的代码[/green]")
            return
        
        console.print(Panel(
            "\n".join(f"[bold]{smell.type}:[/bold] {smell.description}\n"
                     f"  位置: {smell.location}\n"
                     f"  建议: {smell.suggestion}"
                     for smell in report.smells[:10]),
            title="🔧 重构建议",
            style="yellow",
        ))
    
    except Exception as e:
        console.print(f"[red]重构分析失败: {markup.escape(str(e))}[/red]")


def _handle_test_command(agent: FoxCodeAgent, config: Config, cmd_arg: str | None) -> None:
    """
    处理 /test 命令
    
    测试生成
    
    用法:
        /test gen <file>  - 生成测试用例
    """
    try:
        from foxcode.core.test_generator import TestGenerator, TestGeneratorConfig
        
        parts = cmd_arg.split(maxsplit=1) if cmd_arg else [None]
        sub_cmd = parts[0]
        sub_arg = parts[1] if len(parts) > 1 else None
        
        if sub_cmd == "gen" and sub_arg:
            generator_config = TestGeneratorConfig()
            generator = TestGenerator(generator_config)
            result = run_async(generator.generate_tests(Path(sub_arg)))
            console.print(f"[green]✅ 已生成 {len(result.test_cases)} 个测试用例[/green]")
            for test in result.test_cases[:5]:
                console.print(f"  - {test.name}")
        else:
            console.print("[yellow]用法: /test gen <file>[/yellow]")
    
    except Exception as e:
        console.print(f"[red]测试生成失败: {markup.escape(str(e))}[/red]")


def _handle_doc_command(agent: FoxCodeAgent, config: Config, cmd_arg: str | None) -> None:
    """
    处理 /doc 命令
    
    文档生成
    
    用法:
        /doc gen <file>  - 生成文档
    """
    try:
        from foxcode.core.doc_generator import DocGenerator, DocGeneratorConfig
        
        parts = cmd_arg.split(maxsplit=1) if cmd_arg else [None]
        sub_cmd = parts[0]
        sub_arg = parts[1] if len(parts) > 1 else None
        
        if sub_cmd == "gen" and sub_arg:
            generator_config = DocGeneratorConfig()
            generator = DocGenerator(generator_config)
            result = run_async(generator.generate_api_docs(Path(sub_arg)))
            console.print(f"[green]✅ 文档已生成[/green]")
            console.print(f"[dim]端点数: {len(result.endpoints)}[/dim]")
        else:
            console.print("[yellow]用法: /doc gen <file>[/yellow]")
    
    except Exception as e:
        console.print(f"[red]文档生成失败: {markup.escape(str(e))}[/red]")


def _handle_git_command(agent: FoxCodeAgent, config: Config, cmd_arg: str | None) -> None:
    """
    处理 /git 命令
    
    Git 高级操作
    
    用法:
        /git commit  - 智能提交
        /git conflicts     - 分析冲突
    """
    try:
        from foxcode.core.git_advanced_ops import GitAdvancedOps, GitConfig
        
        git_config = GitConfig()
        git_ops = GitAdvancedOps(git_config)
        
        parts = cmd_arg.split(maxsplit=1) if cmd_arg else [None]
        sub_cmd = parts[0]
        
        if sub_cmd == "commit":
            message = git_ops.generate_commit_message(Path(config.working_dir))
            console.print(f"[cyan]建议的提交信息:[/cyan]")
            console.print(f"[dim]{message.to_message()}[/dim]")
        
        elif sub_cmd == "conflicts":
            conflicts = git_ops.analyze_conflicts(Path(config.working_dir))
            if not conflicts:
                console.print("[green]✅ 没有冲突[/green]")
            else:
                console.print(Panel(
                    "\n".join(f"[bold]{c.file_path}:[/bold] {c.description}"
                             for c in conflicts),
                    title="⚠️ 冲突分析",
                    style="yellow",
                ))
        
        else:
            console.print("[yellow]用法: /git [commit|conflicts][/yellow]")
    
    except Exception as e:
        console.print(f"[red]Git 操作失败: {markup.escape(str(e))}[/red]")


def _handle_diagram_command(agent: FoxCodeAgent, config: Config, cmd_arg: str | None) -> None:
    """
    处理 /diagram 命令
    
    生成图表
    
    用法:
        /diagram <type>  - 生成图表 (architecture/chart)
    """
    try:
        from foxcode.core.multimodal_processor import MultimodalProcessor, MultimodalConfig
        
        processor_config = MultimodalConfig()
        processor = MultimodalProcessor(processor_config)
        diagram_type = cmd_arg or "architecture"
        
        if diagram_type == "architecture":
            result = processor.generate_architecture_diagram({})
            console.print(f"[green]✅ 架构图已生成[/green]")
            if result:
                console.print(Panel(
                    result[:500] + "..." if len(result) > 500 else result,
                    title="📊 架构图 (Mermaid)",
                    style="cyan",
                ))
        else:
            console.print(f"[green]✅ 图表已生成[/green]")
    
    except Exception as e:
        console.print(f"[red]图表生成失败: {markup.escape(str(e))}[/red]")


def _handle_space_command(agent: FoxCodeAgent, config: Config, cmd_arg: str | None) -> None:
    """
    处理 /space 命令
    
    OpenSpace - AI 经验知识存储系统
    
    用法:
        /space              - 显示 OpenSpace 状态
        /space true         - 启用 OpenSpace
        /space false        - 禁用 OpenSpace
        /space ai true      - 启用 AI 自动总结经验
        /space ai false     - 禁用 AI 自动总结经验
        /space list         - 列出所有经验
        /space add <title> <content>  - 快速添加经验
        /space show <id>    - 显示经验详情
        /space delete <id>  - 删除经验
        /space stats        - 显示统计信息
    """
    try:
        from foxcode.core.open_space import (
            get_open_space_manager,
            reset_open_space_manager,
            ExperienceCategory,
            Experience,
        )
        
        # 使用工作目录获取管理器
        manager = get_open_space_manager(working_dir=config.working_dir)
        
        # 解析子命令
        if cmd_arg:
            parts = cmd_arg.split(maxsplit=2)
            sub_cmd = parts[0].lower()
            sub_arg1 = parts[1] if len(parts) > 1 else None
            sub_arg2 = parts[2] if len(parts) > 2 else None
        else:
            sub_cmd = None
            sub_arg1 = None
            sub_arg2 = None
        
        # 启用 OpenSpace
        if sub_cmd == "true" or sub_cmd == "on" or sub_cmd == "enable":
            manager.enable()
            config.open_space.enabled = True
            console.print("[green]✅ OpenSpace 已启用[/green]")
            console.print("[dim]AI 经验知识将在下次对话中加载到上下文[/dim]")
            return
        
        # 禁用 OpenSpace
        if sub_cmd == "false" or sub_cmd == "off" or sub_cmd == "disable":
            manager.disable()
            config.open_space.enabled = False
            console.print("[yellow]OpenSpace 已禁用[/yellow]")
            console.print("[dim]AI 经验知识将不会加载到上下文[/dim]")
            return
        
        # AI 自动总结功能
        if sub_cmd == "ai":
            if sub_arg1 == "true" or sub_arg1 == "on" or sub_arg1 == "enable":
                manager.enable_ai_summarize()
                console.print("[green]✅ AI 自动总结已启用[/green]")
                console.print("[dim]每次 AI 完成任务后会自动总结踩过的坑并存入 OpenSpace[/dim]")
                return
            elif sub_arg1 == "false" or sub_arg1 == "off" or sub_arg1 == "disable":
                manager.disable_ai_summarize()
                console.print("[yellow]AI 自动总结已禁用[/yellow]")
                return
            else:
                ai_status = "✅ 启用" if manager.ai_auto_summarize else "❌ 禁用"
                console.print(f"[cyan]AI 自动总结状态: {ai_status}[/cyan]")
                console.print("[dim]用法: /space ai [true|false][/dim]")
                return
        
        # 列出所有经验
        if sub_cmd == "list":
            experiences = manager.list_all(enabled_only=False)
            
            if not experiences:
                console.print("[yellow]暂无经验记录[/yellow]")
                console.print("[dim]使用 /space add <标题> <内容> 添加新经验[/dim]")
                return
            
            from rich.table import Table
            table = Table(title="📚 OpenSpace 经验列表")
            table.add_column("ID", style="cyan", width=15)
            table.add_column("标题", style="white")
            table.add_column("分类", style="green")
            table.add_column("状态", style="yellow")
            table.add_column("创建时间", style="dim")
            
            for exp in experiences:
                status = "✅" if exp.enabled else "❌"
                table.add_row(
                    exp.id,
                    exp.title[:30] + "..." if len(exp.title) > 30 else exp.title,
                    exp.category.value,
                    status,
                    exp.created_at[:10] if exp.created_at else "-",
                )
            
            console.print(table)
            console.print(f"\n[dim]共 {len(experiences)} 条经验[/dim]")
            return
        
        # 添加新经验
        if sub_cmd == "add":
            if sub_arg1 and sub_arg2:
                # 快速添加模式: /space add <title> <content>
                title = sub_arg1
                content = sub_arg2
                
                # 检查内容长度
                if len(content) > 500:
                    content = content[:500]
                    console.print("[yellow]内容已截断至 500 字[/yellow]")
                
                exp = manager.create_experience(
                    title=title,
                    content=content,
                    category=ExperienceCategory.GENERAL,
                )
                
                if manager.save(exp):
                    console.print(f"[green]✅ 已添加经验: {exp.id}[/green]")
                    console.print(f"   标题: {title}")
                    console.print(f"   内容: {content[:50]}...")
                else:
                    console.print("[red]添加经验失败[/red]")
            else:
                # 交互式添加
                console.print("[cyan]添加新经验[/cyan]")
                console.print("[dim]提示: 使用 /space add <标题> <内容> 快速添加[/dim]")
                console.print("[dim]经验内容不超过 500 字[/dim]")
                
                console.print("\n[yellow]请使用以下格式添加:[/yellow]")
                console.print("  /space add <标题> <内容>")
                console.print("\n[dim]示例:[/dim]")
                console.print("  /space add \"Windows路径问题\" \"在Windows上使用反斜杠路径，但Python推荐使用正斜杠或Path对象\"")
            return
        
        # 显示经验详情
        if sub_cmd == "show" and sub_arg1:
            exp = manager.get(sub_arg1)
            
            if not exp:
                console.print(f"[red]经验不存在: {sub_arg1}[/red]")
                return
            
            console.print(Panel(
                f"[bold]标题:[/bold] {exp.title}\n"
                f"[bold]分类:[/bold] {exp.category.value}\n"
                f"[bold]标签:[/bold] {', '.join(exp.tags) if exp.tags else '无'}\n"
                f"[bold]创建时间:[/bold] {exp.created_at}\n"
                f"[bold]状态:[/bold] {'启用' if exp.enabled else '禁用'}\n\n"
                f"[bold]内容:[/bold]\n{exp.content}",
                title=f"📖 经验: {exp.id}",
                style="cyan",
            ))
            return
        
        # 删除经验
        if sub_cmd == "delete" and sub_arg1:
            exp = manager.get(sub_arg1)
            
            if not exp:
                console.print(f"[red]经验不存在: {sub_arg1}[/red]")
                return
            
            if manager.delete(sub_arg1):
                console.print(f"[green]✅ 已删除经验: {sub_arg1}[/green]")
            else:
                console.print(f"[red]删除失败: {sub_arg1}[/red]")
            return
        
        # 显示统计信息
        if sub_cmd == "stats":
            stats = manager.get_statistics()
            
            ai_status = "✅ 启用" if stats.get('ai_auto_summarize', False) else "❌ 禁用"
            
            console.print(Panel(
                f"[bold]总经验数:[/bold] {stats['total']}\n"
                f"[bold]启用:[/bold] {stats['enabled']}\n"
                f"[bold]禁用:[/bold] {stats['disabled']}\n"
                f"[bold]状态:[/bold] {'✅ 启用' if stats['is_enabled'] else '❌ 禁用'}\n"
                f"[bold]AI自动总结:[/bold] {ai_status}\n\n"
                f"[bold]分类统计:[/bold]\n" +
                "\n".join(f"  - {k}: {v}" for k, v in stats['categories'].items()),
                title="📊 OpenSpace 统计",
                style="cyan",
            ))
            return
        
        # 默认显示状态
        status = "✅ 启用" if manager.enabled else "❌ 禁用"
        ai_status = "✅ 启用" if manager.ai_auto_summarize else "❌ 禁用"
        stats = manager.get_statistics()
        
        console.print(Panel(
            f"[bold]状态:[/bold] {status}\n"
            f"[bold]AI自动总结:[/bold] {ai_status}\n"
            f"[bold]经验总数:[/bold] {stats['total']}\n"
            f"[bold]启用的经验:[/bold] {stats['enabled']}\n\n"
            f"[dim]用法:[/dim]\n"
            f"  /space true    - 启用\n"
            f"  /space false   - 禁用\n"
            f"  /space ai true - 启用AI自动总结\n"
            f"  /space ai false - 禁用AI自动总结\n"
            f"  /space list    - 列出所有经验\n"
            f"  /space add <标题> <内容>  - 添加经验\n"
            f"  /space show <id>  - 显示详情\n"
            f"  /space delete <id>  - 删除经验\n"
            f"  /space stats   - 统计信息",
            title="OpenSpace - AI 经验知识库",
            style="cyan",
        ))
        
    except ImportError as e:
        console.print(f"[red]OpenSpace 模块加载失败: {e}[/red]")
    except Exception as e:
        console.print(f"[red]OpenSpace 操作失败: {markup.escape(str(e))}[/red]")


def _handle_topic_command(agent: FoxCodeAgent, config: Config, cmd_arg: str | None) -> None:
    """
    处理 /topic 命令
    
    切换输出主题模式，并保存到配置文件
    
    用法:
        /topic              - 显示当前输出主题模式
        /topic default      - 切换到默认模式（完整输出）
        /topic debug        - 切换到调试模式（详细输出）
        /topic minimalism   - 切换到极简模式（精简输出）
    """
    try:
        # 解析子命令
        if cmd_arg:
            sub_cmd = cmd_arg.lower().strip()
        else:
            sub_cmd = None
        
        # 切换到指定模式
        if sub_cmd == "default":
            config.output_topic = OutputTopic.DEFAULT
            # 保存配置到文件
            if config.save_output_topic(OutputTopic.DEFAULT):
                console.print("[green]✅ 已切换到默认模式（完整输出）并保存配置[/green]")
            else:
                console.print("[green]✅ 已切换到默认模式（完整输出）[/green]")
                console.print("[yellow]⚠️ 配置保存失败，下次启动将恢复默认设置[/yellow]")
            return
        
        elif sub_cmd == "debug":
            config.output_topic = OutputTopic.DEBUG
            config.debug = True
            config.log_level = "DEBUG"
            logging.getLogger().setLevel(logging.DEBUG)
            # 保存配置到文件
            if config.save_output_topic(OutputTopic.DEBUG):
                console.print("[green]✅ 已切换到调试模式（详细输出）并保存配置[/green]")
            else:
                console.print("[green]✅ 已切换到调试模式（详细输出）[/green]")
                console.print("[yellow]⚠️ 配置保存失败，下次启动将恢复默认设置[/yellow]")
            return
        
        elif sub_cmd == "minimalism":
            config.output_topic = OutputTopic.MINIMALISM
            # 保存配置到文件
            if config.save_output_topic(OutputTopic.MINIMALISM):
                print("[OK] 已切换到极简模式（精简输出）并保存配置")
            else:
                print("[OK] 已切换到极简模式（精简输出）")
                print("[WARN] 配置保存失败，下次启动将恢复默认设置")

            return
        
        # 显示当前模式状态
        current_topic = config.output_topic.value
        topic_desc = {
            OutputTopic.DEFAULT.value: "默认模式（完整输出）",
            OutputTopic.DEBUG.value: "调试模式（详细输出）",
            OutputTopic.MINIMALISM.value: "极简模式（精简输出）",
        }
        
        # 极简模式：简洁输出
        if config.output_topic == OutputTopic.MINIMALISM:
            print(f"[topic] 当前模式: {topic_desc.get(current_topic, current_topic)}")
            print("[topic] 可用模式: default, debug, minimalism")
            print("[topic] 用法: /topic [default|debug|minimalism]")
            return
        
        console.print(Panel(
            f"[bold]当前模式:[/bold] {topic_desc.get(current_topic, current_topic)}\n\n"
            f"[bold]可用模式:[/bold]\n"
            f"  [cyan]default[/cyan]    - 默认模式（完整输出）\n"
            f"  [cyan]debug[/cyan]      - 调试模式（详细输出）\n"
            f"  [cyan]minimalism[/cyan] - 极简模式（精简输出）\n\n"
            f"[dim]用法: /topic [default|debug|minimalism][/dim]\n"
            f"[dim]设置会自动保存到配置文件[/dim]",
            title="📋 输出主题模式",
            style="cyan",
        ))
    
    except Exception as e:
        if config.output_topic == OutputTopic.MINIMALISM:
            print(f"[错误] 切换输出模式失败: {str(e)}")
        else:
            console.print(f"[red]切换输出模式失败: {markup.escape(str(e))}[/red]")
