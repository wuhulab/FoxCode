"""
FoxCode 工具模块

导出所有工具和工具注册表
"""

from foxcode.tools.base import (
    BaseTool,
    ToolCategory,
    ToolParameter,
    ToolResult,
    ToolRegistry,
    registry,
    tool,
)
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
from foxcode.tools.shell_tools import (
    ShellCheckStatusTool,
    ShellExecuteTool,
    ShellStopTool,
)
from foxcode.tools.playwright_tools import (
    BrowserSession,
    PlaywrightSessionManager,
    session_manager,
    PlaywrightStartTool,
    PlaywrightCloseTool,
    PlaywrightListSessionsTool,
    PlaywrightNavigateTool,
    PlaywrightGoBackTool,
    PlaywrightGoForwardTool,
    PlaywrightClickTool,
    PlaywrightFillTool,
    PlaywrightSelectTool,
    PlaywrightHoverTool,
    PlaywrightPressKeyTool,
    PlaywrightScreenshotTool,
    PlaywrightGetVisibleTextTool,
    PlaywrightGetVisibleHtmlTool,
    PlaywrightGetTool,
    PlaywrightExpectResponseTool,
    PlaywrightAssertResponseTool,
    PlaywrightEvaluateTool,
    PlaywrightResizeTool,
    PlaywrightUploadFileTool,
    PlaywrightDragTool,
    PlaywrightClickAndSwitchTabTool,
    PlaywrightSaveAsPdfTool,
    PlaywrightCustomUserAgentTool,
    PlaywrightConsoleLogsTool,
)
from foxcode.tools.mcp_tools import (
    MCPToolWrapper,
    MCPToolRegistry,
    mcp_tool_registry,
    register_mcp_tools,
    unregister_mcp_tools,
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
