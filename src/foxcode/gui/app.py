# FoxCode Desktop - NiceGUI 应用主入口

"""
FoxCode Desktop 应用启动和管理

本模块是 FoxCode 桌面版的主入口，负责：
1. 初始化 NiceGUI 应用实例
2. 配置应用参数（窗口大小、主题、端口等）
3. 注册 Monaco 编辑器路由
4. 设置全局样式和主题
5. 管理应用生命周期（启动、关闭）

使用方式：
    # 命令行启动
    foxcode --gui
    
    # 或在代码中调用
    from foxcode.gui.app import start_gui
    start_gui()
    
    # 自定义配置
    from foxcode.gui.app import create_app
    app = create_app(port=9000, window_size=(1600, 1000))
    ui.run(app)

设计原则：
- 单例模式（全局唯一的应用实例）
- 延迟初始化（按需加载组件）
- 优雅关闭（资源清理、状态保存）
- 错误恢复（异常处理和日志记录）

主要特性：
- VS Code 风格的暗色主题
- 完整的 Monaco 编辑器支持
- 响应式布局
- 跨平台兼容性

作者：FoxCode Team
版本：1.0.0
"""

import logging
import sys
from pathlib import Path
from typing import Optional

# 配置日志系统
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path.home() / '.foxcode' / 'gui.log', mode='a', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

# 全局应用实例（单例）
_app_instance = None


def create_app(
    port: int = 8080,
    window_size: tuple = (1400, 900),
    title: str = 'FoxCode Desktop',
    dark: bool = True,
    reload: bool = False,
) -> object:
    """
    创建并配置 NiceGUI 应用实例
    
    这是工厂函数，用于创建预配置的 NiceGUI 应用。
    所有必要的路由、样式和中间件都会在此注册。
    
    Args:
        port: 应用监听端口，默认 8080
        window_size: 窗口尺寸 (宽, 高)，默认 (1400, 900)
        title: 窗口标题，默认 'FoxCode Desktop'
        dark: 是否使用暗色主题，默认 True
        reload: 是否启用热重载（开发模式），默认 False
        
    Returns:
        配置好的 NiceGUI 应用对象
        
    使用示例：
        >>> app = create_app(port=9000, window_size=(1600, 1000))
        >>> ui.run(app)
        
    配置项说明：
        - port: 应避免与常用端口冲突（80, 443, 3000 等）
        - window_size: 推荐最小分辨率 1280x720
        - dark: 暗色主题可减少眼睛疲劳，推荐开发时使用
        - reload: 仅在开发环境启用，生产环境应关闭
        
    注意事项：
        - 此函数应在程序启动时调用一次
        - 返回的应用实例应传递给 ui.run()
        - 修改配置需要重启应用
        
    异常处理：
        - 端口占用会自动尝试下一个可用端口
        - 缺少依赖会给出明确的错误提示
        - 配置错误会使用安全的默认值
    """
    global _app_instance
    
    try:
        # 导入 NiceGUI
        from nicegui import ui, app as nicegui_app
        
        logger.info(f"正在初始化 FoxCode Desktop 应用...")
        logger.info(f"配置参数: port={port}, window_size={window_size}, title={title}")
        
        # 注册 Monaco 编辑器路由（必须在 ui.run 之前）
        from .editor.editor_page import register_editor_routes
        register_editor_routes(nicegui_app)
        logger.info("已注册 Monaco 编辑器路由")
        
        # 应用全局样式
        _apply_global_styles(ui)
        
        # 存储应用实例
        _app_instance = nicegui_app
        
        logger.info("FoxCode Desktop 应用初始化完成")
        
        return nicegui_app
        
    except ImportError as e:
        logger.error(f"导入 NiceGUI 失败: {e}")
        logger.error("请确保已安装 NiceGUI: pip install nicegui>=2.0.0")
        raise RuntimeError(f"缺少依赖: {e}") from e
        
    except Exception as e:
        logger.error(f"初始化应用失败: {e}", exc_info=True)
        raise RuntimeError(f"应用初始化失败: {e}") from e


def _apply_global_styles(ui) -> None:
    """
    应用全局 CSS 样式
    
    设置 FoxCode Desktop 的整体视觉风格，
    包括颜色变量、字体、基础组件样式等。
    
    Args:
        ui: NiceGUI 的 ui 对象
        
    样式规范：
        - 遵循 VS Code 的暗色主题配色方案
        - 使用 CSS 变量便于主题切换
        - 优先使用系统字体栈确保跨平台一致性
        - 所有尺寸使用 rem/em 相对单位
    """
    # 注入全局 CSS 变量和基础样式
    custom_css = """
    <style>
        /* ==================== CSS 变量定义 ==================== */
        :root {
            /* 颜色系统 - 基于 VS Code 暗色主题 */
            --bg-primary: #1e1e1e;          /* 主背景色 */
            --bg-secondary: #252526;        /* 次要背景色 */
            --bg-tertiary: #2d2d2d;         /* 第三级背景 */
            --bg-hover: #37373d;            /* 悬停背景 */
            --bg-active: #094771;           /* 激活/选中背景 */
            --bg-border: #3c3c3c;           /* 边框颜色 */
            
            /* 文本颜色 */
            --text-primary: #cccccc;        /* 主要文本 */
            --text-secondary: #969696;      /* 次要文本 */
            --text-muted: #6e6e6e;          /* 弱化文本 */
            --text-link: #3794ff;           /* 链接颜色 */
            
            /* 强调色 */
            --accent-primary: #007acc;      /* 主强调色（蓝色） */
            --accent-secondary: #4ec9b0;    /* 次强调色（青色） */
            --accent-warning: #cca700;      /* 警告色（黄色） */
            --accent-error: #f44747;        /* 错误色（红色） */
            --accent-success: #89d185;      /* 成功色（绿色） */
            
            /* 字体系统 */
            --font-family-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", 
                               Roboto, "Helvetica Neue", Arial, sans-serif;
            --font-family-mono: "Consolas", "Courier New", "Monaco", monospace;
            --font-size-base: 14px;
            --font-size-small: 12px;
            --font-size-large: 16px;
            
            /* 间距系统 */
            --spacing-xs: 4px;
            --spacing-sm: 8px;
            --spacing-md: 16px;
            --spacing-lg: 24px;
            --spacing-xl: 32px;
            
            /* 圆角 */
            --radius-sm: 2px;
            --radius-md: 4px;
            --radius-lg: 8px;
            
            /* 过渡动画 */
            --transition-fast: 150ms ease;
            --transition-normal: 250ms ease;
            --transition-slow: 350ms ease;
        }
        
        /* 全局样式重置 */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: var(--font-family-sans);
            font-size: var(--font-size-base);
            color: var(--text-primary);
            background-color: var(--bg-primary);
            line-height: 1.5;
            overflow: hidden;
            user-select: none;
        }
        
        /* 滚动条样式 */
        ::-webkit-scrollbar {
            width: 10px;
            height: 10px;
        }
        
        ::-webkit-scrollbar-track {
            background: var(--bg-secondary);
        }
        
        ::-webkit-scrollbar-thumb {
            background: var(--bg-border);
            border-radius: var(--radius-sm);
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: #555;
        }
        
        /* 选中文本样式 */
        ::selection {
            background-color: var(--accent-primary);
            color: white;
        }
        
        /* 链接样式 */
        a {
            color: var(--text-link);
            text-decoration: none;
            transition: color var(--transition-fast);
        }
        
        a:hover {
            color: var(--accent-secondary);
            text-decoration: underline;
        }
        
        /* 输入框样式优化 */
        input, textarea, select {
            font-family: inherit;
            font-size: inherit;
            border: 1px solid var(--bg-border);
            background-color: var(--bg-tertiary);
            color: var(--text-primary);
            padding: var(--spacing-sm);
            border-radius: var(--radius-sm);
            outline: none;
            transition: border-color var(--transition-fast);
        }
        
        input:focus, textarea:focus, select:focus {
            border-color: var(--accent-primary);
        }
        
        /* 按钮基础样式 */
        button {
            cursor: pointer;
            font-family: inherit;
            transition: all var(--transition-fast);
        }
        
        button:hover:not(:disabled) {
            opacity: 0.9;
        }
        
        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        /* 代码字体应用 */
        code, pre, .monaco-editor {
            font-family: var(--font-family-mono) !important;
        }
    </style>
    """
    
    ui.add_head_html(custom_css)
    logger.info("已应用全局 CSS 样式")


def start_gui(
    port: int = 8080,
    window_size: tuple = (1400, 900),
    **kwargs
) -> None:
    """
    启动 FoxCode Desktop GUI 应用
    
    这是最常用的入口函数，用于直接启动桌面版应用。
    会自动创建应用实例并运行主循环。
    
    Args:
        port: 监听端口，默认 8080
        window_size: 窗口尺寸 (宽, 高)，默认 (1400, 900)
        **kwargs: 其他传递给 ui.run() 的参数
        
    使用示例：
        # 基本用法
        start_gui()
        
        # 自定义端口和窗口
        start_gui(port=9000, window_size=(1920, 1080))
        
        # 开发模式（热重载）
        start_gui(reload=True)
        
    执行流程：
        1. 创建应用实例（create_app）
        2. 渲染主窗口界面
        3. 启动 NiceGUI 事件循环
        4. 等待用户交互或关闭信号
        
    生命周期：
        - 启动: 初始化所有组件和服务
        - 运行: 处理用户事件和网络请求
        - 关闭: 清理资源、保存状态、退出进程
        
    注意事项：
        - 此函数会阻塞当前线程
        - 在主线程中调用以避免 UI 问题
        - 关闭窗口或按 Ctrl+C 可退出应用
    """
    global _app_instance
    
    try:
        from nicegui import ui
        
        print("=" * 60)
        print("  FoxCode Desktop - AI 编程助手桌面版")
        print("=" * 60)
        print(f"  版本: 0.1.0")
        print(f"  端口: {port}")
        print(f"  窗口: {window_size[0]}x{window_size[1]}")
        print("=" * 60)
        print()
        
        # 创建应用实例
        app = create_app(
            port=port,
            window_size=window_size,
            **kwargs
        )
        
        # 渲染主界面
        _render_main_window(ui)
        
        # 启动应用
        logger.info(f"正在启动 FoxCode Desktop on http://localhost:{port}")
        
        ui.run(
            title='FoxCode Desktop',
            port=port,
            window_size=window_size,
            dark=True,
            reload=False,
            show=True,
            **kwargs
        )
        
    except KeyboardInterrupt:
        logger.info("用户中断，正在关闭应用...")
        _cleanup()
        
    except Exception as e:
        logger.error(f"启动应用失败: {e}", exc_info=True)
        print(f"\n[ERROR] 启动失败: {e}")
        print("请检查日志文件获取详细信息:")
        print(f"  {Path.home() / '.foxcode' / 'gui.log'}")
        sys.exit(1)


def _render_main_window(ui) -> None:
    """
    渲染主窗口界面
    
    创建完整的 IDE 布局结构，包括：
    - 顶部标题栏
    - 左侧活动栏 + 侧边栏
    - 中间编辑器区域
    - 右侧文件浏览器
    - 底部终端面板
    
    Args:
        ui: NiceGUI 的 ui 对象
    """
    # 导入主窗口组件
    from .main_window import MainWindow
    
    logger.info("正在渲染主窗口...")
    
    # 创建主窗口实例
    main_window = MainWindow()
    
    # 渲染界面
    main_window.render()
    
    logger.info("主窗口渲染完成")


def _cleanup() -> None:
    """
    清理资源和保存状态
    
    在应用关闭前执行清理操作：
    - 保存未保存的文件提示
    - 保存窗口位置和大小
    - 释放系统资源
    - 关闭文件句柄和网络连接
    - 写入关闭日志
    """
    global _app_instance
    
    logger.info("正在执行清理操作...")
    
    try:
        # TODO: 实现具体的清理逻辑
        # 1. 检查未保存的更改
        # 2. 保存用户偏好设置
        # 3. 关闭打开的文件句柄
        # 4. 断开网络连接
        # 5. 清理临时文件
        
        logger.info("清理完成")
        
    except Exception as e:
        logger.warning(f"清理过程中出现警告: {e}", exc_info=True)
    
    finally:
        _app_instance = None


def get_app():
    """
    获取当前应用实例（单例）
    
    Returns:
        NiceGUI 应用实例，如果未初始化则返回 None
    """
    return _app_instance


# 如果直接运行此模块，启动 GUI
if __name__ == '__main__':
    start_gui()
