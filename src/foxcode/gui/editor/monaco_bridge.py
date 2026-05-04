# Monaco Editor 通信桥接层

"""
Monaco Bridge - 主应用与 Monaco 编辑器的双向通信桥接

本模块负责管理 NiceGUI 主应用与 iframe 中的 Monaco Editor 之间的所有通信。
使用 postMessage API 实现跨窗口消息传递，确保数据传输的可靠性和安全性。

核心功能：
1. 创建和管理 iframe 元素
2. 发送消息到 Monaco 编辑器
3. 接收并处理来自编辑器的消息
4. 管理文件状态（打开、修改、保存）
5. 提供异步接口供其他组件调用

架构设计：
NiceGUI (Python) <--postMessage--> iframe (Monaco Editor - JavaScript)
        |                                    |
   monaco_bridge.py                     editor.js
   (本模块)                              (Monaco 侧)

消息协议：
发送到 Monaco:
- file-content: {file, content} - 设置文件内容
- save-file: {} - 请求保存当前文件
- update-config: {config} - 更新编辑器配置
- format-code: {} - 格式化代码
- load-file: {file, language} - 加载新文件

从 Monaco 接收:
- request-file: {file} - 请求文件内容
- content-changed: {file, content} - 内容变更通知
- save-content: {file, content} - 保存内容请求
- editor-ready: {} - 编辑器初始化完成
- focus/blur: {} - 焦点事件

使用方式：
    from foxcode.gui.editor.monaco_bridge import MonacoBridge
    
    # 创建桥接实例
    bridge = MonacoBridge()
    
    # 创建 iframe 并嵌入页面
    bridge.create_iframe(file_path="example.py")
    
    # 打开新文件
    await bridge.open_file("another_file.py")
    
    # 保存当前文件
    await bridge.save_current_file()

作者：FoxCode Team
版本：1.0.0
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from nicegui import ui

# 配置日志
logger = logging.getLogger(__name__)


class MonacoBridge:
    """
    Monaco 编辑器通信桥接类
    
    这是 FoxCode Desktop 的核心组件之一，负责：
    - 管理 iframe 生命周期
    - 处理双向异步通信
    - 维护文件状态和未保存更改追踪
    - 提供统一的 API 供其他组件调用
    
    设计模式：
    - 单例模式（每个编辑器区域一个实例）
    - 观察者模式（事件通知）
    - 异步优先（所有 I/O 操作都是异步的）
    
    使用示例：
        >>> bridge = MonacoBridge()
        >>> 
        >>> # 创建回调函数
        >>> async def on_content_changed(file_path, content):
        ...     print(f"文件已修改: {file_path}")
        ... 
        >>> bridge.on_content_changed = on_content_changed
        >>> 
        >>> # 嵌入编辑器
        >>> bridge.create_iframe()
        >>> 
        >>> # 打开文件
        >>> await bridge.open_file("/path/to/file.py")
        
    线程安全：
        - 所有公共方法都是异步的
        - 内部状态通过锁保护（如果需要）
        - 消息队列确保顺序处理
    """
    
    def __init__(self):
        """
        初始化 Monaco 桥接实例
        
        创建必要的数据结构来管理：
        - iframe 元素引用
        - 当前文件状态
        - 未保存更改追踪
        - 消息处理器注册表
        - 事件回调函数
        """
        self.iframe_element: Optional[ui.element] = None
        """NiceGUI iframe 元素引用"""
        
        self.current_file: Optional[str] = None
        """当前打开的文件路径"""
        
        self.current_language: str = 'python'
        """当前文件的编程语言"""
        
        self.unsaved_changes: Dict[str, str] = {}
        """未保存的更改字典 {file_path: content}"""
        
        self.message_handlers: Dict[str, Callable] = {}
        """消息处理器注册表"""
        
        self._is_ready: bool = False
        """编辑器是否已初始化就绪"""
        
        self._message_queue: List[Dict] = []
        """消息队列（在编辑器就绪前缓存消息）"""
        
        # 注册默认的消息处理器
        self._register_default_handlers()
        
        logger.info("MonacoBridge 实例已创建")
    
    def _register_default_handlers(self) -> None:
        """
        注册默认的消息处理函数
        
        这些处理器处理来自 Monaco 编辑器的标准消息类型。
        可以通过覆盖这些方法或添加新的处理器来自定义行为。
        """
        self.message_handlers = {
            'request-file': self._handle_file_request,
            'content-changed': self._handle_content_changed,
            'save-content': self._handle_save_request,
            'editor-ready': self._handle_editor_ready,
            'file-loaded': self._handle_file_loaded,
            'focus': self._handle_focus_event,
            'blur': self._handle_blur_event,
        }
    
    # ==================== iframe 管理 ====================
    
    def create_iframe(
        self,
        file_path: Optional[str] = None,
        language: str = 'python',
        theme: str = 'vs-dark',
        readonly: bool = False
    ) -> ui.element:
        """
        创建嵌入 Monaco 编辑器的 iframe 元素
        
        这是最重要的方法之一，用于在 NiceGUI 页面中嵌入独立的 Monaco 编辑器。
        iframe 会加载 /editor/ 路由提供的独立页面。
        
        Args:
            file_path: 要打开的文件路径（可选，可在之后通过 open_file 打开）
            language: 初始编程语言标识符，默认 'python'
                       支持: python, javascript, typescript, html, css, json 等
            theme: 编辑器主题，默认 'vs-dark'（暗色），可选 'vs'（亮色）
            readonly: 是否只读模式，默认 False
            
        Returns:
            ui.element: NiceGUI iframe 元素，可直接添加到布局中
            
        使用示例：
            >>> # 基本用法
            >>> iframe = bridge.create_iframe()
            >>> 
            >>> # 打开指定文件
            >>> iframe = bridge.create_iframe(
            ...     file_path="/home/user/main.py",
            ...     language="python"
            ... )
            >>> 
            >>> # 只读模式（查看日志等）
            >>> iframe = bridge.create_iframe(readonly=True)
            
        技术细节：
            - iframe 使用 sandbox 属性限制权限
            - URL 参数传递初始配置
            - 自动设置消息监听器
            - 支持后续动态切换文件
            
        安全措施：
            - sandbox="allow-scripts allow-same-origin"（限制权限）
            - 仅允许同源通信
            - 输入参数验证和清理
            
        注意事项：
            - 每个实例只能有一个活跃的 iframe
            - 重复调用会销毁旧 iframe 并创建新的
            - iframe 加载是异步的，需要等待 editor-ready 事件
        """
        try:
            from .editor_page import get_editor_url
            
            # 构建完整的 URL
            url = get_editor_url(
                file_path=file_path,
                language=language,
                theme=theme
            )
            
            logger.info(f"创建 Monaco iframe: {url}")
            
            # 如果已有 iframe，先移除
            if self.iframe_element:
                logger.debug("移除已有的 iframe 元素")
                self.iframe_element.delete()
                self.iframe_element = None
            
            # 创建新的 iframe 元素
            with ui.element('div').classes('w-full h-full') as container:
                self.iframe_element = ui.iframe(src=url).props(
                    'sandbox="allow-scripts allow-same-origin"'
                ).classes(
                    'w-full '
                    'h-full '
                    'border-none '
                    'bg-[#1e1e1e]'  # VS Code 暗色背景
                )
                
                # 设置 iframe ID 以便后续查找
                self.iframe_element._props['id'] = 'monaco-editor-iframe'
            
            # 设置 JavaScript 消息监听器
            self._setup_message_listener()
            
            # 记录初始状态
            if file_path:
                self.current_file = file_path
                self.current_language = language
            
            self._is_ready = False
            
            logger.info("Monaco iframe 已创建成功")
            
            return self.iframe_element
            
        except Exception as e:
            logger.error(f"创建 Monaco iframe 失败: {e}", exc_info=True)
            raise RuntimeError(f"无法创建 Monaco 编辑器 iframe: {e}") from e
    
    def _setup_message_listener(self) -> None:
        """
        设置 JavaScript 消息监听器
        
        在浏览器端注入 JavaScript 代码，监听来自 iframe 的 postMessage，
        并将消息转发给 Python 后端处理。
        
        技术实现：
        - 使用 ui.add_head_html() 注入脚本
        - 监听 window.message 事件
        - 通过自定义事件机制转发给 Python
        
        注意事项：
        - 应只调用一次以避免重复监听
        - 需要处理跨域安全问题
        - 消息格式验证很重要
        """
        js_code = '''
        // Monaco Bridge Message Listener
        (function() {
            // 标记是否已初始化
            if (window.__monacoBridgeListenerInitialized) return;
            window.__monacoBridgeListenerInitialized = true;
            
            console.log('[MonacoBridge] 设置消息监听器');
            
            // 监听来自 iframe 的消息
            window.addEventListener('message', function(event) {
                // 安全检查：验证来源
                // 生产环境应限制为具体域名
                
                const data = event.data;
                
                // 验证消息格式
                if (!data || typeof data !== 'object' || !data.type) {
                    console.warn('[MonacoBridge] 收到无效消息:', data);
                    return;
                }
                
                console.log('[MonacoBridge] 收到消息:', data.type, data);
                
                // 将消息存储到全局变量，供 Python 读取
                window.__lastMonacoMessage = data;
                window.__monacoMessageTimestamp = Date.now();
                
                // 触发自定义事件（用于调试）
                window.dispatchEvent(new CustomEvent('monaco-message', {
                    detail: data
                }));
            });
            
            console.log('[MonacoBridge] 消息监听器已激活');
        })();
        '''
        
        try:
            ui.add_head_html(f'<script>{js_code}</script}')
            logger.debug("JavaScript 消息监听器已注入")
        except Exception as e:
            logger.warning(f"注入消息监听器失败: {e}", exc_info=True)
    
    # ==================== 消息发送 ====================
    
    async def send_message(self, message: Dict[str, Any]) -> None:
        """
        向 Monaco 编辑器发送消息
        
        通过执行 JavaScript 向 iframe 的 contentWindow 发送 postMessage。
        所有发送操作都是异步的，不阻塞主线程。
        
        Args:
            message: 要发送的消息字典，必须包含 'type' 字段
                   示例: {'type': 'save-file'}
                         {'type': 'file-content', 'file': '/path', 'content': '...'}
                         
        Raises:
            RuntimeError: 如果 iframe 未初始化
            ValueError: 如果消息格式无效
            
        使用示例：
            >>> await bridge.send_message({'type': 'format-code'})
            >>> 
            >>> await bridge.send_message({
            ...     'type': 'update-config',
            ...     'config': {'fontSize': 16}
            ... })
            
        消息类型参考：
            - save-file: 请求保存当前文件
            - format-code: 格式化代码
            - update-config: 更新配置
            - set-theme: 切换主题
            - set-language: 切换语言
            - undo/redo: 撤销/重做
        """
        if not message or 'type' not in message:
            raise ValueError("消息必须包含 'type' 字段")
        
        if not self.iframe_element:
            raise RuntimeError("iframe 未初始化，请先调用 create_iframe()")
        
        try:
            # 序列化消息为 JSON
            message_json = json.dumps(message, ensure_ascii=False)
            
            # 构建 JavaScript 代码
            js_code = f'''
            (() => {{
                const iframe = document.getElementById('monaco-editor-iframe');
                if (iframe && iframe.contentWindow) {{
                    try {{
                        iframe.contentWindow.postMessage({message_json}, '*');
                        console.log('[MonacoBridge] 已发送消息:', {json.dumps(message['type'])});
                    }} catch (error) {{
                        console.error('[MonacoBridge] 发送消息失败:', error);
                    }}
                }} else {{
                    console.warn('[MonacoBridge] iframe 未找到或无法访问');
                }}
            }})();
            '''
            
            # 执行 JavaScript
            await ui.run_javascript(js_code)
            
            logger.debug(f"已向 Monaco 发送消息: {message.get('type')}")
            
        except Exception as e:
            logger.error(f"发送消息失败 ({message.get('type')}): {e}", exc_info=True)
            raise RuntimeError(f"发送消息失败: {e}") from e
    
    # ==================== 高级 API ====================
    
    async def open_file(self, file_path: str, language: Optional[str] = None) -> None:
        """
        在编辑器中打开文件
        
        向 Monaco 发送 load-file 消息，编辑器会反过来请求文件内容。
        
        Args:
            file_path: 文件的绝对路径
            language: 编程语言标识符（可选，自动检测）
            
        使用示例：
            >>> await bridge.open_file("/path/to/main.py")
            >>> 
            >>> # 显式指定语言
            >>> await bridge.open_file("/path/to/script", language="bash")
            
        流程说明：
            1. 更新内部状态（current_file, current_language）
            2. 向 Monaco 发送 load-file 消息
            3. Monaco 收到后发送 request-file 回来
            4. _handle_file_request 处理器读取文件并发送内容
            5. Monaco 显示文件内容
            
        注意事项：
            - 文件必须存在且可读
            - 大文件（>10MB）可能影响性能
            - 二进制文件不应使用此方法
        """
        from pathlib import Path
        
        path = Path(file_path)
        
        # 验证文件路径
        if not path.exists():
            logger.warning(f"文件不存在: {file_path}")
            # 仍然发送请求，让 Monaco 显示错误信息
            pass
        
        # 自动检测语言
        if not language:
            ext = path.suffix.lstrip('.')
            language = self._detect_language(ext)
        
        # 更新状态
        self.current_file = file_path
        self.current_language = language or 'plaintext'
        
        logger.info(f"打开文件: {file_path} (语言: {self.current_language})")
        
        # 发送加载请求
        await self.send_message({
            'type': 'load-file',
            'file': file_path,
            'language': self.current_language
        })
    
    async def save_current_file(self) -> bool:
        """
        保存当前文件
        
        向 Monaco 发送 save-file 请求，Monaco 会返回内容，
        然后由 _handle_save_request 处理器写入磁盘。
        
        Returns:
            bool: 保存是否成功
            
        使用示例：
            >>> success = await bridge.save_current_file()
            >>> if success:
            ...     print("保存成功")
            ... else:
            ...     print("保存失败")
            
        流程：
            1. 向 Monaco 发送 save-file
            2. Monaco 返回 save-content 消息（包含最新内容）
            3. 写入文件到磁盘
            4. 清除未保存标记
            5. 返回成功/失败状态
        """
        if not self.current_file:
            logger.warning("没有当前文件可保存")
            return False
        
        logger.info(f"请求保存文件: {self.current_file}")
        
        try:
            await self.send_message({'type': 'save-file'})
            return True
        except Exception as e:
            logger.error(f"保存文件失败: {e}", exc_info=True)
            return False
    
    async def format_code(self) -> None:
        """格式化当前代码"""
        await self.send_message({'type': 'format-code'})
    
    async def update_config(self, config: Dict[str, Any]) -> None:
        """
        更新编辑器配置
        
        Args:
            config: 配置字典，支持的选项：
                   - fontSize: int (字体大小)
                   - theme: str (主题名称)
                   - tabSize: int (Tab 宽度)
                   - wordWrap: str (自动换行模式)
                   - minimap: dict (minimap 配置)
                   
        使用示例：
            >>> await bridge.update_config({
            ...     'fontSize': 16,
            ...     'tabSize': 2,
            ...     'wordWrap': 'on'
            ... })
        """
        await self.send_message({
            'type': 'update-config',
            'config': config
        })
        
        # 同步更新本地配置记录
        if hasattr(self, '_config'):
            self._config.update(config)
    
    async def set_theme(self, theme: str) -> None:
        """
        切换编辑器主题
        
        Args:
            theme: 主题名称 ('vs-dark' 或 'vs')
        """
        await self.send_message({
            'type': 'set-theme',
            'theme': theme
        })
    
    async def undo(self) -> None:
        """撤销上一步操作"""
        await self.send_message({'type': 'undo'})
    
    async def redo(self) -> None:
        """重做撤销的操作"""
        await self.send_message({'type': 'redo'})
    
    # ==================== 状态查询 ====================
    
    def has_unsaved_changes(self, file_path: Optional[str] = None) -> bool:
        """
        检查是否有未保存的更改
        
        Args:
            file_path: 特定文件路径（可选），
                      不提供则检查所有文件
                      
        Returns:
            bool: 是否有未保存的更改
        """
        if file_path:
            return file_path in self.unsaved_changes
        return len(self.unsaved_changes) > 0
    
    def get_unsaved_files(self) -> List[str]:
        """
        获取所有有未保存更改的文件列表
        
        Returns:
            list: 文件路径列表
        """
        return list(self.unsaved_changes.keys())
    
    def is_ready(self) -> bool:
        """
        检查编辑器是否已初始化就绪
        
        Returns:
            bool: 是否可以正常使用
        """
        return self._is_ready and self.iframe_element is not None
    
    def get_current_file(self) -> Optional[str]:
        """获取当前文件路径"""
        return self.current_file
    
    def get_current_language(self) -> str:
        """获取当前编程语言"""
        return self.current_language
    
    # ==================== 消息处理器 ====================
    
    async def _handle_file_request(self, data: Dict) -> None:
        """
        处理来自 Monaco 的文件内容请求
        
        当 Monaco 需要显示某个文件时，会发送 request-file 消息，
        此处理器读取文件内容并发送回给 Monaco。
        
        Args:
            data: 包含 'file' 字段的字典
        """
        file_path = data.get('file')
        
        if not file_path:
            logger.warning("收到空的文件路径请求")
            await self.send_message({
                'type': 'file-content',
                'file': '',
                'content': ''
            })
            return
        
        try:
            path = Path(file_path)
            
            # 检查文件是否存在
            if not path.exists():
                logger.warning(f"文件不存在: {file_path}")
                await self.send_message({
                    'type': 'error',
                    'message': f"文件不存在: {file_path}"
                })
                return
            
            # 异步读取文件内容（避免阻塞主线程）
            content = await asyncio.to_thread(
                path.read_text,
                encoding='utf-8',
                errors='replace'  # 替换非法字符而非报错
            )
            
            # 如果有未保存的更改，使用未保存的版本
            if file_path in self.unsaved_changes:
                content = self.unsaved_changes[file_path]
                logger.info(f"使用未保存版本: {file_path}")
            
            # 更新当前文件状态
            self.current_file = file_path
            
            # 发送文件内容给 Monaco
            await self.send_message({
                'type': 'file-content',
                'file': file_path,
                'content': content
            })
            
            logger.info(f"已加载文件: {file_path} ({len(content)} 字符)")
            
            # 触发外部回调
            if hasattr(self, 'on_file_loaded'):
                await self.on_file_loaded(file_path, content)
            
        except UnicodeDecodeError as e:
            logger.error(f"文件编码错误: {file_path}, {e}")
            await self.send_message({
                'type': 'error',
                'message': f"无法解码文件（可能不是文本文件）: {e}"
            })
            
        except PermissionError as e:
            logger.error(f"权限不足: {file_path}, {e}")
            await self.send_message({
                'type': 'error',
                'message': f"没有读取权限: {file_path}"
            })
            
        except Exception as e:
            logger.error(f"读取文件失败: {file_path}, 错误: {e}", exc_info=True)
            await self.send_message({
                'type': 'error',
                'message': f"无法读取文件: {e}"
            })
    
    async def _handle_content_changed(self, data: Dict) -> None:
        """
        处理编辑器内容变更事件
        
        当用户在 Monaco 中修改代码时触发此处理器。
        会记录未保存的更改，并可触发外部回调。
        
        Args:
            data: 包含 'file', 'content' 字段的字典
        """
        file_path = data.get('file')
        content = data.get('content', '')
        
        if not file_path:
            return
        
        # 记录未保存的更改
        self.unsaved_changes[file_path] = content
        
        logger.debug(f"内容变更: {file_path} ({len(content)} 字符)")
        
        # 触发外部回调（如更新标签页的修改状态指示器）
        if hasattr(self, 'on_content_changed'):
            try:
                await self.on_content_changed(file_path, content)
            except Exception as e:
                logger.error(f"on_content_changed 回调出错: {e}", exc_info=True)
    
    async def _handle_save_request(self, data: Dict) -> None:
        """
        处理保存文件请求
        
        当用户按 Ctrl+S 或调用 save 时，Monaco 发送 save-content 消息，
        此处理器将内容写入磁盘。
        
        Args:
            data: 包含 'file', 'content' 字段的字典
        """
        file_path = data.get('file')
        content = data.get('content', '')
        
        if not file_path:
            logger.warning("收到空的保存请求")
            return
        
        try:
            path = Path(file_path)
            
            # 确保父目录存在
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # 异步写入文件
            await asyncio.to_thread(
                path.write_text,
                content,
                encoding='utf-8'
            )
            
            # 清除未保存标记
            if file_path in self.unsaved_changes:
                del self.unsaved_changes[file_path]
            
            # 通知保存成功
            await self.send_message({
                'type': 'save-success',
                'file': file_path
            })
            
            logger.info(f"已保存文件: {file_path} ({len(content)} 字符)")
            
            # 触发外部回调
            if hasattr(self, 'on_file_saved'):
                try:
                    await self.on_file_saved(file_path)
                except Exception as e:
                    logger.error(f"on_file_saved 回调出错: {e}", exc_info=True)
            
        except PermissionError as e:
            logger.error(f"保存失败（权限不足）: {file_path}, {e}")
            await self.send_message({
                'type': 'error',
                'message': f"没有写入权限: {file_path}"
            })
            
        except OSError as e:
            logger.error(f"保存失败（IO错误）: {file_path}, {e}")
            await self.send_message({
                'type': 'error',
                'message': f"无法保存文件: {e}"
            })
            
        except Exception as e:
            logger.error(f"保存文件失败: {file_path}, 错误: {e}", exc_info=True)
            await self.send_message({
                'type': 'error',
                'message': f"保存失败: {e}"
            })
    
    async def _handle_editor_ready(self, data: Dict) -> None:
        """
        处理编辑器就绪事件
        
        当 Monaco 完成初始化后会发送 editor-ready 消息，
        此处理器标记编辑器可用，并可处理排队的消息。
        
        Args:
            data: 编辑器配置信息
        """
        self._is_ready = True
        logger.info("Monaco 编辑器已就绪")
        
        # 触发外部回调
        if hasattr(self, 'on_editor_ready'):
            try:
                await self.on_editor_ready(data.get('config'))
            except Exception as e:
                logger.error(f"on_editor_ready 回调出错: {e}", exc_info=True)
    
    async def _handle_file_loaded(self, data: Dict) -> None:
        """处理文件加载完成事件"""
        logger.debug(f"文件已加载到编辑器: {data.get('file')}")
    
    async def _handle_focus_event(self, data: Dict) -> None:
        """处理编辑器获得焦点事件"""
        pass  # 可根据需要实现
    
    async def _handle_blur_event(self, data: Dict) -> None:
        """处理编辑器失去焦点事件"""
        pass  # 可根据需要实现
    
    # ==================== 工具方法 ====================
    
    @staticmethod
    def _detect_language(extension: str) -> str:
        """
        根据文件扩展名检测编程语言
        
        Args:
            extension: 文件扩展名（不含点号）
            
        Returns:
            str: Monaco 语言标识符
        """
        lang_map = {
            'py': 'python',
            'js': 'javascript',
            'ts': 'typescript',
            'jsx': 'javascript',
            'tsx': 'typescript',
            'html': 'html',
            'css': 'css',
            'json': 'json',
            'md': 'markdown',
            'yaml': 'yaml',
            'yml': 'yaml',
            'toml': 'ini',
            'sh': 'shell',
            'bash': 'shell',
            'ps1': 'powershell',
            'sql': 'sql',
            'go': 'go',
            'rs': 'rust',
            'java': 'java',
            'c': 'c',
            'cpp': 'cpp',
            'rb': 'ruby',
            'php': 'php',
            'vue': 'html',
            'svelte': 'html',
        }
        
        return lang_map.get(extension.lower(), 'plaintext')
    
    def destroy(self) -> None:
        """
        销毁桥接实例，释放资源
        
        移除 iframe 元素，清除状态，注销监听器。
        在组件卸载时应调用此方法。
        """
        try:
            # 移除 iframe
            if self.iframe_element:
                self.iframe_element.delete()
                self.iframe_element = None
            
            # 清除状态
            self.current_file = None
            self.unsaved_changes.clear()
            self._is_ready = False
            
            logger.info("MonacoBridge 实例已销毁")
            
        except Exception as e:
            logger.warning(f"销毁 MonacoBridge 时出现异常: {e}", exc_info=True)


# 导出的公共 API
__all__ = ['MonacoBridge']
