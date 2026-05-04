# 服务层模块初始化

"""
服务层模块 - 提供业务逻辑服务

本模块包含 GUI 的各种服务，负责处理业务逻辑和数据操作。

主要服务：
- file_service.py: 文件操作服务（读取、写入、搜索、监听）
- ai_service.py: AI 对话服务（复用核心 Agent 逻辑）
- terminal_service.py: 终端服务（Shell 进程管理）

设计原则：
- 异步优先
- 错误处理完善
- 日志记录详细
- 与现有 CLI 逻辑兼容

使用方式：
    from foxcode.gui.services import FileService, AIService
    
    # 创建服务实例
    file_service = FileService()
    content = await file_service.read_file("example.py")
"""

__all__ = []
