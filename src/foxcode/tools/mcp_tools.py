"""
FoxCode MCP 工具包装器

将 MCP 工具包装为 FoxCode 内置工具
使得 MCP 工具可以像内置工具一样被调用
"""

from __future__ import annotations

import logging
from typing import Any

from foxcode.services.mcp import mcp_manager
from foxcode.tools.base import BaseTool, ToolCategory, ToolParameter, ToolResult, registry

logger = logging.getLogger(__name__)


class MCPToolWrapper(BaseTool):
    """
    MCP 工具包装器
    
    将 MCP 服务器的工具包装为 FoxCode 工具
    """

    name = "mcp_tool"
    description = "MCP 工具包装器（动态）"
    category = ToolCategory.SYSTEM
    dangerous = False

    def __init__(self, mcp_tool_name: str, server_name: str, description: str, input_schema: dict[str, Any]):
        """
        初始化 MCP 工具包装器
        
        Args:
            mcp_tool_name: MCP 工具名称
            server_name: MCP 服务器名称
            description: 工具描述
            input_schema: 输入 Schema
        """
        super().__init__()
        self._mcp_tool_name = mcp_tool_name
        self._server_name = server_name
        self.name = f"mcp_{server_name}_{mcp_tool_name}"
        self.description = f"[MCP:{server_name}] {description}"
        self._input_schema = input_schema

        # 从 Schema 构建参数定义
        self.parameters = self._build_parameters()

    def _build_parameters(self) -> list[ToolParameter]:
        """从 Schema 构建参数定义"""
        parameters = []
        properties = self._input_schema.get("properties", {})
        required = set(self._input_schema.get("required", []))

        for param_name, param_info in properties.items():
            param = ToolParameter(
                name=param_name,
                type=self._map_json_type(param_info.get("type", "string")),
                description=param_info.get("description", ""),
                required=param_name in required,
                default=param_info.get("default"),
                enum=param_info.get("enum"),
            )
            parameters.append(param)

        return parameters

    def _map_json_type(self, json_type: str) -> str:
        """映射 JSON Schema 类型到工具参数类型"""
        type_mapping = {
            "string": "string",
            "number": "float",
            "integer": "int",
            "boolean": "bool",
            "array": "array",
            "object": "dict",
        }
        return type_mapping.get(json_type, "string")

    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行 MCP 工具"""
        try:
            result = await mcp_manager.call_tool(self._mcp_tool_name, kwargs)

            return ToolResult(
                success=not result.is_error,
                output=result.get_text_content(),
                error=result.get_text_content() if result.is_error else None,
                data={
                    "mcp_tool": True,
                    "server": self._server_name,
                    "tool": self._mcp_tool_name,
                },
            )

        except Exception as e:
            logger.error(f"MCP tool {self.name} execution failed: {e}")
            return ToolResult(
                success=False,
                output="",
                error=str(e),
            )


class MCPToolRegistry:
    """
    MCP 工具注册表
    
    管理动态注册的 MCP 工具
    """

    def __init__(self):
        self._registered_tools: dict[str, str] = {}  # tool_name -> server_name
        self._logger = logging.getLogger("foxcode.mcp.tool_registry")

    def register_mcp_tools(self) -> int:
        """
        注册所有 MCP 工具到 FoxCode 工具注册表
        
        Returns:
            成功注册的工具数量
        """
        registered = 0

        for tool in mcp_manager.list_tools():
            try:
                # 创建包装器
                wrapper = MCPToolWrapper(
                    mcp_tool_name=tool.name,
                    server_name=tool.server_name,
                    description=tool.description,
                    input_schema=tool.input_schema,
                )

                # 注册到工具注册表
                registry._tools[wrapper.name] = wrapper.__class__
                registry._instances[wrapper.name] = wrapper

                self._registered_tools[wrapper.name] = tool.server_name
                registered += 1

                self._logger.debug(f"Registered MCP tool: {wrapper.name}")

            except Exception as e:
                self._logger.error(f"Failed to register MCP tool {tool.name}: {e}")

        if registered > 0:
            self._logger.info(f"Registered {registered} MCP tools")

        return registered

    def unregister_mcp_tools(self, server_name: str | None = None) -> int:
        """
        注销 MCP 工具
        
        Args:
            server_name: 服务器名称，如果为 None 则注销所有
            
        Returns:
            注销的工具数量
        """
        unregistered = 0

        to_remove = []
        for tool_name, srv_name in self._registered_tools.items():
            if server_name is None or srv_name == server_name:
                to_remove.append(tool_name)

        for tool_name in to_remove:
            try:
                # 从工具注册表移除
                registry._tools.pop(tool_name, None)
                registry._instances.pop(tool_name, None)

                self._registered_tools.pop(tool_name)
                unregistered += 1

                self._logger.debug(f"Unregistered MCP tool: {tool_name}")

            except Exception as e:
                self._logger.error(f"Failed to unregister MCP tool {tool_name}: {e}")

        return unregistered

    def list_registered_tools(self) -> list[dict[str, str]]:
        """列出已注册的 MCP 工具"""
        return [
            {"name": name, "server": server}
            for name, server in self._registered_tools.items()
        ]


# 全局 MCP 工具注册表
mcp_tool_registry = MCPToolRegistry()


def register_mcp_tools() -> int:
    """
    注册所有 MCP 工具
    
    Returns:
        成功注册的工具数量
    """
    return mcp_tool_registry.register_mcp_tools()


def unregister_mcp_tools(server_name: str | None = None) -> int:
    """
    注销 MCP 工具
    
    Args:
        server_name: 服务器名称，如果为 None 则注销所有
        
    Returns:
        注销的工具数量
    """
    return mcp_tool_registry.unregister_mcp_tools(server_name)
