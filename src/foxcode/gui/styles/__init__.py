# 样式模块初始化

"""
样式模块 - 提供 GUI 的主题和样式配置

本模块负责管理 FoxCode Desktop 的视觉样式，
包括主题、颜色、字体、动画等。

主要内容：
- theme.py: 主题配置（暗色主题、颜色变量）
- custom.css: 自定义 CSS 样式

设计规范：
- 暗色主题为主（匹配 VS Code 风格）
- 色彩方案：
  * 背景：#1e1e1e, #252526
  * 文本：#cccccc, #ffffff
  * 强调色：#007acc, #4ec9b0
  * 边框：#3c3c3c
- 字体：Consolas/Menlo (代码), 系统默认字体 (UI)

使用方式：
    from foxcode.gui.styles import ThemeManager
    
    # 应用主题
    theme = ThemeManager()
    theme.apply_dark_theme()
"""

__all__ = []
