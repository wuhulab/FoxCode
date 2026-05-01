"""
TUI (Terminal User Interface) 界面模块

提供现代化的终端交互界面，包括：
- 对话界面：与 AI 进行交互式对话
- 任务管理界面：显示和管理任务列表
- 配置界面：可视化配置管理
- 日志查看器：实时查看系统日志

使用方法：
    from foxcode.tui import run_app
    run_app()
"""
from foxcode.tui.app import FoxCodeApp, run_app

__all__ = ["FoxCodeApp", "run_app"]
