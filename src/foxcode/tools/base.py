"""
FoxCode 工具系统模块 - 工具的基础架构

这个文件定义了工具系统的核心架构：
1. BaseTool: 所有工具的基类
2. ToolRegistry: 工具注册表，管理所有工具
3. ToolResult: 工具执行结果
4. ConfirmationManager: 危险操作确认管理器

工具生命周期：
定义 -> 注册 -> 获取实例 -> 验证参数 -> 执行 -> 返回结果

使用方式：
    # 定义工具
    @tool
    class MyTool(BaseTool):
        name = "my_tool"
        description = "我的工具"
        
        async def execute(self, param: str) -> ToolResult:
            # 工具逻辑
            return ToolResult(success=True, output="完成")
    
    # 使用工具
    result = await registry.execute("my_tool", param="value")

关键特性：
- 支持参数验证和类型检查
- 支持危险操作确认
- 支持工具分类和搜索
- 支持工具使用统计
"""

from __future__ import annotations

import abc
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ToolCategory(str, Enum):
    """
    工具类别 - 工具的分类标签
    
    用于组织和过滤工具，方便用户查找和管理。
    每个工具都属于一个主要类别。
    
    类别说明：
    - FILE: 文件操作（读、写、编辑、删除）
    - SHELL: Shell命令执行
    - SEARCH: 代码搜索（grep、glob等）
    - CODE: 代码分析和生成
    - WEB: 网页相关（搜索、抓取）
    - SYSTEM: 系统操作（进程、环境变量）
    - AI: AI相关功能
    - DATABASE: 数据库操作
    - NETWORK: 网络操作
    - SECURITY: 安全相关
    - TESTING: 测试相关
    """
    FILE = "file"
    SHELL = "shell"
    SEARCH = "search"
    CODE = "code"
    WEB = "web"
    SYSTEM = "system"
    AI = "ai"
    DATABASE = "database"
    NETWORK = "network"
    SECURITY = "security"
    TESTING = "testing"


class ToolParameter(BaseModel):
    """工具参数定义"""
    name: str
    type: str = "string"
    description: str = ""
    required: bool = True
    default: Any = None
    enum: list[str] | None = None


@dataclass
class ToolResult:
    """
    工具执行结果 - 统一的结果格式
    
    所有工具执行后都返回这个统一格式，方便：
    1. 判断执行是否成功
    2. 获取输出内容
    3. 处理错误信息
    4. 获取额外数据
    
    使用示例：
        # 成功结果
        result = ToolResult(
            success=True,
            output="文件已读取",
            data={"lines": 100}
        )
        
        # 失败结果
        result = ToolResult(
            success=False,
            output="",
            error="文件不存在"
        )
    """
    success: bool
    output: str
    error: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "data": self.data,
        }

    def __str__(self) -> str:
        """字符串表示：成功显示输出，失败显示错误"""
        if self.success:
            return self.output
        return f"错误: {self.error}\n{self.output}"


@dataclass
class ConfirmationRequest:
    """
    操作确认请求
    
    用于危险操作前的用户确认
    """
    tool_name: str
    operation: str
    details: dict[str, Any]
    risk_level: str  # low, medium, high, critical
    message: str
    requires_confirmation: bool = True


class ConfirmationManager:
    """
    操作确认管理器
    
    管理危险操作的确认流程
    """

    HIGH_RISK_OPERATIONS = {
        "delete_file": "critical",
        "write_file": "medium",
        "edit_file": "medium",
        "shell_execute": "high",
        "stop_command": "medium",
    }

    HIGH_RISK_PATTERNS = {
        "delete_file": {
            "recursive": {"risk": "critical", "message": "递归删除操作将删除目录及其所有内容"},
        },
        "shell_execute": {
            "async_mode": {"risk": "medium", "message": "异步命令将在后台执行"},
        },
    }

    def __init__(self, auto_confirm: bool = False, yolo_mode: bool = False):
        """
        初始化确认管理器
        
        Args:
            auto_confirm: 是否自动确认所有操作
            yolo_mode: YOLO 模式（自动执行所有操作）
        """
        self.auto_confirm = auto_confirm
        self.yolo_mode = yolo_mode
        self._pending_confirmations: dict[str, ConfirmationRequest] = {}
        self._confirmation_callbacks: list[Callable[[ConfirmationRequest], bool]] = []

    def add_confirmation_callback(self, callback: Callable[[ConfirmationRequest], bool]) -> None:
        """
        添加确认回调函数
        
        Args:
            callback: 回调函数，返回 True 表示确认，False 表示拒绝
        """
        self._confirmation_callbacks.append(callback)

    def needs_confirmation(
        self,
        tool_name: str,
        params: dict[str, Any],
        is_dangerous: bool,
    ) -> ConfirmationRequest | None:
        """
        检查操作是否需要确认
        
        Args:
            tool_name: 工具名称
            params: 操作参数
            is_dangerous: 工具是否标记为危险
            
        Returns:
            确认请求，如果不需要确认则返回 None
        """
        if self.yolo_mode:
            return None

        risk_level = self.HIGH_RISK_OPERATIONS.get(tool_name, "low")

        if not is_dangerous and risk_level == "low":
            return None

        patterns = self.HIGH_RISK_PATTERNS.get(tool_name, {})
        for param_name, param_config in patterns.items():
            if params.get(param_name):
                risk_level = max(risk_level, param_config["risk"], key=lambda x: ["low", "medium", "high", "critical"].index(x))

        operation_desc = self._build_operation_description(tool_name, params)

        message = f"即将执行危险操作: {operation_desc}"
        if risk_level == "critical":
            message += "\n⚠️ 警告: 此操作不可逆，请谨慎确认！"
        elif risk_level == "high":
            message += "\n⚠️ 注意: 此操作可能影响系统安全！"

        return ConfirmationRequest(
            tool_name=tool_name,
            operation=operation_desc,
            details=params,
            risk_level=risk_level,
            message=message,
            requires_confirmation=not self.auto_confirm,
        )

    def confirm(self, request: ConfirmationRequest) -> bool:
        """
        执行确认流程
        
        Args:
            request: 确认请求
            
        Returns:
            是否确认执行
        """
        if self.auto_confirm or self.yolo_mode:
            logger.info(f"自动确认操作: {request.tool_name} - {request.operation}")
            return True

        for callback in self._confirmation_callbacks:
            try:
                if callback(request):
                    logger.info(f"用户确认操作: {request.tool_name} - {request.operation}")
                    return True
                else:
                    logger.info(f"用户拒绝操作: {request.tool_name} - {request.operation}")
                    return False
            except Exception as e:
                logger.error(f"确认回调执行失败: {e}")

        logger.warning(f"没有确认回调，默认拒绝危险操作: {request.tool_name}")
        return False

    def _build_operation_description(self, tool_name: str, params: dict[str, Any]) -> str:
        """
        构建操作描述
        
        Args:
            tool_name: 工具名称
            params: 操作参数
            
        Returns:
            操作描述字符串
        """
        if tool_name == "delete_file":
            path = params.get("file_path", "未知路径")
            recursive = params.get("recursive", False)
            return f"删除 {'目录' if recursive else '文件'}: {path}"

        elif tool_name == "write_file":
            path = params.get("file_path", "未知路径")
            size = len(params.get("content", ""))
            return f"写入文件: {path} ({size} 字符)"

        elif tool_name == "edit_file":
            path = params.get("file_path", "未知路径")
            return f"编辑文件: {path}"

        elif tool_name == "shell_execute":
            command = params.get("command", "未知命令")[:50]
            return f"执行命令: {command}"

        elif tool_name == "stop_command":
            cmd_id = params.get("command_id", "未知")
            return f"停止命令: {cmd_id}"

        else:
            return f"执行 {tool_name}"


_confirmation_manager: ConfirmationManager | None = None


def get_confirmation_manager() -> ConfirmationManager:
    """
    获取全局确认管理器实例
    
    Returns:
        ConfirmationManager 实例
    """
    global _confirmation_manager
    if _confirmation_manager is None:
        _confirmation_manager = ConfirmationManager()
    return _confirmation_manager


def set_confirmation_manager(manager: ConfirmationManager) -> None:
    """
    设置全局确认管理器实例
    
    Args:
        manager: ConfirmationManager 实例
    """
    global _confirmation_manager
    _confirmation_manager = manager


class BaseTool(abc.ABC):
    """
    工具基类 - 所有工具的父类
    
    这是工具系统的核心，定义了工具的基本结构：
    1. 工具名称和描述
    2. 工具类别
    3. 参数定义
    4. 执行方法
    
    工具开发流程：
    1. 继承BaseTool
    2. 定义name、description、category、parameters
    3. 实现execute方法
    4. 使用@tool装饰器注册
    
    使用示例：
        @tool
        class ReadFileTool(BaseTool):
            name = "read_file"
            description = "读取文件内容"
            category = ToolCategory.FILE
            parameters = [
                ToolParameter(name="file_path", type="string", required=True)
            ]
            
            async def execute(self, file_path: str) -> ToolResult:
                try:
                    with open(file_path) as f:
                        content = f.read()
                    return ToolResult(success=True, output=content)
                except Exception as e:
                    return ToolResult(success=False, output="", error=str(e))
    
    安全特性：
    - 参数验证：自动验证参数类型和必需性
    - 危险标记：dangerous=True的工具需要确认
    - 错误处理：统一捕获异常并返回错误结果
    """

    name: str = "base_tool"
    description: str = "基础工具"
    category: ToolCategory = ToolCategory.SYSTEM
    parameters: list[ToolParameter] = []
    dangerous: bool = False  # 是否为危险操作（需要用户确认）

    def __init__(self, config: Any = None):
        self.config = config
        self._logger = logging.getLogger(f"foxcode.tools.{self.name}")

    @abc.abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        执行工具 - 子类必须实现此方法
        
        这是工具的核心方法，实现具体的工具逻辑。
        
        Args:
            **kwargs: 工具参数，已通过验证
            
        Returns:
            ToolResult: 执行结果
            
        注意：
        - 参数已经过验证，可以直接使用
        - 应该捕获所有异常并返回错误结果
        - 成功时返回success=True
        - 失败时返回success=False和error信息
        """
        pass

    def get_schema(self) -> dict[str, Any]:
        """
        获取工具的 JSON Schema
        
        Returns:
            工具定义的 JSON Schema
        """
        properties = {}
        required = []

        for param in self.parameters:
            prop = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            if param.default is not None:
                prop["default"] = param.default

            properties[param.name] = prop
            if param.required:
                required.append(param.name)

        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }

    def validate_parameters(self, **kwargs: Any) -> dict[str, Any]:
        """
        验证参数（增强版）
        
        使用 Pydantic 进行严格验证，包括：
        - 类型检查
        - 必需参数检查
        - 枚举值检查
        - 大小/长度限制
        - 安全检查
        
        Args:
            **kwargs: 输入参数
            
        Returns:
            验证后的参数
            
        Raises:
            ValueError: 参数验证失败
        """
        validated = {}

        for param in self.parameters:
            value = kwargs.get(param.name, param.default)

            if param.required and value is None:
                raise ValueError(f"缺少必需参数: {param.name}")

            if value is None:
                validated[param.name] = None
                continue

            if param.enum and value not in param.enum:
                raise ValueError(
                    f"参数 {param.name} 的值必须是 {param.enum} 之一，得到: {value}"
                )

            validated_value = self._validate_parameter_value(param, value)
            validated[param.name] = validated_value

        return validated

    def _validate_parameter_value(self, param: ToolParameter, value: Any) -> Any:
        """
        验证单个参数值
        
        Args:
            param: 参数定义
            value: 参数值
            
        Returns:
            验证后的值
            
        Raises:
            ValueError: 验证失败
        """
        if value is None:
            return None

        if param.type == "string":
            if not isinstance(value, str):
                try:
                    value = str(value)
                except Exception:
                    raise ValueError(f"参数 {param.name} 必须是字符串类型")

            max_length = getattr(param, 'max_length', 100000)
            if len(value) > max_length:
                raise ValueError(f"参数 {param.name} 长度超过限制 ({len(value)} > {max_length})")

            if param.name in ('file_path', 'path', 'directory'):
                if '..' in value:
                    raise ValueError(f"参数 {param.name} 包含非法路径穿越字符")
                if '\x00' in value:
                    raise ValueError(f"参数 {param.name} 包含非法空字节")

            if param.name in ('command', 'cmd'):
                dangerous_patterns = [
                    '$((', '`', '${', '$(',
                    '||', '&&', ';',
                    '$IFS', '$(printf', '$(eval',
                    'base64', 'xxd', 'od',
                ]
                for pattern in dangerous_patterns:
                    if pattern in value:
                        raise ValueError(
                            f"参数 {param.name} 包含危险的命令模式 '{pattern}'，已拒绝执行"
                        )

        elif param.type == "integer":
            if not isinstance(value, int):
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    raise ValueError(f"参数 {param.name} 必须是整数类型")

            min_val = getattr(param, 'min_value', None)
            max_val = getattr(param, 'max_value', None)

            if min_val is not None and value < min_val:
                raise ValueError(f"参数 {param.name} 值 {value} 小于最小值 {min_val}")
            if max_val is not None and value > max_val:
                raise ValueError(f"参数 {param.name} 值 {value} 大于最大值 {max_val}")

        elif param.type == "number":
            if not isinstance(value, (int, float)):
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    raise ValueError(f"参数 {param.name} 必须是数字类型")

        elif param.type == "boolean":
            if not isinstance(value, bool):
                if isinstance(value, str):
                    if value.lower() in ('true', '1', 'yes'):
                        value = True
                    elif value.lower() in ('false', '0', 'no'):
                        value = False
                    else:
                        raise ValueError(f"参数 {param.name} 必须是布尔类型")
                else:
                    value = bool(value)

        elif param.type == "array":
            if not isinstance(value, list):
                if isinstance(value, (tuple, set)):
                    value = list(value)
                else:
                    raise ValueError(f"参数 {param.name} 必须是数组类型")

            max_items = getattr(param, 'max_items', 1000)
            if len(value) > max_items:
                raise ValueError(f"参数 {param.name} 数组长度超过限制 ({len(value)} > {max_items})")

        elif param.type == "object":
            if not isinstance(value, dict):
                raise ValueError(f"参数 {param.name} 必须是对象类型")

        return value


class ToolRegistry:
    """
    工具注册表 - 管理所有可用工具
    
    这是工具系统的中心，负责：
    1. 注册工具类
    2. 创建工具实例
    3. 执行工具
    4. 列出和搜索工具
    
    工具注册流程：
    定义工具 -> @tool装饰器 -> 注册到registry -> 可以使用
    
    使用示例：
        # 注册工具
        @tool
        class MyTool(BaseTool):
            ...
        
        # 获取工具实例
        tool = registry.get_tool("my_tool")
        
        # 执行工具
        result = await registry.execute("my_tool", param="value")
        
        # 列出所有工具
        tools = registry.list_tools()
    
    懒加载机制：
    - 工具类注册后不会立即创建实例
    - 第一次使用时才创建实例
    - 节省内存和启动时间
    """

    def __init__(self):
        self._tools: dict[str, type[BaseTool]] = {}  # 工具类注册表
        self._instances: dict[str, BaseTool] = {}  # 工具实例缓存
        self._config: Any = None
        self._loaded_modules: set[str] = set()  # 已加载的模块

    def register(self, tool_class: type[BaseTool]) -> type[BaseTool]:
        """
        注册工具类
        
        Args:
            tool_class: 工具类
            
        Returns:
            工具类（支持装饰器用法）
            
        使用示例：
            # 装饰器方式
            @tool
            class MyTool(BaseTool):
                ...
            
            # 直接调用
            registry.register(MyTool)
        """
        self._tools[tool_class.name] = tool_class
        logger.debug(f"注册工具: {tool_class.name}")
        return tool_class

    def set_config(self, config: Any) -> None:
        """设置配置"""
        self._config = config
        
    def load_tools_from_module(self, module_name: str) -> None:
        """
        从模块中加载工具
        
        Args:
            module_name: 模块名称
        """
        if module_name in self._loaded_modules:
            return
        
        try:
            module = __import__(module_name, fromlist=['*'])
            self._loaded_modules.add(module_name)
            logger.debug(f"从模块 {module_name} 加载工具")
        except ImportError as e:
            logger.warning(f"加载模块 {module_name} 失败: {e}")
        
    def load_tools_from_config(self) -> None:
        """
        从配置中加载工具
        """
        if not self._config:
            return
        
        # 从配置中获取要加载的工具模块
        if hasattr(self._config, 'tools') and hasattr(self._config.tools, 'modules'):
            modules = self._config.tools.modules
            for module_name in modules:
                self.load_tools_from_module(module_name)
        
        # 从配置中获取要启用的工具
        if hasattr(self._config, 'tools') and hasattr(self._config.tools, 'enabled'):
            enabled_tools = self._config.tools.enabled
            # 这里可以根据配置启用或禁用工具
            logger.debug(f"从配置中加载工具: {enabled_tools}")

    def get_tool(self, name: str) -> BaseTool:
        """
        获取工具实例
        
        Args:
            name: 工具名称
            
        Returns:
            工具实例
        """
        # 尝试从配置中加载工具
        self.load_tools_from_config()
        
        if name not in self._tools:
            # 尝试动态加载工具模块
            try:
                # 假设工具模块名称为 foxcode.tools.{name}_tools
                module_name = f"foxcode.tools.{name}_tools"
                self.load_tools_from_module(module_name)
            except Exception as e:
                logger.debug(f"动态加载工具模块失败: {e}")
        
        if name not in self._tools:
            raise KeyError(f"工具不存在: {name}")

        if name not in self._instances:
            self._instances[name] = self._tools[name](self._config)

        return self._instances[name]

    def list_tools(self, category: ToolCategory | None = None) -> list[dict[str, Any]]:
        """
        列出所有工具
        
        Args:
            category: 工具类别过滤
            
        Returns:
            工具信息列表
        """
        # 尝试从配置中加载工具
        self.load_tools_from_config()
        
        tools = []
        for name, cls in self._tools.items():
            if category and cls.category != category:
                continue
            tools.append({
                "name": name,
                "description": cls.description,
                "category": cls.category.value,
                "dangerous": cls.dangerous,
            })
        # 按工具名称排序
        tools.sort(key=lambda x: x["name"])
        return tools
    
    def find_tools(self, pattern: str) -> list[dict[str, Any]]:
        """
        查找匹配模式的工具
        
        Args:
            pattern: 搜索模式
            
        Returns:
            匹配的工具信息列表
        """
        # 尝试从配置中加载工具
        self.load_tools_from_config()
        
        matches = []
        for name, cls in self._tools.items():
            if pattern.lower() in name.lower() or pattern.lower() in cls.description.lower():
                matches.append({
                    "name": name,
                    "description": cls.description,
                    "category": cls.category.value,
                    "dangerous": cls.dangerous,
                })
        # 按工具名称排序
        matches.sort(key=lambda x: x["name"])
        return matches
    
    def get_tools_by_category(self, category: ToolCategory) -> list[dict[str, Any]]:
        """
        按类别获取工具
        
        Args:
            category: 工具类别
            
        Returns:
            该类别下的工具信息列表
        """
        # 尝试从配置中加载工具
        self.load_tools_from_config()
        return self.list_tools(category)
    
    def get_tool_categories(self) -> list[str]:
        """
        获取所有工具类别
        
        Returns:
            工具类别列表
        """
        # 尝试从配置中加载工具
        self.load_tools_from_config()
        
        categories = set()
        for cls in self._tools.values():
            categories.add(cls.category.value)
        return sorted(list(categories))

    def get_schemas(self) -> list[dict[str, Any]]:
        """
        获取所有工具的 Schema
        
        Returns:
            工具 Schema 列表
        """
        # 尝试从配置中加载工具
        self.load_tools_from_config()
        
        return [
            self.get_tool(name).get_schema()
            for name in self._tools
        ]

    async def execute(self, name: str, **kwargs: Any) -> ToolResult:
        """
        执行工具 - 工具执行的主入口
        
        执行流程：
        1. 获取工具实例
        2. 验证参数
        3. 执行工具
        4. 记录统计
        5. 返回结果
        
        Args:
            name: 工具名称
            **kwargs: 工具参数
            
        Returns:
            ToolResult: 执行结果
            
        异常处理：
        - 参数验证失败：返回错误结果
        - 工具执行异常：捕获并返回错误结果
        - 工具不存在：抛出KeyError
        """
        # 确保工具已加载
        self.load_tools_from_config()
        
        tool = self.get_tool(name)
        start_time = time.time()
        error_msg = None

        try:
            # 验证参数
            validated_params = tool.validate_parameters(**kwargs)
            
            # 执行工具
            result = await tool.execute(**validated_params)

            duration = time.time() - start_time

            if result.success:
                logger.info(f"工具 {name} 执行成功，耗时 {duration:.2f}s")
            else:
                logger.warning(f"工具 {name} 执行失败: {result.error}")
                error_msg = result.error

            # 记录统计信息
            self._record_tool_usage(
                tool_name=name,
                success=result.success,
                duration=duration,
                error=error_msg,
                params=validated_params,
                result_size=len(result.output),
            )

            return result
        except Exception as e:
            # 捕获所有异常，返回错误结果
            duration = time.time() - start_time
            logger.error(f"工具 {name} 执行异常: {e}")

            # 记录失败统计
            self._record_tool_usage(
                tool_name=name,
                success=False,
                duration=duration,
                error=str(e),
                params=kwargs,
            )

            return ToolResult(
                success=False,
                output="",
                error=str(e),
            )

    def _record_tool_usage(
        self,
        tool_name: str,
        success: bool,
        duration: float,
        error: str | None = None,
        params: dict[str, Any] | None = None,
        result_size: int = 0,
    ) -> None:
        """
        记录工具使用统计
        
        Args:
            tool_name: 工具名称
            success: 是否成功
            duration: 执行时长
            error: 错误信息
            params: 参数
            result_size: 结果大小
        """
        try:
            from foxcode.core.statistics import stats_manager
            stats_manager.record_tool_usage(
                tool_name=tool_name,
                success=success,
                duration=duration,
                error=error,
                params=params,
                result_size=result_size,
            )
        except ImportError:
            pass  # 统计模块不可用时忽略


# 全局工具注册表
registry = ToolRegistry()


def tool(cls: type[BaseTool]) -> type[BaseTool]:
    """
    工具注册装饰器
    
    用法:
        @tool
        class MyTool(BaseTool):
            ...
    """
    return registry.register(cls)
