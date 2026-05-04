# Monaco 编辑器路由和页面服务

"""
Monaco Editor 路由管理 - 提供 VS Code 级别的代码编辑功能

本模块负责：
1. 注册 FastAPI 路由，提供 Monaco 编辑器独立页面
2. 管理编辑器静态资源（HTML、JS、CSS）
3. 处理文件加载请求（可选的服务端渲染）
4. 配置 CORS 和安全策略

架构设计：
NiceGUI 主应用 (端口 8080)
|
+-- iframe src="/editor?file=xxx.py&lang=python"
    |
    +-- 本模块提供的独立页面
        |
        +-- Monaco Editor (CDN/本地)
        +-- 自定义主题和配置
        +-- postMessage 通信接口

使用方式：
    # 自动注册（推荐）
    from foxcode.gui.app import create_app
    app = create_app()  # 会自动调用 register_editor_routes
    
    # 手动注册
    from nicegui import app as nicegui_app
    from foxcode.gui.editor.editor_page import register_editor_routes
    register_editor_routes(nicegui_app)

技术栈：
- FastAPI: Web 框架和路由
- Monaco Editor: 代码编辑器引擎
- postMessage API: 跨窗口通信

作者：FoxCode Team
版本：1.0.0
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/editor")

# 静态资源目录
STATIC_DIR = Path(__file__).parent / "static"

# 确保 static 目录存在
STATIC_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/", response_class=HTMLResponse)
async def editor_index(
    request: Request,
    file: Optional[str] = Query(None, description="要打开的文件路径"),
    lang: Optional[str] = Query("python", description="编程语言标识符"),
    theme: Optional[str] = Query("vs-dark", description="编辑器主题"),
    readonly: Optional[bool] = Query(False, description="是否只读模式")
):
    """
    Monaco 编辑器主页 - 提供独立的编辑器界面
    
    这是 iframe 嵌入的目标页面，包含完整的 Monaco Editor 实例。
    
    Args:
        request: FastAPI 请求对象
        file: 要打开的文件的绝对路径（可选）
        lang: 编程语言，默认 'python'，支持：
              python, javascript, typescript, html, css, json,
              markdown, yaml, shell, sql, go, rust 等
        theme: 编辑器主题，默认 'vs-dark'（暗色），可选 'vs'（亮色）
        readonly: 是否只读模式，默认 False
        
    Returns:
        HTMLResponse: 包含 Monaco 编辑器的完整 HTML 页面
        
    URL 示例：
        /editor/?file=/path/to/file.py&lang=python&theme=vs-dark
        /editor/
        /editor/?lang=javascript&readonly=true
        
    功能特性：
        - 自动检测语言（根据文件扩展名）
        - 语法高亮和智能提示
        - 代码折叠和 minimap
        - 多光标编辑
        - 查找替换
        - 与主应用的双向通信
    """
    logger.info(f"访问编辑器页面: file={file}, lang={lang}, theme={theme}")
    
    # 读取 HTML 模板
    html_file = STATIC_DIR / "monaco.html"
    
    if not html_file.exists():
        logger.error(f"Monaco HTML 文件不存在: {html_file}")
        return HTMLResponse(
            content="<h1>Monaco Editor 未正确安装</h1><p>请检查静态资源文件</p>",
            status_code=500
        )
    
    try:
        # 返回 HTML 文件
        return FileResponse(
            path=str(html_file),
            media_type="text/html",
            headers={
                "Cache-Control": "no-cache",
                "X-Content-Type-Options": "nosniff"
            }
        )
        
    except Exception as e:
        logger.error(f"读取 Monaco HTML 失败: {e}", exc_info=True)
        return HTMLResponse(
            content=f"<h1>服务器错误</h1><p>{str(e)}</p>",
            status_code=500
        )


@router.get("/static/{filename:path}")
async def serve_static(filename: str):
    """
    提供编辑器相关的静态资源
    
    包括 JavaScript、CSS、图片等文件。
    所有静态文件都位于 gui/editor/static/ 目录下。
    
    Args:
        filename: 静态文件路径（相对于 static 目录）
        
    Returns:
        FileResponse: 请求的静态文件，或 404 错误
        
    支持的文件类型：
        - JavaScript (.js)
        - CSS (.css)
        - 图片 (.png, .svg, .ico)
        - 字体 (.woff, .woff2, .ttf)
        
    安全措施：
        - 路径遍历防护（禁止 .. 访问）
        - MIME 类型自动检测
        - 缓存控制头设置
    """
    # 安全检查：防止路径遍历攻击
    if ".." in filename or filename.startswith("/"):
        logger.warning(f"检测到可疑路径访问: {filename}")
        return JSONResponse(
            status_code=403,
            content={"error": "Forbidden", "message": "非法路径"}
        )
    
    # 构建完整路径
    file_path = STATIC_DIR / filename
    
    # 检查文件是否存在且在允许目录内
    if not file_path.exists():
        logger.warning(f"静态文件不存在: {filename}")
        return JSONResponse(
            status_code=404,
            content={"error": "Not Found", "message": f"文件不存在: {filename}"}
        )
    
    # 确保不离开 static 目录
    try:
        file_path.resolve().relative_to(STATIC_DIR.resolve())
    except ValueError:
        logger.error(f"路径遍历攻击尝试: {filename}")
        return JSONResponse(
            status_code=403,
            content={"error": "Forbidden", "message": "访问被拒绝"}
        )
    
    try:
        # 返回文件
        return FileResponse(
            path=str(file_path),
            headers={
                "Cache-Control": "public, max-age=3600"  # 缓存 1 小时
            }
        )
        
    except Exception as e:
        logger.error(f"提供静态文件失败: {filename}, 错误: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal Server Error", "message": str(e)}
        )


@router.get("/health")
async def health_check():
    """
    健康检查端点 - 用于监控和服务发现
    
    Returns:
        JSONResponse: 服务状态信息
    """
    return {
        "status": "healthy",
        "service": "foxcode-monaco-editor",
        "version": "1.0.0",
        "static_dir_exists": STATIC_DIR.exists(),
        "static_files_count": len(list(STATIC_DIR.glob("*"))) if STATIC_DIR.exists() else 0
    }


def register_editor_routes(app) -> None:
    """
    将 Monaco 编辑器路由注册到 FastAPI 应用
    
    这是最重要的函数之一，必须在 ui.run() 之前调用，
    否则编辑器页面将无法访问。
    
    Args:
        app: NiceGUI/FastAPI 应用实例（通常是 nicegui.app）
        
    使用示例：
        >>> from nicegui import app as nicegui_app
        >>> from foxcode.gui.editor.editor_page import register_editor_routes
        >>> 
        >>> # 在创建 UI 之前注册路由
        >>> register_editor_routes(nicegui_app)
        >>> 
        >>> # 现在可以正常使用编辑器了
        >>> ui.run()
        
    注册的路由：
        GET /editor/          - 编辑器主页
        GET /editor/static/*  - 静态资源
        GET /editor/health    - 健康检查
        
    注意事项：
        - 必须在 ui.run() 之前调用
        - 只需调用一次（重复调用会警告）
        - 路由前缀为 /editor/
        
    异常处理：
        - 如果 app 为 None，记录错误并抛出异常
        - 如果路由已存在，记录警告但不中断
    """
    global router
    
    if app is None:
        error_msg = "无法注册路由: 应用实例为 None"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    try:
        # 检查是否已注册
        existing_routes = [route.path for route in app.routes]
        if "/editor/" in existing_routes:
            logger.warning("Monaco 编辑器路由已存在，跳过重复注册")
            return
        
        # 注册路由
        app.include_router(router)
        
        logger.info("成功注册 Monaco 编辑器路由:")
        logger.info("  - GET /editor/")
        logger.info("  - GET /editor/static/{filename}")
        logger.info("  - GET /editor/health")
        
        # 验证静态目录
        if not STATIC_DIR.exists():
            logger.warning(f"静态资源目录不存在: {STATIC_DIR}")
            logger.warning("Monaco 编辑器可能无法正常工作")
        else:
            static_files = list(STATIC_DIR.glob("*"))
            logger.info(f"静态资源目录就绪，包含 {len(static_files)} 个文件")
            
    except Exception as e:
        error_msg = f"注册 Monaco 编辑器路由失败: {e}"
        logger.error(error_msg, exc_info=True)
        raise RuntimeError(error_msg) from e


def get_editor_url(
    file_path: str = None,
    language: str = "python",
    theme: str = "vs-dark",
    base_url: str = "/editor/"
) -> str:
    """
    构建编辑器页面的完整 URL
    
    这是一个辅助函数，用于生成正确的 iframe src URL。
    
    Args:
        file_path: 要打开的文件路径（可选）
        language: 编程语言标识符
        theme: 编辑器主题名称
        base_url: 基础 URL，默认 /editor/
        
    Returns:
        str: 完整的 URL 字符串
        
    使用示例：
        >>> get_editor_url()
        '/editor/'
        
        >>> get_editor_url(file_path="/home/user/main.py")
        '/editor/?file=/home/user/main.py&lang=python'
        
        >>> get_editor_url(language="javascript", theme="vs")
        '/editor/?lang=javascript&theme=vs'
        
    URL 参数说明：
        - file: 文件的绝对路径或相对路径
        - lang: Monaco 支持的语言标识符
        - theme: vs-dark（暗色）或 vs（亮色）
    """
    from urllib.parse import urlencode
    
    params = {}
    
    if file_path:
        params["file"] = file_path
    
    params["lang"] = language
    params["theme"] = theme
    
    query_string = urlencode(params)
    
    return f"{base_url}?{query_string}" if params else base_url


# 导出的公共 API
__all__ = [
    'register_editor_routes',
    'get_editor_url',
    'router',
]
