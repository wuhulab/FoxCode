"""
FoxCode MCP (Model Context Protocol) 模块

实现 MCP 协议，支持与外部工具和资源服务器通信
MCP 是一个标准化的协议，用于 AI 模型与外部工具之间的通信

安全说明：
- MCP 服务器命令需要验证，防止命令注入
- 使用白名单机制限制可执行的命令
- 对命令参数进行严格验证

参考: https://modelcontextprotocol.io/
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)


# MCP 服务器命令白名单
# 只有在此列表中的命令才允许执行
DEFAULT_ALLOWED_COMMANDS = [
    "npx",
    "node",
    "python",
    "python3",
    "uvx",
    "uv",
    "pip",
    "pip3",
]


def validate_command_security(command: str, allowed_commands: list[str] | None = None) -> tuple[bool, str]:
    """
    验证命令安全性
    
    检查命令是否在允许的白名单中，防止命令注入攻击。
    
    Args:
        command: 要验证的命令
        allowed_commands: 允许的命令列表，如果为 None 则使用默认白名单
        
    Returns:
        (是否安全, 原因消息)
    """
    if not command:
        return False, "命令不能为空"
    
    # 使用默认白名单或自定义白名单
    allowed = allowed_commands or DEFAULT_ALLOWED_COMMANDS
    
    # 获取命令的基本名称（去除路径）
    command_basename = os.path.basename(command)
    
    # 检查命令是否在白名单中
    if command_basename not in allowed:
        logger.warning(f"命令 '{command}' 不在允许的白名单中")
        return False, f"命令 '{command_basename}' 不在允许的白名单中。允许的命令: {', '.join(allowed)}"
    
    # 检查命令是否存在于系统 PATH 中
    command_path = shutil.which(command)
    if command_path is None:
        # 如果是相对路径，检查是否是白名单中的命令
        if command_basename in allowed:
            logger.warning(f"命令 '{command}' 在白名单中但未找到可执行文件")
            return True, f"命令在白名单中，但未找到可执行文件（将在运行时检查）"
        return False, f"命令 '{command}' 未找到"
    
    return True, "命令验证通过"


def validate_arguments_security(args: list[str]) -> tuple[bool, str]:
    """
    验证命令参数安全性
    
    检查参数中是否包含危险的命令注入模式。
    
    Args:
        args: 命令参数列表
        
    Returns:
        (是否安全, 原因消息)
    """
    if not args:
        return True, "参数为空"
    
    # 危险模式列表
    dangerous_patterns = [
        "&&", "||", "|", ";", "`", "$(", "${",  # 命令连接和替换
        ">", ">>", "<", "<<",  # 重定向
        "../", "..\\",  # 路径穿越
    ]
    
    for arg in args:
        for pattern in dangerous_patterns:
            if pattern in arg:
                logger.warning(f"参数 '{arg}' 包含危险模式 '{pattern}'")
                return False, f"参数包含危险模式: {pattern}"
    
    return True, "参数验证通过"


class MCPMessageType(str, Enum):
    """MCP 消息类型"""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"


class MCPCapability(str, Enum):
    """MCP 能力类型"""
    TOOLS = "tools"
    RESOURCES = "resources"
    PROMPTS = "prompts"
    LOGGING = "logging"


class MCPErrorCode(int, Enum):
    """MCP 错误码"""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    SERVER_ERROR_START = -32000
    SERVER_ERROR_END = -32099


@dataclass
class MCPTool:
    """MCP 工具定义"""
    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "server_name": self.server_name,
        }


@dataclass
class MCPResource:
    """MCP 资源定义"""
    uri: str
    name: str
    description: str = ""
    mime_type: str = "text/plain"
    server_name: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type,
            "server_name": self.server_name,
        }


@dataclass
class MCPPrompt:
    """MCP 提示模板定义"""
    name: str
    description: str
    arguments: list[dict[str, Any]] = field(default_factory=list)
    server_name: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "arguments": self.arguments,
            "server_name": self.server_name,
        }


class MCPToolResult(BaseModel):
    """MCP 工具执行结果"""
    content: list[dict[str, Any]] = Field(default_factory=list)
    is_error: bool = False
    
    def get_text_content(self) -> str:
        """获取文本内容"""
        texts = []
        for item in self.content:
            if item.get("type") == "text":
                texts.append(item.get("text", ""))
        return "\n".join(texts)
    
    @classmethod
    def from_text(cls, text: str, is_error: bool = False) -> "MCPToolResult":
        """从文本创建结果"""
        return cls(
            content=[{"type": "text", "text": text}],
            is_error=is_error,
        )


class MCPServerConfig(BaseModel):
    """
    MCP 服务器配置
    
    安全说明：
    - command 字段会进行白名单验证
    - args 字段会进行危险模式检查
    - 禁止执行不在白名单中的命令
    """
    name: str = Field(description="服务器名称")
    command: str = Field(description="启动命令")
    args: list[str] = Field(default_factory=list, description="命令参数")
    env: dict[str, str] = Field(default_factory=dict, description="环境变量")
    cwd: str | None = Field(default=None, description="工作目录")
    enabled: bool = Field(default=True, description="是否启用")
    auto_start: bool = Field(default=True, description="是否自动启动")
    restart_on_failure: bool = Field(default=True, description="失败时是否重启")
    max_restart_attempts: int = Field(default=3, description="最大重启尝试次数")
    # 安全配置
    allowed_commands: list[str] | None = Field(
        default=None,
        description="允许的命令白名单（为 None 则使用默认白名单）"
    )
    skip_security_validation: bool = Field(
        default=False,
        description="是否跳过安全验证（不推荐，仅用于开发环境）"
    )
    
    @field_validator("command", mode="after")
    @classmethod
    def validate_command(cls, v: str) -> str:
        """验证命令是否在白名单中"""
        if not v:
            raise ValueError("命令不能为空")
        return v
    
    @model_validator(mode="after")
    def validate_security(self) -> "MCPServerConfig":
        """验证命令和参数的安全性"""
        if self.skip_security_validation:
            logger.warning(f"服务器 '{self.name}' 跳过了安全验证，这存在安全风险")
            return self
        
        # 验证命令
        is_valid, message = validate_command_security(self.command, self.allowed_commands)
        if not is_valid:
            raise ValueError(f"服务器 '{self.name}' 命令验证失败: {message}")
        
        # 验证参数
        is_valid, message = validate_arguments_security(self.args)
        if not is_valid:
            raise ValueError(f"服务器 '{self.name}' 参数验证失败: {message}")
        
        return self


class BaseMCPServer(ABC):
    """
    MCP 服务器基类
    
    定义 MCP 服务器的基本接口
    """
    
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._tools: list[MCPTool] = []
        self._resources: list[MCPResource] = []
        self._prompts: list[MCPPrompt] = []
        self._initialized = False
        self._logger = logging.getLogger(f"foxcode.mcp.{config.name}")
    
    @property
    def name(self) -> str:
        return self.config.name
    
    @property
    def tools(self) -> list[MCPTool]:
        return self._tools
    
    @property
    def resources(self) -> list[MCPResource]:
        return self._resources
    
    @property
    def prompts(self) -> list[MCPPrompt]:
        return self._prompts
    
    @abstractmethod
    async def start(self) -> None:
        """启动服务器"""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """停止服务器"""
        pass
    
    @abstractmethod
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        """调用工具"""
        pass
    
    @abstractmethod
    async def read_resource(self, uri: str) -> str:
        """读取资源"""
        pass
    
    @abstractmethod
    async def get_prompt(self, name: str, arguments: dict[str, Any]) -> str:
        """获取提示模板"""
        pass
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """检查连接状态"""
        pass
    
    def get_tool(self, name: str) -> MCPTool | None:
        """获取工具定义"""
        for tool in self._tools:
            if tool.name == name:
                return tool
        return None
    
    def get_resource(self, uri: str) -> MCPResource | None:
        """获取资源定义"""
        for resource in self._resources:
            if resource.uri == uri:
                return resource
        return None
    
    def get_prompt_def(self, name: str) -> MCPPrompt | None:
        """获取提示模板定义"""
        for prompt in self._prompts:
            if prompt.name == name:
                return prompt
        return None


class StdioMCPServer(BaseMCPServer):
    """
    基于 stdio 的 MCP 服务器实现
    
    通过标准输入/输出与子进程通信
    """
    
    def __init__(self, config: MCPServerConfig):
        super().__init__(config)
        self._process: subprocess.Popen | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._request_id = 0
        self._pending_requests: dict[int, asyncio.Future] = {}
        self._reader_task: asyncio.Task | None = None
        self._restart_count = 0
    
    async def start(self) -> None:
        """启动服务器进程"""
        if self._process is not None:
            self._logger.warning(f"Server {self.name} already started")
            return
        
        try:
            # 安全验证：再次检查命令和参数
            if not self.config.skip_security_validation:
                is_valid, message = validate_command_security(
                    self.config.command, 
                    self.config.allowed_commands
                )
                if not is_valid:
                    raise RuntimeError(f"命令安全验证失败: {message}")
                
                is_valid, message = validate_arguments_security(self.config.args)
                if not is_valid:
                    raise RuntimeError(f"参数安全验证失败: {message}")
            
            # 准备环境变量
            env = dict(sys.environ)
            env.update(self.config.env)
            
            # 构建命令
            cmd = [self.config.command] + self.config.args
            
            self._logger.info(f"Starting MCP server: {self.name}")
            self._logger.debug(f"Command: {' '.join(cmd)}")
            
            # 创建子进程（使用 shell=False 确保安全）
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=self.config.cwd,
            )
            
            # 设置读写器
            self._reader = self._process.stdout
            self._writer = self._process.stdin
            
            # 启动读取任务
            self._reader_task = asyncio.create_task(self._read_loop())
            
            # 启动 stderr 读取任务（用于日志）
            asyncio.create_task(self._read_stderr())
            
            # 初始化连接
            await self._initialize()
            
            self._logger.info(f"MCP server {self.name} started successfully")
            
        except Exception as e:
            self._logger.error(f"Failed to start MCP server {self.name}: {e}")
            await self._cleanup()
            raise
    
    async def stop(self) -> None:
        """停止服务器进程"""
        self._logger.info(f"Stopping MCP server: {self.name}")
        
        # 取消读取任务
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        
        await self._cleanup()
        
        self._initialized = False
        self._logger.info(f"MCP server {self.name} stopped")
    
    async def _cleanup(self) -> None:
        """清理资源"""
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
        
        if self._process:
            try:
                self._process.terminate()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    self._process.kill()
                    await self._process.wait()
            except Exception:
                pass
        
        self._process = None
        self._reader = None
        self._writer = None
    
    async def _initialize(self) -> None:
        """初始化 MCP 连接"""
        # 发送 initialize 请求
        result = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
                "resources": {},
                "prompts": {},
            },
            "clientInfo": {
                "name": "foxcode",
                "version": "0.1.0",
            },
        })
        
        if "error" in result:
            raise RuntimeError(f"Initialize failed: {result['error']}")
        
        # 发送 initialized 通知
        await self._send_notification("notifications/initialized", {})
        
        # 获取工具列表
        await self._load_tools()
        
        # 获取资源列表
        await self._load_resources()
        
        # 获取提示模板列表
        await self._load_prompts()
        
        self._initialized = True
    
    async def _load_tools(self) -> None:
        """加载工具列表"""
        try:
            result = await self._send_request("tools/list", {})
            if "result" in result and "tools" in result["result"]:
                for tool_data in result["result"]["tools"]:
                    tool = MCPTool(
                        name=tool_data.get("name", ""),
                        description=tool_data.get("description", ""),
                        input_schema=tool_data.get("inputSchema", {}),
                        server_name=self.name,
                    )
                    self._tools.append(tool)
                    self._logger.debug(f"Loaded tool: {tool.name}")
        except Exception as e:
            self._logger.warning(f"Failed to load tools: {e}")
    
    async def _load_resources(self) -> None:
        """加载资源列表"""
        try:
            result = await self._send_request("resources/list", {})
            if "result" in result and "resources" in result["result"]:
                for res_data in result["result"]["resources"]:
                    resource = MCPResource(
                        uri=res_data.get("uri", ""),
                        name=res_data.get("name", ""),
                        description=res_data.get("description", ""),
                        mime_type=res_data.get("mimeType", "text/plain"),
                        server_name=self.name,
                    )
                    self._resources.append(resource)
                    self._logger.debug(f"Loaded resource: {resource.uri}")
        except Exception as e:
            self._logger.warning(f"Failed to load resources: {e}")
    
    async def _load_prompts(self) -> None:
        """加载提示模板列表"""
        try:
            result = await self._send_request("prompts/list", {})
            if "result" in result and "prompts" in result["result"]:
                for prompt_data in result["result"]["prompts"]:
                    prompt = MCPPrompt(
                        name=prompt_data.get("name", ""),
                        description=prompt_data.get("description", ""),
                        arguments=prompt_data.get("arguments", []),
                        server_name=self.name,
                    )
                    self._prompts.append(prompt)
                    self._logger.debug(f"Loaded prompt: {prompt.name}")
        except Exception as e:
            self._logger.warning(f"Failed to load prompts: {e}")
    
    async def _send_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """发送请求并等待响应"""
        if not self._writer or not self._reader:
            raise RuntimeError("Server not connected")
        
        self._request_id += 1
        request_id = self._request_id
        
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }
        
        # 创建 Future 用于等待响应
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future
        
        try:
            # 发送请求
            message = json.dumps(request) + "\n"
            self._writer.write(message.encode("utf-8"))
            await self._writer.drain()
            
            # 等待响应（超时 60 秒）
            return await asyncio.wait_for(future, timeout=60.0)
            
        except asyncio.TimeoutError:
            self._pending_requests.pop(request_id, None)
            return {"error": {"code": -1, "message": "Request timeout"}}
        except Exception as e:
            self._pending_requests.pop(request_id, None)
            return {"error": {"code": -1, "message": str(e)}}
    
    async def _send_notification(self, method: str, params: dict[str, Any]) -> None:
        """发送通知（不需要响应）"""
        if not self._writer:
            raise RuntimeError("Server not connected")
        
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        
        message = json.dumps(notification) + "\n"
        self._writer.write(message.encode("utf-8"))
        await self._writer.drain()
    
    async def _read_loop(self) -> None:
        """读取响应循环"""
        if not self._reader:
            return
        
        try:
            while True:
                line = await self._reader.readline()
                if not line:
                    break
                
                try:
                    response = json.loads(line.decode("utf-8").strip())
                    
                    # 处理响应
                    if "id" in response:
                        request_id = response["id"]
                        if request_id in self._pending_requests:
                            future = self._pending_requests.pop(request_id)
                            if not future.done():
                                future.set_result(response)
                    
                    # 处理通知
                    elif "method" in response:
                        await self._handle_notification(response)
                        
                except json.JSONDecodeError as e:
                    self._logger.warning(f"Invalid JSON response: {e}")
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._logger.error(f"Read loop error: {e}")
    
    async def _handle_notification(self, notification: dict[str, Any]) -> None:
        """处理服务器通知"""
        method = notification.get("method", "")
        params = notification.get("params", {})
        
        self._logger.debug(f"Received notification: {method}")
        
        # 处理工具列表变更
        if method == "notifications/tools/list_changed":
            self._tools.clear()
            await self._load_tools()
        
        # 处理资源列表变更
        elif method == "notifications/resources/list_changed":
            self._resources.clear()
            await self._load_resources()
        
        # 处理提示模板列表变更
        elif method == "notifications/prompts/list_changed":
            self._prompts.clear()
            await self._load_prompts()
    
    async def _read_stderr(self) -> None:
        """读取 stderr 输出"""
        if not self._process or not self._process.stderr:
            return
        
        try:
            while True:
                line = await self._process.stderr.readline()
                if not line:
                    break
                self._logger.debug(f"[{self.name} stderr] {line.decode('utf-8').strip()}")
        except Exception:
            pass
    
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        """调用工具"""
        if not self._initialized:
            raise RuntimeError("Server not initialized")
        
        result = await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments,
        })
        
        if "error" in result:
            return MCPToolResult.from_text(
                f"Tool call error: {result['error'].get('message', 'Unknown error')}",
                is_error=True,
            )
        
        if "result" in result:
            content = result["result"].get("content", [])
            is_error = result["result"].get("isError", False)
            return MCPToolResult(content=content, is_error=is_error)
        
        return MCPToolResult.from_text("Empty response", is_error=True)
    
    async def read_resource(self, uri: str) -> str:
        """读取资源"""
        if not self._initialized:
            raise RuntimeError("Server not initialized")
        
        result = await self._send_request("resources/read", {"uri": uri})
        
        if "error" in result:
            raise RuntimeError(f"Resource read error: {result['error'].get('message', 'Unknown error')}")
        
        if "result" in result and "contents" in result["result"]:
            contents = result["result"]["contents"]
            if isinstance(contents, list) and contents:
                return contents[0].get("text", "")
        
        return ""
    
    async def get_prompt(self, name: str, arguments: dict[str, Any]) -> str:
        """获取提示模板"""
        if not self._initialized:
            raise RuntimeError("Server not initialized")
        
        result = await self._send_request("prompts/get", {
            "name": name,
            "arguments": arguments,
        })
        
        if "error" in result:
            raise RuntimeError(f"Prompt get error: {result['error'].get('message', 'Unknown error')}")
        
        if "result" in result and "messages" in result["result"]:
            messages = result["result"]["messages"]
            if isinstance(messages, list) and messages:
                return messages[0].get("content", {}).get("text", "")
        
        return ""
    
    async def is_connected(self) -> bool:
        """检查连接状态"""
        return self._process is not None and self._process.returncode is None


class MCPManager:
    """
    MCP 管理器
    
    管理多个 MCP 服务器的连接和工具调用
    """
    
    def __init__(self):
        self._servers: dict[str, BaseMCPServer] = {}
        self._tool_to_server: dict[str, str] = {}
        self._resource_to_server: dict[str, str] = {}
        self._prompt_to_server: dict[str, str] = {}
        self._logger = logging.getLogger("foxcode.mcp.manager")
    
    async def add_server(self, config: MCPServerConfig) -> bool:
        """
        添加 MCP 服务器
        
        Args:
            config: 服务器配置
            
        Returns:
            是否成功添加
        """
        if config.name in self._servers:
            self._logger.warning(f"Server {config.name} already exists")
            return False
        
        try:
            server = StdioMCPServer(config)
            
            if config.auto_start:
                await server.start()
            
            self._servers[config.name] = server
            
            # 更新映射
            self._update_mappings(server)
            
            self._logger.info(f"Added MCP server: {config.name}")
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to add server {config.name}: {e}")
            return False
    
    def _update_mappings(self, server: BaseMCPServer) -> None:
        """更新工具/资源/提示到服务器的映射"""
        for tool in server.tools:
            self._tool_to_server[tool.name] = server.name
        
        for resource in server.resources:
            self._resource_to_server[resource.uri] = server.name
        
        for prompt in server.prompts:
            self._prompt_to_server[prompt.name] = server.name
    
    async def remove_server(self, name: str) -> bool:
        """
        移除 MCP 服务器
        
        Args:
            name: 服务器名称
            
        Returns:
            是否成功移除
        """
        if name not in self._servers:
            return False
        
        server = self._servers.pop(name)
        await server.stop()
        
        # 清理映射
        for tool in server.tools:
            self._tool_to_server.pop(tool.name, None)
        
        for resource in server.resources:
            self._resource_to_server.pop(resource.uri, None)
        
        for prompt in server.prompts:
            self._prompt_to_server.pop(prompt.name, None)
        
        self._logger.info(f"Removed MCP server: {name}")
        return True
    
    async def start_server(self, name: str) -> bool:
        """启动指定服务器"""
        if name not in self._servers:
            return False
        
        server = self._servers[name]
        if await server.is_connected():
            return True
        
        try:
            await server.start()
            self._update_mappings(server)
            return True
        except Exception as e:
            self._logger.error(f"Failed to start server {name}: {e}")
            return False
    
    async def stop_server(self, name: str) -> bool:
        """停止指定服务器"""
        if name not in self._servers:
            return False
        
        await self._servers[name].stop()
        return True
    
    async def stop_all(self) -> None:
        """停止所有服务器"""
        for name in list(self._servers.keys()):
            await self.stop_server(name)
    
    def get_server(self, name: str) -> BaseMCPServer | None:
        """获取服务器实例"""
        return self._servers.get(name)
    
    def list_servers(self) -> list[str]:
        """列出所有服务器名称"""
        return list(self._servers.keys())
    
    def list_tools(self) -> list[MCPTool]:
        """列出所有工具"""
        tools = []
        for server in self._servers.values():
            tools.extend(server.tools)
        return tools
    
    def list_resources(self) -> list[MCPResource]:
        """列出所有资源"""
        resources = []
        for server in self._servers.values():
            resources.extend(server.resources)
        return resources
    
    def list_prompts(self) -> list[MCPPrompt]:
        """列出所有提示模板"""
        prompts = []
        for server in self._servers.values():
            prompts.extend(server.prompts)
        return prompts
    
    def get_tool(self, name: str) -> MCPTool | None:
        """获取工具定义"""
        server_name = self._tool_to_server.get(name)
        if server_name:
            server = self._servers.get(server_name)
            if server:
                return server.get_tool(name)
        return None
    
    def get_resource(self, uri: str) -> MCPResource | None:
        """获取资源定义"""
        server_name = self._resource_to_server.get(uri)
        if server_name:
            server = self._servers.get(server_name)
            if server:
                return server.get_resource(uri)
        return None
    
    def get_prompt(self, name: str) -> MCPPrompt | None:
        """获取提示模板定义"""
        server_name = self._prompt_to_server.get(name)
        if server_name:
            server = self._servers.get(server_name)
            if server:
                return server.get_prompt_def(name)
        return None
    
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        """
        调用工具
        
        Args:
            name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果
        """
        server_name = self._tool_to_server.get(name)
        if not server_name:
            return MCPToolResult.from_text(
                f"Tool not found: {name}",
                is_error=True,
            )
        
        server = self._servers.get(server_name)
        if not server:
            return MCPToolResult.from_text(
                f"Server not found: {server_name}",
                is_error=True,
            )
        
        if not await server.is_connected():
            return MCPToolResult.from_text(
                f"Server {server_name} is not connected",
                is_error=True,
            )
        
        return await server.call_tool(name, arguments)
    
    async def read_resource(self, uri: str) -> str:
        """
        读取资源
        
        Args:
            uri: 资源 URI
            
        Returns:
            资源内容
        """
        server_name = self._resource_to_server.get(uri)
        if not server_name:
            raise ValueError(f"Resource not found: {uri}")
        
        server = self._servers.get(server_name)
        if not server:
            raise ValueError(f"Server not found: {server_name}")
        
        return await server.read_resource(uri)
    
    async def get_prompt(self, name: str, arguments: dict[str, Any] = None) -> str:
        """
        获取提示模板
        
        Args:
            name: 提示模板名称
            arguments: 参数
            
        Returns:
            提示内容
        """
        server_name = self._prompt_to_server.get(name)
        if not server_name:
            raise ValueError(f"Prompt not found: {name}")
        
        server = self._servers.get(server_name)
        if not server:
            raise ValueError(f"Server not found: {server_name}")
        
        return await server.get_prompt(name, arguments or {})
    
    def get_tools_for_prompt(self) -> str:
        """
        获取用于系统提示的工具描述
        
        Returns:
            格式化的工具描述
        """
        tools = self.list_tools()
        if not tools:
            return ""
        
        lines = ["## MCP Tools (from external servers)"]
        lines.append("")
        
        for tool in tools:
            lines.append(f"### {tool.name}")
            lines.append(f"Server: {tool.server_name}")
            lines.append(f"Description: {tool.description}")
            
            if tool.input_schema.get("properties"):
                lines.append("Parameters:")
                for param_name, param_info in tool.input_schema.get("properties", {}).items():
                    required = param_name in tool.input_schema.get("required", [])
                    req_str = " (required)" if required else ""
                    lines.append(f"  - {param_name}{req_str}: {param_info.get('description', '')}")
            lines.append("")
        
        return "\n".join(lines)


# 全局 MCP 管理器实例
mcp_manager = MCPManager()
