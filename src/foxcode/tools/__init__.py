"""
FoxCode 工具模块 - 导出所有工具和工具注册表

这个文件统一导出 FoxCode 的所有工具组件。

工具分类:
1. 基础组件:
   - BaseTool: 工具基类
   - ToolRegistry: 工具注册表
   - ToolResult: 工具执行结果
   - registry: 全局工具注册表实例
   - tool: 工具注册装饰器

2. AI 工具:
   - AIChatTool: AI 对话
   - AICodeTool: AI 代码生成
   - AISummarizeTool: AI 摘要

3. 文件工具:
   - ReadFileTool / WriteFileTool / EditFileTool: 文件读写编辑
   - ListDirectoryTool / SearchInFileTool / DeleteFileTool / GlobTool: 目录和搜索

4. Shell 工具:
   - ShellExecuteTool / ShellCheckStatusTool / ShellStopTool: 命令执行

5. 代码工具:
   - GrepTool / SearchCodebaseTool: 代码搜索

6. Playwright 浏览器工具:
   - 浏览器操作、截图、表单填写等

7. MCP 工具:
   - MCPToolWrapper / MCPToolRegistry: MCP 协议工具

使用方式:
    from foxcode.tools import registry

    result = await registry.execute("read_file", path="main.py")
"""

from foxcode.tools.base import (
    BaseTool,
    ToolCategory,
    ToolParameter,
    ToolRegistry,
    ToolResult,
    registry,
    tool,
)
from foxcode.tools.ai_tools import AIChatTool, AICodeTool, AISummarizeTool
from foxcode.tools.code_tools import GrepTool, SearchCodebaseTool
from foxcode.tools.file_tools import (
    DeleteFileTool,
    EditFileTool,
    GlobTool,
    ListDirectoryTool,
    ReadFileTool,
    SearchInFileTool,
    WriteFileTool,
)
from foxcode.tools.mcp_tools import (
    MCPToolRegistry,
    MCPToolWrapper,
    mcp_tool_registry,
    register_mcp_tools,
    unregister_mcp_tools,
)
from foxcode.tools.playwright_tools import (
    BrowserSession,
    PlaywrightAssertResponseTool,
    PlaywrightClickAndSwitchTabTool,
    PlaywrightClickTool,
    PlaywrightCloseTool,
    PlaywrightConsoleLogsTool,
    PlaywrightCustomUserAgentTool,
    PlaywrightDragTool,
    PlaywrightEvaluateTool,
    PlaywrightExpectResponseTool,
    PlaywrightFillTool,
    PlaywrightGetTool,
    PlaywrightGetVisibleHtmlTool,
    PlaywrightGetVisibleTextTool,
    PlaywrightGoBackTool,
    PlaywrightGoForwardTool,
    PlaywrightHoverTool,
    PlaywrightListSessionsTool,
    PlaywrightNavigateTool,
    PlaywrightPressKeyTool,
    PlaywrightResizeTool,
    PlaywrightSaveAsPdfTool,
    PlaywrightScreenshotTool,
    PlaywrightSelectTool,
    PlaywrightSessionManager,
    PlaywrightStartTool,
    PlaywrightUploadFileTool,
    session_manager,
)
from foxcode.tools.shell_tools import (
    ShellCheckStatusTool,
    ShellExecuteTool,
    ShellStopTool,
)

__all__ = [
    # 基类
    "BaseTool",
    "ToolCategory",
    "ToolParameter",
    "ToolResult",
    "ToolRegistry",
    "registry",
    "tool",
    # AI 工具
    "AIChatTool",
    "AICodeTool",
    "AISummarizeTool",
    # 文件工具
    "ReadFileTool",
    "WriteFileTool",
    "EditFileTool",
    "ListDirectoryTool",
    "SearchInFileTool",
    "DeleteFileTool",
    "GlobTool",
    # Shell 工具
    "ShellExecuteTool",
    "ShellCheckStatusTool",
    "ShellStopTool",
    # 代码工具
    "GrepTool",
    "SearchCodebaseTool",
    # Playwright 浏览器工具
    "BrowserSession",
    "PlaywrightSessionManager",
    "session_manager",
    "PlaywrightStartTool",
    "PlaywrightCloseTool",
    "PlaywrightListSessionsTool",
    "PlaywrightNavigateTool",
    "PlaywrightGoBackTool",
    "PlaywrightGoForwardTool",
    "PlaywrightClickTool",
    "PlaywrightFillTool",
    "PlaywrightSelectTool",
    "PlaywrightHoverTool",
    "PlaywrightPressKeyTool",
    "PlaywrightScreenshotTool",
    "PlaywrightGetVisibleTextTool",
    "PlaywrightGetVisibleHtmlTool",
    "PlaywrightGetTool",
    "PlaywrightExpectResponseTool",
    "PlaywrightAssertResponseTool",
    "PlaywrightEvaluateTool",
    "PlaywrightResizeTool",
    "PlaywrightUploadFileTool",
    "PlaywrightDragTool",
    "PlaywrightClickAndSwitchTabTool",
    "PlaywrightSaveAsPdfTool",
    "PlaywrightCustomUserAgentTool",
    "PlaywrightConsoleLogsTool",
    # MCP 工具
    "MCPToolWrapper",
    "MCPToolRegistry",
    "mcp_tool_registry",
    "register_mcp_tools",
    "unregister_mcp_tools",
]
