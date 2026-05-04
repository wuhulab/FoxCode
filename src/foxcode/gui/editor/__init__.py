# Monaco 编辑器模块初始化

"""
Monaco 编辑器模块 - 提供 VS Code 级别的代码编辑体验

本模块通过 iframe 嵌入独立的 Monaco Editor 页面，
避免与 NiceGUI 的 Vue.js 产生冲突，确保最佳性能和功能完整性。

主要组件：
- editor_page.py: FastAPI 路由，提供编辑器页面
- monaco_bridge.py: 通信桥接层，处理主应用与编辑器的双向通信
- editor_config.py: 编辑器配置管理
- static/: 静态资源（HTML、JS）

架构设计：
NiceGUI 主应用 <--postMessage--> iframe (Monaco Editor)

使用方式：
    from foxcode.gui.editor.monaco_bridge import MonacoBridge
    
    bridge = MonacoBridge()
    bridge.create_iframe(file_path="example.py")
    await bridge.open_file("another_file.py")
"""

from .editor_page import register_editor_routes
from .monaco_bridge import MonacoBridge

__all__ = ['register_editor_routes', 'MonacoBridge']
