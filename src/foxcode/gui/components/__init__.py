# UI 组件模块初始化

"""
UI 组件模块 - 提供所有界面组件

本模块包含 FoxCode Desktop 的所有 UI 组件，
遵循统一的设计规范和使用 SVG 图标系统（禁止 emoji）。

主要组件：
- icons.py: SVG 图标库（统一管理所有图标）
- activity_bar.py: 左侧活动栏（文件、搜索、设置）
- sidebar.py: 侧边栏（项目信息、AI 对话）
- editor_area.py: 编辑器区域容器（Monaco iframe）
- file_explorer.py: 右侧文件浏览器
- terminal_panel.py: 底部终端面板
- title_bar.py: 顶部标题栏
- status_bar.py: 底部状态栏

设计原则：
- 使用 SVG 图标，禁止 emoji
- 响应式布局
- 暗色主题优先
- 无障碍访问支持

使用方式：
    from foxcode.gui.components import Icons, ActivityBar, EditorArea
    
    # 创建图标
    svg_icon = Icons.file_icon(24)
    
    # 创建组件
    activity_bar = ActivityBar()
    activity_bar.render()
"""

from .icons import Icons, icon_button

__all__ = ['Icons', 'icon_button']
