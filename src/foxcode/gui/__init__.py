# FoxCode GUI 模块初始化

"""
FoxCode Desktop - 基于 NiceGUI 的桌面版 GUI 界面

这个模块提供完整的桌面 IDE 体验，包括：
- Monaco 编辑器（通过 iframe 嵌入）
- 文件浏览器
- AI 对话界面
- 终端面板
- SVG 图标系统

使用方式：
    # 启动桌面版
    foxcode --gui
    
    # 或在代码中调用
    from foxcode.gui.app import start_gui
    start_gui()

主要特性：
- VS Code 风格的现代化界面
- 完整的代码编辑功能（Monaco Editor）
- AI 辅助编程（复用核心 Agent）
- 多标签支持
- 暗色主题
- 跨平台支持

技术栈：
- NiceGUI (Vue.js + FastAPI)
- Monaco Editor (iframe 隔离)
- xterm.js (终端)
- Tailwind CSS (样式)

作者：FoxCode Team
版本：0.1.0
"""

__version__ = "0.1.0"
__author__ = "FoxCode Team"
