# SVG 图标库 - 统一管理所有 UI 图标

"""
SVG 图标组件库 - FoxCode Desktop 图标管理系统

本模块提供统一的 SVG 图标管理，禁止使用任何 emoji 表情包。
所有图标均为矢量格式（SVG），支持尺寸和颜色自定义。

设计原则：
- 使用 Material Design Icons 风格
- 统一的视觉语言
- 支持多种尺寸（16px, 20px, 24px, 32px）
- 支持颜色自定义
- 轻量级（内联 SVG）

主要功能：
1. 提供常用图标的静态方法
2. 支持参数化尺寸和颜色
3. 创建带图标的按钮组件
4. 集中管理，易于维护

图标分类：
- 文件/文件夹图标
- 操作图标（搜索、设置、关闭等）
- 状态图标（保存、修改等）
- 应用特定图标（Logo、品牌等）

使用方式：
    from foxcode.gui.components.icons import Icons, icon_button
    
    # 获取 SVG 字符串
    file_svg = Icons.file_icon(24)
    
    # 创建图标按钮
    btn = icon_button(
        Icons.search_icon(20),
        on_click=search_handler,
        tooltip='搜索'
    )
    
    # 在 NiceGUI 中使用
    ui.html(Icons.folder_icon(32))

作者：FoxCode Team
版本：1.0.0
"""


class Icons:
    """
    SVG 图标库 - 统一管理所有图标
    
    所有方法返回 SVG 字符串，可直接嵌入 HTML 或用于 NiceGUI 组件
    
    使用示例：
        >>> svg = Icons.file_icon(24)
        >>> print(svg[:50])
        '<svg width="24" height="24" viewBox="0 0 24 24" ...'
    """
    
    # ==================== 文件和文件夹图标 ====================
    
    @staticmethod
    def file_icon(size: int = 24) -> str:
        """
        文件图标 - 表示普通文件
        
        Args:
            size: 图标尺寸（像素），默认 24
            
        Returns:
            SVG 图标字符串
            
        使用场景：
            - 文件浏览器中的文件项
            - 标签页图标
            - 文件操作按钮
        """
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <path d="M14 2H6C4.9 2 4 2.9 4 4V20C4 21.1 4.9 22 6 22H18C19.1 22 20 21.1 20 20V8L14 2Z" 
                  stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M14 2V8H20" stroke="currentColor" stroke-width="2" 
                  stroke-linecap="round" stroke-linejoin="round"/>
        </svg>'''
    
    @staticmethod
    def folder_icon(size: int = 24) -> str:
        """
        文件夹图标 - 表示目录
        
        Args:
            size: 图标尺寸（像素），默认 24
            
        Returns:
            SVG 图标字符串
            
        使用场景：
            - 文件浏览器中的文件夹
            - 项目导航
            - 目录选择器
        """
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <path d="M22 19C22 20.1 21.1 21 20 21H4C2.9 21 2 20.1 2 19V5C2 3.9 2.9 3 4 3H9L11 5H20C21.1 5 22 5.9 22 7V19Z" 
                  stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>'''
    
    @staticmethod
    def folder_open_icon(size: int = 24) -> str:
        """
        打开的文件夹图标 - 表示展开的目录
        
        Args:
            size: 图标尺寸（像素），默认 24
            
        Returns:
            SVG 图标字符串
        """
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <path d="M5 19C5 20.1 5.9 21 7 21H19C20.1 21 21 20.1 21 19V10C21 8.9 20.1 8 19 8H13L11 6H5C3.9 6 3 6.9 3 8V19C3 20.1 3.9 21 5 21Z" 
                  stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                  fill="currentColor" fill-opacity="0.2"/>
        </svg>'''
    
    # ==================== 编程语言特定图标 ====================
    
    @staticmethod
    def python_icon(size: int = 24) -> str:
        """
        Python 文件图标 - 表示 .py 文件
        
        Args:
            size: 图标尺寸（像素）
            
        Returns:
            SVG 图标字符串（包含 Python logo 元素）
        """
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <rect x="3" y="3" width="18" height="18" rx="2" 
                  stroke="#3776AB" stroke-width="2" fill="#FFD43B" fill-opacity="0.2"/>
            <text x="12" y="16" text-anchor="middle" font-size="10" 
                  font-weight="bold" fill="#3776AB">Py</text>
        </svg>'''
    
    @staticmethod
    def javascript_icon(size: int = 24) -> str:
        """
        JavaScript 文件图标 - 表示 .js 文件
        """
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <rect x="3" y="3" width="18" height="18" rx="2" 
                  stroke="#F7DF1E" stroke-width="2" fill="#000000" fill-opacity="0.1"/>
            <text x="12" y="16" text-anchor="middle" font-size="9" 
                  font-weight="bold" fill="#F7DF1E">JS</text>
        </svg>'''
    
    @staticmethod
    def typescript_icon(size: int = 24) -> str:
        """
        TypeScript 文件图标 - 表示 .ts 文件
        """
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <rect x="3" y="3" width="18" height="18" rx="2" 
                  stroke="#3178C6" stroke-width="2" fill="#3178C6" fill-opacity="0.1"/>
            <text x="12" y="16" text-anchor="middle" font-size="8" 
                  font-weight="bold" fill="#3178C6">TS</text>
        </svg>'''
    
    @staticmethod
    def html_icon(size: int = 24) -> str:
        """HTML 文件图标"""
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <rect x="3" y="3" width="18" height="18" rx="2" 
                  stroke="#E34F26" stroke-width="2" fill="#E34F26" fill-opacity="0.1"/>
            <text x="12" y="16" text-anchor="middle" font-size="8" 
                  font-weight="bold" fill="#E34F26">&lt;/&gt;</text>
        </svg>'''
    
    @staticmethod
    def css_icon(size: int = 24) -> str:
        """CSS 文件图标"""
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <rect x="3" y="3" width="18" height="18" rx="2" 
                  stroke="#1572B6" stroke-width="2" fill="#1572B6" fill-opacity="0.1"/>
            <text x="12" y="16" text-anchor="middle" font-size="9" 
                  font-weight="bold" fill="#1572B6">#</text>
        </svg>'''
    
    @staticmethod
    def json_icon(size: int = 24) -> str:
        """JSON 文件图标"""
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <rect x="3" y="3" width="18" height="18" rx="2" 
                  stroke="#CB3837" stroke-width="2" fill="#CB3837" fill-opacity="0.1"/>
            <text x="12" y="15" text-anchor="middle" font-size="8" 
                  font-weight="bold" fill="#CB3837">{{}}</text>
        </svg>'''
    
    @staticmethod
    def markdown_icon(size: int = 24) -> str:
        """Markdown 文件图标"""
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <rect x="3" y="3" width="18" height="18" rx="2" 
                  stroke="#083FA1" stroke-width="2" fill="#083FA1" fill-opacity="0.1"/>
            <text x="12" y="16" text-anchor="middle" font-size="10" 
                  font-weight="bold" fill="#083FA1">MD</text>
        </svg>'''
    
    # ==================== 配置和文档图标 ====================
    
    @staticmethod
    def config_icon(size: int = 24) -> str:
        """配置文件图标（.toml, .yaml, .ini 等）"""
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <rect x="3" y="3" width="18" height="18" rx="2" 
                  stroke="#6D8086" stroke-width="2" fill="#6D8086" fill-opacity="0.1"/>
            <path d="M8 12H16M8 8H16M8 16H12" stroke="#6D8086" 
                  stroke-width="2" stroke-linecap="round"/>
        </svg>'''
    
    @staticmethod
    def git_icon(size: int = 24) -> str:
        """Git 相关文件图标（.gitignore 等）"""
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <circle cx="12" cy="12" r="9" stroke="#F05032" stroke-width="2" fill="#F05032" fill-opacity="0.1"/>
            <path d="M12 7V17M8 11L12 7L16 11" stroke="#F05032" 
                  stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>'''
    
    @staticmethod
    def license_icon(size: int = 24) -> str:
        """许可证文件图标（LICENSE 等）"""
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <rect x="3" y="3" width="18" height="18" rx="2" 
                  stroke="#A0522D" stroke-width="2" fill="#A0522D" fill-opacity="0.1"/>
            <text x="12" y="16" text-anchor="middle" font-size="8" 
                  font-weight="bold" fill="#A0522D">L</text>
        </svg>'''
    
    @staticmethod
    def readme_icon(size: int = 24) -> str:
        """README 文件图标"""
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <rect x="3" y="3" width="18" height="18" rx="2" 
                  stroke="#0066CC" stroke-width="2" fill="#0066CC" fill-opacity="0.15"/>
            <circle cx="12" cy="12" r="3" stroke="#0066CC" stroke-width="1.5" fill="none"/>
            <text x="12" y="15" text-anchor="middle" font-size="6" 
                  font-weight="bold" fill="#0066CC">i</text>
        </svg>'''
    
    @staticmethod
    def python_pkg_icon(size: int = 24) -> str:
        """Python 包配置图标（pyproject.toml）"""
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <rect x="3" y="3" width="18" height="18" rx="2" 
                  stroke="#3776AB" stroke-width="2" fill="#FFD43B" fill-opacity="0.25"/>
            <text x="12" y="15" text-anchor="middle" font-size="7" 
                  font-weight="bold" fill="#3776AB">pkg</text>
        </svg>'''
    
    @staticmethod
    def log_icon(size: int = 24) -> str:
        """日志文件图标"""
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <rect x="3" y="3" width="18" height="18" rx="2" 
                  stroke="#666666" stroke-width="2" fill="#666666" fill-opacity="0.1"/>
            <path d="M8 8H16M8 12H14M8 16H12" stroke="#666666" 
                  stroke-width="1.5" stroke-linecap="round"/>
        </svg>'''
    
    @staticmethod
    def text_icon(size: int = 24) -> str:
        """纯文本文件图标"""
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <path d="M14 2H6C4.9 2 4 2.9 4 4V20C4 21.1 4.9 22 6 22H18C19.1 22 20 21.1 20 20V8L14 2Z" 
                  stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M14 2V8H20" stroke="currentColor" stroke-width="2" 
                  stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M8 13H16M8 17H12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>'''
    
    @staticmethod
    def default_file_icon(size: int = 24) -> str:
        """默认文件图标（未知类型）"""
        return Icons.file_icon(size)
    
    # ==================== 操作图标 ====================
    
    @staticmethod
    def search_icon(size: int = 24) -> str:
        """
        搜索图标 - 用于搜索功能
        
        使用场景：
            - 全局搜索框
            - 文件内容搜索
            - 命令面板
        """
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <circle cx="11" cy="11" r="8" stroke="currentColor" stroke-width="2" fill="none"/>
            <path d="M21 21L16.65 16.65" stroke="currentColor" stroke-width="2" 
                  stroke-linecap="round" stroke-linejoin="round"/>
        </svg>'''
    
    @staticmethod
    def gear_icon(size: int = 24) -> str:
        """
        设置齿轮图标 - 用于设置菜单
        
        使用场景：
            - 设置入口
            - 配置选项
            - 偏好设置
        """
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2" fill="none"/>
            <path d="M19.4 15C19.2667 15.3016 19.1267 15.5917 19 15.87L20.36 17.77C20.4622 17.908 20.4503 18.1006 20.33 18.23L18.23 20.33C18.0974 20.4526 17.9017 20.4644 17.76 20.35L15.86 19C15.5866 19.1267 15.3022 19.2333 15.01 19.32L14.56 21.55C14.5178 21.7133 14.3706 21.8262 14.2 21.83H11.27C11.1022 21.8289 10.9565 21.7189 10.91 21.56L10.42 19.33C10.1261 19.2433 9.83996 19.1367 9.56499 19.01L7.67 20.36C7.53198 20.4622 7.33939 20.4503 7.21 20.33L5.11 18.23C4.98739 18.0974 4.97561 17.9017 5.09 17.76L6.44 15.87C6.31333 15.5966 6.20666 15.3122 6.12 15.02L3.89 14.57C3.72667 14.5278 3.61379 14.3806 3.61 14.21V11.28C3.61114 11.1122 3.72107 10.9665 3.88 10.92L6.11 10.43C6.19666 10.1361 6.30333 9.84996 6.43 9.575L5.08 7.68C4.97561 7.54198 4.98739 7.34939 5.11 7.22L7.21 5.12C7.34261 4.99739 7.53828 4.98561 7.68 5.1L9.57 6.45C9.84333 6.32333 10.1277 6.21666 10.42 6.13L10.87 3.9C10.9122 3.73667 11.0594 3.62379 11.23 3.62H14.16C14.3278 3.62114 14.4735 3.73107 14.52 3.89L15.01 6.12C15.3039 6.20666 15.59 6.31333 15.865 6.44L17.76 5.09C17.898 4.98761 18.0906 4.99939 18.22 5.12L20.32 7.22C20.4426 7.35261 20.4544 7.54828 20.34 7.69L19 9.58C19.1267 9.85333 19.2333 10.1377 19.32 10.43L21.55 10.88C21.7133 10.9222 21.8262 11.0694 21.83 11.24V14.17C21.8289 14.3378 21.7189 14.4835 21.56 14.53L19.33 15.02" 
                  stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>'''
    
    @staticmethod
    def close_icon(size: int = 16) -> str:
        """
        关闭按钮图标 - 用于关闭标签、对话框等
        
        Args:
            size: 图标尺寸，默认较小（16px）适合按钮使用
        """
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" 
                  stroke-linecap="round" stroke-linejoin="round"/>
        </svg>'''
    
    @staticmethod
    def plus_icon(size: int = 16) -> str:
        """
        加号/新建图标 - 用于新建文件、添加标签等
        """
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <path d="M12 5V19M5 12H19" stroke="currentColor" stroke-width="2" 
                  stroke-linecap="round" stroke-linejoin="round"/>
        </svg>'''
    
    @staticmethod
    def send_icon(size: int = 20) -> str:
        """
        发送图标 - 用于消息发送按钮
        """
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <path d="M22 2L11 13M22 2L15 22L11 13L2 9L22 2Z" 
                  stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>'''
    
    @staticmethod
    def save_icon(size: int = 24) -> str:
        """保存图标"""
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <path d="M19 21H5C3.89543 21 3 20.1046 3 19V5C3 3.89543 3.89543 3 5 3H16L21 8V19C21 20.1046 20.1046 21 19 21Z" 
                  stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M17 21V13H7V21" stroke="currentColor" stroke-width="2" 
                  stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M7 3V8H15" stroke="currentColor" stroke-width="2" 
                  stroke-linecap="round" stroke-linejoin="round"/>
        </svg>'''
    
    @staticmethod
    def user_avatar(size: int = 32) -> str:
        """
        用户头像图标 - 用于显示用户信息
        
        Args:
            size: 尺寸较大（默认 32px），适合头像显示
        """
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <circle cx="12" cy="8" r="4" stroke="currentColor" stroke-width="2" fill="none"/>
            <path d="M4 20C4 16.6863 6.68629 14 10 14H14C17.3137 14 20 16.6863 20 20" 
                  stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>'''
    
    @staticmethod
    def logo_icon(size: int = 40) -> str:
        """
        FoxCode Logo 图标 - 品牌标识
        
        Args:
            size: 较大尺寸（默认 40px），适合作为主 Logo
        """
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 48 48" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <!-- 外框：深色背景 -->
            <rect x="4" y="4" width="40" height="40" rx="6" 
                  fill="#1e1e1e" stroke="#007acc" stroke-width="2"/>
            
            <!-- 内部：字母 F 的艺术化设计 -->
            <path d="M14 14H28M14 14V34M14 24H24" 
                  stroke="#4ec9b0" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
            
            <!-- 装饰点 -->
            <circle cx="32" cy="14" r="2" fill="#007acc"/>
            <circle cx="32" cy="34" r="2" fill="#007acc"/>
        </svg>'''
    
    @staticmethod
    def chevron_right_icon(size: int = 16) -> str:
        """
        右箭头图标 - 用于可展开的树形结构
        """
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <path d="M9 18L15 12L9 6" stroke="currentColor" stroke-width="2" 
                  stroke-linecap="round" stroke-linejoin="round"/>
        </svg>'''
    
    @staticmethod
    def chevron_down_icon(size: int = 16) -> str:
        """
        下箭头图标 - 用于已展开的树形结构
        """
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <path d="M6 9L12 15L18 9" stroke="currentColor" stroke-width="2" 
                  stroke-linecap="round" stroke-linejoin="round"/>
        </svg>'''
    
    @staticmethod
    def branch_icon(size: int = 16) -> str:
        """Git 分支图标"""
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" 
                xmlns="http://www.w3.org/2000/svg">
            <circle cx="6" cy="6" r="2" stroke="currentColor" stroke-width="2" fill="none"/>
            <circle cx="6" cy="18" r="2" stroke="currentColor" stroke-width="2" fill="none"/>
            <circle cx="18" cy="12" r="2" stroke="currentColor" stroke-width="2" fill="none"/>
            <path d="M6 8V16M8 18H16M16 14V12" stroke="currentColor" stroke-width="2"/>
        </svg>'''


def icon_button(icon_svg: str, on_click=None, tooltip: str = None):
    """
    创建带 SVG 图标的按钮组件
    
    这是一个工厂函数，用于快速创建带有图标的 NiceGUI 按钮。
    按钮采用扁平化设计，适合工具栏和活动栏使用。
    
    Args:
        icon_svg: SVG 图标字符串（从 Icons 类获取）
        on_click: 点击事件回调函数
        tooltip: 鼠标悬停时显示的提示文字
        
    Returns:
        NiceGUI icon_button 元素
        
    使用示例：
        >>> from foxcode.gui.components.icons import Icons, icon_button
        >>> 
        >>> # 创建搜索按钮
        >>> btn = icon_button(
        ...     Icons.search_icon(24),
        ...     on_click=lambda: print("搜索"),
        ...     tooltip='搜索 (Ctrl+F)'
        ... )
        
    设计规范：
        - 扁平化样式（flat）
        - 紧凑布局（dense）
        - 圆角按钮（round）
        - 默认无背景色
        - 悬停时显示提示
    
    注意事项：
        - 图标应使用 Icons 类的静态方法生成
        - 建议为所有图标按钮提供 tooltip
        - 回调函数应为异步或同步函数
    """
    from nicegui import ui
    
    with ui.icon_button(on_click=on_click).props('flat dense round').tooltip(tooltip or ''):
        ui.html(icon_svg)


def get_file_icon(filename: str, is_folder: bool = False, size: int = 16) -> str:
    """
    根据文件名或扩展名获取对应的 SVG 图标
    
    这是一个便捷函数，自动根据文件类型返回合适的图标。
    主要用于文件浏览器组件中显示不同类型的文件图标。
    
    Args:
        filename: 文件名或完整路径
        is_folder: 是否为文件夹
        size: 图标尺寸（像素），默认 16（适合树形列表）
        
    Returns:
        SVG 图标字符串
        
    使用示例：
        >>> get_file_icon("main.py")
        '<svg ...>'  # 返回 Python 图标
        
        >>> get_file_icon("src", is_folder=True)
        '<svg ...>'  # 返回文件夹图标
        
        >>> get_file_icon(".gitignore")
        '<svg ...>'  # 返回 Git 图标
        
    支持的文件类型：
        - 编程语言：Python (.py), JS (.ts/.js), HTML/CSS/JSON
        - 配置文件：TOML/YAML/INI/CFG
        - 文档文件：Markdown (.md), TXT (.txt), README
        - Git 文件：.gitignore, .gitattributes
        - 其他：LICENSE, 日志文件, Python 包配置
        
    特殊处理：
        - 特殊文件名（如 README.md, pyproject.toml）优先匹配
        - 未知扩展名使用默认文件图标
        - 文件夹统一使用文件夹图标
    """
    from pathlib import Path
    
    if is_folder:
        return Icons.folder_icon(size)
    
    # 特殊文件名映射（优先级最高）
    special_files = {
        '.gitignore': Icons.git_icon,
        '.gitattributes': Icons.git_icon,
        '.dockerignore': Icons.config_icon,
        'LICENSE': Icons.license_icon,
        'LICENSE.txt': Icons.license_icon,
        'LICENSE.md': Icons.license_icon,
        'README.md': Icons.readme_icon,
        'README_EN.md': Icons.readme_icon,
        'README': Icons.readme_icon,
        'README.txt': Icons.readme_icon,
        'README_EN.txt': Icons.readme_icon,
        'pyproject.toml': Icons.python_pkg_icon,
        'setup.py': Icons.python_icon,
        'setup.cfg': Icons.python_icon,
        'Makefile': Icons.config_icon,
        'Dockerfile': Icons.config_icon,
        'docker-compose.yml': Icons.config_icon,
        'docker-compose.yaml': Icons.config_icon,
        '.env': Icons.config_icon,
        '.env.example': Icons.config_icon,
        '.env.local': Icons.config_icon,
        'security_scan.log': Icons.log_icon,
        '.python-version': Icons.python_icon,
        'package.json': Icons.javascript_icon,
        'tsconfig.json': Icons.typescript_icon,
    }
    
    # 检查特殊文件名
    name = Path(filename).name
    if name in special_files:
        return special_files[name](size)
    
    # 根据扩展名判断
    ext = Path(filename).suffix.lower()
    
    ext_map = {
        # Python 相关
        '.py': Icons.python_icon,
        '.pyw': Icons.python_icon,
        '.pyx': Icons.python_icon,
        '.pyd': Icons.python_icon,
        
        # JavaScript/TypeScript
        '.js': Icons.javascript_icon,
        '.jsx': Icons.javascript_icon,
        '.mjs': Icons.javascript_icon,
        '.cjs': Icons.javascript_icon,
        '.ts': Icons.typescript_icon,
        '.tsx': Icons.typescript_icon,
        
        # Web 技术
        '.html': Icons.html_icon,
        '.htm': Icons.html_icon,
        '.css': Icons.css_icon,
        '.scss': Icons.css_icon,
        '.sass': Icons.css_icon,
        '.less': Icons.css_icon,
        '.vue': Icons.html_icon,
        '.svelte': Icons.html_icon,
        
        # 数据格式
        '.json': Icons.json_icon,
        '.jsonc': Icons.json_icon,
        '.xml': Icons.config_icon,
        '.yaml': Icons.config_icon,
        '.yml': Icons.config_icon,
        '.toml': Icons.config_icon,
        '.ini': Icons.config_icon,
        '.cfg': Icons.config_icon,
        '.conf': Icons.config_icon,
        
        # 文档
        '.md': Icons.markdown_icon,
        '.markdown': Icons.markdown_icon,
        '.rst': Icons.text_icon,
        '.txt': Icons.text_icon,
        '.log': Icons.log_icon,
        
        # Shell 脚本
        '.sh': Icons.config_icon,
        '.bash': Icons.config_icon,
        '.zsh': Icons.config_icon,
        '.fish': Icons.config_icon,
        '.ps1': Icons.config_icon,
        '.bat': Icons.config_icon,
        '.cmd': Icons.config_icon,
        
        # 其他编程语言
        '.java': Icons.text_icon,
        '.kt': Icons.text_icon,
        '.kts': Icons.text_icon,
        '.c': Icons.text_icon,
        '.h': Icons.text_icon,
        '.cpp': Icons.text_icon,
        '.hpp': Icons.text_icon,
        '.cc': Icons.text_icon,
        '.cxx': Icons.text_icon,
        '.go': Icons.text_icon,
        '.rs': Icons.text_icon,
        '.rb': Icons.text_icon,
        '.php': Icons.text_icon,
        '.swift': Icons.text_icon,
        '.scala': Icons.text_icon,
        '.r': Icons.text_icon,
        '.R': Icons.text_icon,
        '.lua': Icons.text_icon,
        '.pl': Icons.text_icon,
        '.pm': Icons.text_icon,
        '.ex': Icons.text_icon,
        '.exs': Icons.text_icon,
        '.erl': Icons.text_icon,
        '.hrl': Icons.text_icon,
        '.cs': Icons.text_icon,
        '.vb': Icons.text_icon,
        '.f90': Icons.text_icon,
        '.f95': Icons.text_icon,
        '.f03': Icons.text_icon,
        '.asm': Icons.text_icon,
        '.s': Icons.text_icon,
        '.sql': Icons.text_icon,
        '.graphql': Icons.text_icon,
        '.gql': Icons.text_icon,
        '.proto': Icons.text_icon,
        
        # 数据科学
        '.ipynb': Icons.python_icon,
        '.Rmd': Icons.markdown_icon,
        
        # Web 配置
        '.htaccess': Icons.config_icon,
        '.editorconfig': Icons.config_icon,
        '.eslintrc': Icons.config_icon,
        '.eslintrc.js': Icons.javascript_icon,
        '.eslintrc.json': Icons.json_icon,
        '.prettierrc': Icons.config_icon,
        '.prettierrc.js': Icons.javascript_icon,
        '.prettierrc.json': Icons.json_icon,
        '.babelrc': Icons.config_icon,
        '.babelrc.js': Icons.javascript_icon,
        '.babelrc.json': Icons.json_icon,
        'babel.config.js': Icons.javascript_icon,
        'babel.config.json': Icons.json_icon,
        'tsconfig.json': Icons.typescript_icon,
        'webpack.config.js': Icons.javascript_icon,
        'rollup.config.js': Icons.javascript_icon,
        'vite.config.ts': Icons.typescript_icon,
        'next.config.js': Icons.javascript_icon,
        'nuxt.config.ts': Icons.typescript_icon,
        '.pre-commit-config.yaml': Icons.config_icon,
        'tox.ini': Icons.config_icon,
        'pytest.ini': Icons.config_icon,
        'setup.cfg': Icons.python_icon,
        'my.ini': Icons.config_icon,
        '.npmrc': Icons.config_icon,
        '.yarnrc': Icons.config_icon,
        '.pnp.cjs': Icons.javascript_icon,
        '.pnp.js': Icons.javascript_icon,
        '.huskyrc': Icons.config_icon,
        '.huskyrc.js': Icons.javascript_icon,
        '.lintstagedrc': Icons.config_icon,
        '.lintstagedrc.js': Icons.javascript_icon,
        '.lintstagedrc.json': Icons.json_icon,
        'stylelint.config.js': Icons.javascript_icon,
        'commitlint.config.js': Icons.javascript_icon,
        'composer.json': Icons.text_icon,
        'Gemfile': Icons.text_icon,
        'Cargo.toml': Icons.config_icon,
        'pom.xml': Icons.config_icon,
        'build.gradle': Icons.text_icon,
        'CMakeLists.txt': Icons.text_icon,
        'Makefile': Icons.config_icon,
        'Dockerfile': Icons.config_icon,
        'docker-compose.yml': Icons.config_icon,
        'docker-compose.yaml': Icons.config_icon,
        'Vagrantfile': Icons.text_icon,
        'terraform.tfvars': Icons.config_icon,
        '.terraformrc': Icons.config_icon,
        '.tf': Icons.config_icon,
        '.hcl': Icons.config_icon,
        '.pp': Icons.text_icon,
        '.chefignore': Icons.config_icon,
        'Berksfile': Icons.text_icon,
        'Vagrantfile': Icons.text_icon,
        'Jenkinsfile': Icons.text_icon,
        '.gitlab-ci.yml': Icons.config_icon,
        '.circleci': Icons.config_icon,
        'azure-pipelines.yml': Icons.config_icon,
        '.travis.yml': Icons.config_icon,
        'appveyor.yml': Icons.config_icon,
        'bitbucket-pipelines.yml': Icons.config_icon,
        'jenkinsfile': Icons.text_icon,
        '.vercel': Icons.config_icon,
        '.now.json': Icons.json_icon,
        'netlify.toml': Icons.config_icon,
        '_config.yml': Icons.config_icon,
        '.stackbit.yml': Icons.config_icon,
        'wrangler.toml': Icons.config_icon,
        'firebase.json': Icons.json_icon,
        'firestore.rules': Icons.text_icon,
        'database.rules': Icons.text_icon,
        'storage.rules': Icons.text_icon,
        'index.yaml': Icons.config_icon,
        'index Buddle': Icons.config_icon,
        'svelte.config.js': Icons.javascript_icon,
        'astro.config.mjs': Icons.javascript_icon,
        'solid.config.js': Icons.javascript_icon,
        'quasar.conf.js': Icons.javascript_icon,
        'ionic.config.json': Icons.json_icon,
        '.vscode': Icons.folder_icon,
        '.idea': Icons.folder_icon,
    }
    
    # 查找对应的图标函数
    icon_func = ext_map.get(ext, Icons.default_file_icon)
    
    return icon_func(size)
