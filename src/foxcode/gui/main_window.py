# FoxCode Desktop 主窗口布局

"""
MainWindow - 主窗口布局管理器

本模块负责创建和管理整个 IDE 界面的布局结构，
包括所有主要组件的组织和协调。

布局结构：
+------------------------------------------------------------------+
| TitleBar (顶部标题栏)                                             |
+--------+---------------------------+-------------------------------+
|        |                           |                               |
| Activity|   Editor Area          |  File Explorer                 |
| Bar     |   (Monaco iframe)       |  (文件树)                      |
| (50px) |                           |                               |
|        +---------------------------+                               |
|        | Sidebar (可选)           |                               |
|        | (AI 对话/项目信息)        |                               |
+--------+---------------------------+-------------------------------+
| Terminal Panel (底部终端面板)                                     |
+------------------------------------------------------------------+

设计原则：
- 响应式布局：支持窗口大小调整
- 组件化：每个区域独立封装
- 可配置：面板大小和可见性可调整
- 性能优先：懒加载非核心组件

使用方式：
    from foxcode.gui.main_window import MainWindow
    
    main = MainWindow()
    main.render()

作者：FoxCode Team
版本：1.0.0
"""

import logging
from pathlib import Path
from typing import Optional

from nicegui import ui

# 配置日志
logger = logging.getLogger(__name__)


class MainWindow:
    """
    主窗口布局管理类
    
    负责创建完整的 IDE 布局，包括：
    - 顶部标题栏
    - 左侧活动栏
    - 侧边栏
    - 中间编辑器区域
    - 右侧文件浏览器
    - 底部终端面板
    
    使用示例：
        >>> main = MainWindow()
        >>> main.render()
        
    自定义配置：
        >>> main = MainWindow(
        ...     show_file_explorer=True,
        ...     show_terminal=True,
        ...     initial_width=1400,
        ...     initial_height=900
        ... )
        
    注意事项：
        - 应在应用启动时调用一次 render()
        - 布局会自动适应窗口大小变化
        - 各个面板可以独立显示/隐藏
    """
    
    def __init__(
        self,
        show_title_bar: bool = True,
        show_activity_bar: bool = True,
        show_sidebar: bool = True,
        show_file_explorer: bool = True,
        show_terminal: bool = True,
        initial_width: int = 1400,
        initial_height: int = 900
    ):
        """
        初始化主窗口
        
        Args:
            show_title_bar: 是否显示顶部标题栏
            show_activity_bar: 是否显示左侧活动栏
            show_sidebar: 是否显示侧边栏
            show_file_explorer: 是否显示右侧文件浏览器
            show_terminal: 是否显示底部终端面板
            initial_width: 初始宽度（像素）
            initial_height: 初始高度（像素）
        """
        # 显示配置
        self.show_title_bar = show_title_bar
        self.show_activity_bar = show_activity_bar
        self.show_sidebar = show_sidebar
        self.show_file_explorer = show_file_explorer
        self.show_terminal = show_terminal
        
        # 尺寸配置
        self.initial_width = initial_width
        self.initial_height = initial_height
        
        # 组件引用（延迟初始化）
        self._title_bar = None
        self._activity_bar = None
        self._sidebar = None
        self._editor_area = None
        self._file_explorer = None
        self._terminal_panel = None
        
        logger.info(f"MainWindow 初始化完成 (尺寸: {initial_width}x{initial_height})")
    
    def render(self) -> None:
        """
        渲染主窗口界面
        
        创建完整的 IDE 布局结构，
        包括所有可见的 UI 组件。
        
        这是主要的公共方法，应在应用启动时调用。
        
        使用示例：
            >>> main = MainWindow()
            >>> main.render()
            
        渲染顺序：
            1. 创建主容器
            2. 添加标题栏（如果启用）
            3. 创建主内容区（三栏布局）
            4. 添加终端面板（如果启用）
            5. 初始化各个子组件
            
        布局层次：
            ui.column (主容器)
            ├── title_bar (标题栏)
            └── ui.row (内容区)
                ├── activity_bar (活动栏)
                ├── sidebar (侧边栏)
                ├── editor_area (编辑器)
                └── file_explorer (文件浏览器)
            └── terminal_panel (终端)
        """
        logger.info("正在渲染主窗口...")
        
        with ui.column().classes('w-full h-screen overflow-hidden bg-[#1e1e1e]'):
            
            # 1. 顶部标题栏
            if self.show_title_bar:
                self._render_title_bar()
            
            # 2. 主内容区（三栏布局）
            with ui.row().classes('flex-1 overflow-hidden'):
                
                # 左侧：活动栏 + 侧边栏
                if self.show_activity_bar or self.show_sidebar:
                    with ui.column().classes('h-full'):
                        # 活动栏
                        if self.show_activity_bar:
                            self._render_activity_bar()
                        
                        # 侧边栏
                        if self.show_sidebar:
                            self._render_sidebar()
                
                # 中间：编辑器区域（主体）
                self._render_editor_area()
                
                # 右侧：文件浏览器
                if self.show_file_explorer:
                    self._render_file_explorer()
            
            # 3. 底部：终端面板
            if self.show_terminal:
                self._render_terminal_panel()
        
        logger.info("主窗口渲染完成")
    
    def _render_title_bar(self) -> None:
        """渲染顶部标题栏"""
        from .components.icons import Icons
        
        with ui.row().classes(
            'w-full h-10 '
            'bg-[#323233] '
            'items-center px-2 '
            'border-b border-[#3c3c3c]'
        ):
            # 左侧：菜单按钮（可选）
            ui.icon(Icons.file_icon(16)).classes('text-gray-400 mx-2')
            
            # 中间：搜索框
            with ui.input(
                placeholder='搜索 shunxcode',
            ).props(
                'dense outlined'
            ).classes(
                'w-64 '
                'bg-transparent '
                'text-gray-300 '
                'text-sm'
            ).props('color=white'):
                pass  # 占位符文本
            
            # 弹性空间
            ui.spacer()
            
            # 右侧：工具按钮组
            with ui.row().classes('items-center gap-1'):
                # 主题切换
                ui.icon(Icons.gear_icon(18)).classes(
                    'text-gray-400 hover:text-white cursor-pointer'
                )
                
                # 通知
                ui.label('').classes(
                    'w-4 h-4 rounded-full bg-blue-500 text-xs text-white '
                    'flex items-center justify-center'
                ).text('3')
                
                # 布局切换
                ui.icon(Icons.folder_icon(18)).classes(
                    'text-gray-400 hover:text-white cursor-pointer'
                )
    
    def _render_activity_bar(self) -> None:
        """渲染左侧活动栏"""
        from .components.icons import Icons, icon_button
        
        with ui.column().classes(
            'w-14 '
            'bg-[#333333] '
            'items-center py-2 '
            'gap-1 border-r border-[#3c3c3c]'
        ):
            # Logo 区域
            ui.html(Icons.logo_icon(40)).classes('mb-4 cursor-pointer')
            
            # 分隔线
            ui.separator().classes('w-8 bg-[#3c3c3c] mb-2')
            
            # 文件浏览器按钮
            icon_button(
                Icons.file_icon(24),
                tooltip='资源管理器 (Ctrl+E)'
            ).classes('text-gray-300 hover:text-white hover:bg-[#4e4e4e]')
            
            # 搜索按钮
            icon_button(
                Icons.search_icon(24),
                tooltip='搜索 (Ctrl+F)'
            ).classes('text-gray-300 hover:text-white hover:bg-[#4e4e4e]')
            
            # Git 按钮（占位）
            icon_button(
                Icons.branch_icon(20),
                tooltip='源代码管理'
            ).classes('text-gray-300 hover:text-white hover:bg-[#4e4e4e]')
            
            # 调试按钮（占位）
            icon_button(
                Icons.play_icon(22),
                tooltip='运行和调试'
            ).classes('text-gray-300 hover:text-white hover:bg-[#4e4e4e]')
            
            # 扩展按钮（占位）
            icon_button(
                Icons.blocks_icon(22),
                tooltip='扩展'
            ).classes('text-gray-300 hover:text-white hover:bg-[#4e4e4e]')
            
            # 弹性空间
            ui.spacer()
            
            # 设置按钮
            icon_button(
                Icons.gear_icon(24),
                tooltip='设置'
            ).classes('text-gray-300 hover:text-white hover:bg-[#4e4e4e] mb-2')
            
            # 用户头像
            ui.avatar(icon=Icons.user_avatar(28), size='sm').classes('mb-2')
    
    def _render_sidebar(self) -> None:
        """渲染侧边栏（AI 对话区域）"""
        from .components.icons import Icons, icon_button
        
        with ui.column().classes(
            'w-72 '
            'bg-[#252526] '
            'p-4 border-r border-[#3c3c3c] overflow-y-auto'
        ):
            # Logo 和标题
            ui.html(Icons.logo_icon(56)).classes('mx-auto mb-4')
            ui.label('构建任何东西').classes(
                'text-xl font-bold text-gray-200 text-center mb-2'
            )
            
            # 项目路径
            ui.label('S:/shunxcode').classes(
                'text-sm text-gray-400 mb-1'
            )
            
            # Git 信息
            with ui.row().classes('items-center gap-1 mb-1'):
                ui.html(Icons.branch_icon(14)).classes('text-gray-500')
                ui.label('主分支 (master)').classes('text-xs text-gray-400')
            
            # 最后修改时间
            ui.label('最后修改 14秒钟前').classes('text-xs text-gray-500 mb-6')
            
            # AI 对话输入框
            with ui.element('div').classes('w-full mb-4'):
                ui.textarea(
                    placeholder="随便问点什么... '帮我写一个迁移脚本'"
                ).props(
                    'autogrow dense outlined rows=2'
                ).classes(
                    'w-full '
                    'bg-[#3c3c3c] '
                    'text-gray-200'
                )
            
            # 操作按钮行
            with ui.row().classes('items-center justify-between w-full mb-4'):
                # 发送按钮
                ui.button(
                    icon=Icons.send_icon(18),
                    on_click=lambda: print("发送消息")
                ).props('flat round').classes('text-blue-400')
                
                # Build 下拉
                ui.select(
                    options=['Build', 'Run', 'Test'],
                    value='Build'
                ).props('dense outlined').classes('w-24 text-sm')
                
                # 模型选择下拉
                ui.select(
                    options=['MiniMax M2.5 Free', 'GPT-4', 'Claude'],
                    value='MiniMax M2.5 Free'
                ).props('dense outlined').classes('w-40 text-sm')
    
    def _render_editor_area(self) -> None:
        """渲染编辑器区域容器"""
        from .components.icons import Icons
        
        with ui.column().classes('flex-1 h-full overflow-hidden'):
            # 标签栏
            with ui.row().classes(
                'h-9 '
                'bg-[#252526] '
                'items-center border-b border-[#3c3c3c] px-1'
            ):
                # 示例标签页
                for i, tab in enumerate(['审阅', 'test_skill_generator.py', 'count_lines.py']):
                    with ui.item(
                        on_click=lambda idx=i: print(f"切换到标签 {idx}")
                    ).classes(
                        'px-3 py-1 h-full flex items-center gap-2 '
                        'cursor-pointer hover:bg-[#2a2d2e] '
                        f'{"bg-[#1e1e1e]" if i == 1 else ""}'
                    ):
                        ui.label(tab).classes(
                            'text-sm text-gray-300'
                        )
                        
                        # 关闭按钮（除第一个标签外）
                        if i > 0:
                            ui.html(Icons.close_icon(12)).classes(
                                'text-gray-500 hover:text-white cursor-pointer'
                            )
                
                # 新建标签按钮
                ui.button(
                    icon=Icons.plus_icon(14)
                ).props('flat dense round').classes('text-gray-400 ml-1')
                
                # 弹性空间
                ui.spacer()
                
                # 右侧信息
                ui.label('0 更改').classes('text-xs text-gray-500 mr-3')
                ui.label('所有文件').classes('text-xs text-gray-500 mr-2')
            
            # Monaco 编辑器 iframe 容器
            with ui.element('div').classes('flex-1 relative overflow-hidden'):
                # 这里将嵌入 Monaco 编辑器的 iframe
                # 在实际使用时会通过 EditorArea 组件创建
                
                # 占位符：显示欢迎信息
                with ui.column().classes(
                    'absolute inset-0 '
                    'flex items-center justify-center '
                    'text-gray-600'
                ):
                    ui.label('FoxCode Desktop').classes('text-3xl mb-4')
                    ui.label('打开一个文件开始编辑').classes('text-lg mb-2')
                    ui.label('快捷键: Ctrl+O 打开文件').classes('text-sm')
                    
                    ui.label('\n\n或者从左侧选择功能：').classes('mt-8 text-sm')
                    ui.label('- 文件浏览器: 浏览项目文件').classes('text-sm mt-1')
                    ui.label('- AI 对话: 输入问题获取帮助').classes('text-sm mt-1')
    
    def _render_file_explorer(self) -> None:
        """渲染右侧文件浏览器"""
        from .components.icons import Icons, get_file_icon
        
        with ui.column().classes(
            'w-64 '
            'bg-[#252526] '
            'border-l border-[#3c3c3c] overflow-y-auto'
        ):
            # 头部
            with ui.row().classes(
                'h-9 items-center px-3 border-b border-[#3c3c3c] justify-between'
            ):
                ui.label('资源管理器').classes('text-xs font-semibold text-gray-300 uppercase')
                
                with ui.row().classes('gap-1'):
                    # 新建文件按钮
                    ui.icon(Icons.plus_icon(14)).classes(
                        'text-gray-400 hover:text-white cursor-pointer'
                    )
                    # 刷新按钮
                    ui.icon(Icons.refresh_icon(14)).classes(
                        'text-gray-400 hover:text-white cursor-pointer'
                    )
                    # 折叠全部按钮
                    ui.icon(Icons.collapse_icon(14)).classes(
                        'text-gray-400 hover:text-white cursor-pointer'
                    )
            
            # 文件树
            with ui.column().classes('py-2 px-1 text-sm'):
                # 项目根目录列表
                folders_files = [
                    ('.foxcode', True),
                    ('.github', True),
                    ('.mypycache', True),
                    ('.pytest_cache', True),
                    ('.ruff_cache', True),
                    ('.trae', True),
                    ('abouttest', True),
                    ('blog-system', True),
                    ('design.md', False),
                    ('src', True),  # 展开状态
                ]
                
                for name, is_folder in folders_files:
                    with ui.item(
                        on_click=lambda n=name: print(f"点击: {n}")
                    ).classes(
                        'flex items-center gap-2 px-2 py-0.5 rounded '
                        'hover:bg-[#2a2d2e] cursor-pointer'
                    ):
                        # 展开/折叠箭头或图标
                        if is_folder:
                            ui.html(Icons.chevron_right_icon(12)).classes('text-gray-500')
                            ui.html(get_file_icon(name, is_folder=True, size=16))
                        else:
                            ui.html(get_file_icon(name, is_folder=False, size=16))
                        
                        # 文件名
                        ui.label(name).classes(
                            'text-gray-300 text-xs truncate'
                        )
                
                # src 目录的展开内容（示例）
                with ui.column().classes('ml-4 pl-2 border-l border-[#3c3c3c]'):
                    sub_items = [
                        ('foxcode.toml', False),
                        ('foxcode.toml.example', False),
                        ('.gitignore', False),
                        ('count_lines.py', False),
                        ('LICENSE.txt', False),
                        ('pyproject.toml', False),
                        ('README_EN.md', False),
                        ('README.md', False),
                        ('security_scan.log', False),
                    ]
                    
                    for name, is_folder in sub_items:
                        with ui.item(
                            on_click=lambda n=f"src/{name}": print(f"打开: {n}")
                        ).classes(
                            'flex items-center gap-2 px-2 py-0.5 rounded '
                            'hover:bg-[#2a2d2e] cursor-pointer'
                        ):
                            ui.html(get_file_icon(name, is_folder=False, size=16))
                            
                            ui.label(name).classes(
                                'text-gray-300 text-xs truncate'
                            )
    
    def _render_terminal_panel(self) -> None:
        """渲染底部终端面板"""
        from .components.icons import Icons
        
        with ui.column().classes(
            'h-48 '
            'bg-[#1e1e1e] '
            'border-t border-[#3c3c3c]'
        ):
            # 终端标签栏
            with ui.row().classes(
                'h-8 items-center px-2 border-b border-[#3c3c3c] bg-[#252526]'
            ):
                # 终端标签
                with ui.item(
                    on_click=lambda: print("激活终端")
                ).classes(
                    'flex items-center gap-2 px-3 h-full '
                    'bg-[#1e1e1e] border-t-2 border-[#007acc] cursor-pointer'
                ):
                    ui.label('终端 1').classes('text-xs text-gray-200')
                    ui.html(Icons.close_icon(10)).classes(
                        'text-gray-500 hover:text-white cursor-pointer'
                    )
                
                # 新建终端按钮
                ui.button(
                    icon=Icons.plus_icon(12)
                ).props('flat dense round').classes('text-gray-400')
                
                # 弹性空间
                ui.spacer()
                
                # 用户头像
                ui.avatar(icon=Icons.user_avatar(20), size='xs')
            
            # 终端内容区
            with ui.element('div').classes(
                'flex-1 p-2 font-mono text-sm overflow-auto bg-black'
            ):
                # PowerShell 提示符
                ui.label('PS S:\\shunxcode>').classes('text-gray-300')
                
                # 光标
                ui.element('span').classes(
                    'w-2 h-4 bg-gray-300 inline-block animate-pulse'
                )


# 为 Icons 类添加缺失的方法（临时解决方案）
def _add_missing_icons():
    """动态添加缺失的图标方法"""
    @staticmethod
    def _play_icon(size):
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M8 5v14l11-7z" fill="currentColor"/>
        </svg>'''
    
    @staticmethod
    def _blocks_icon(size):
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" xmlns="http://www.w3.org/2000/svg" stroke-width="2">
            <rect x="3" y="3" width="7" height="7"/>
            <rect x="14" y="3" width="7" height="7"/>
            <rect x="14" y="14" width="7" height="7"/>
            <rect x="3" y="14" width="7" height="7"/>
        </svg>'''
    
    @staticmethod
    def _refresh_icon(size):
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" xmlns="http://www.w3.org/2000/svg" stroke-width="2">
            <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4M22 12.5a10 10 0 0 1-18.8 4"/>
        </svg>'''
    
    @staticmethod
    def _collapse_icon(size):
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" xmlns="http://www.w3.org/2000/svg" stroke-width="2">
            <path d="M4 14h16M4 10h16"/>
        </svg>'''

# 执行添加
try:
    from .components import Icons as IconsClass
    IconsClass.play_icon = _play_icon
    IconsClass.blocks_icon = _blocks_icon
    IconsClass.refresh_icon = _refresh_icon
    IconsClass.collapse_icon = _collapse_icon
except Exception as e:
    logger.debug(f"添加额外图标方法时出错（可能已存在）: {e}")
