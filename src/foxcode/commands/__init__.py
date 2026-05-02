"""
命令模块 - 管理所有命令的加载、注册和调度

这个文件提供 FoxCode 的命令系统基础设施:
1. CommandType: 命令类型枚举（LOCAL/PROMPT/JSX）
2. Command: 命令基类，所有命令需继承此类
3. CommandManager: 命令管理器，负责加载、注册、查找命令

使用方式:
    from foxcode.commands import get_command_manager, CommandType
    from foxcode.core.config import get_config

    # 获取命令管理器
    config = get_config()
    manager = get_command_manager(config)

    # 列出所有命令
    commands = manager.list_commands()

    # 查找命令
    matches = manager.find_commands("help")

    # 按类型过滤
    local_commands = manager.list_commands(CommandType.LOCAL)
"""

import importlib
import os
import sys
from typing import Dict, List, Type, Optional, Callable, Any

from foxcode.core.config import Config


class CommandType:
    """命令类型 - 区分不同执行方式的命令"""
    LOCAL = "local"      # 本地命令：在本地直接执行
    PROMPT = "prompt"    # 提示命令：生成提示词模板
    JSX = "jsx"          # JSX命令：生成JSX代码


class Command:
    """
    命令基类 - 所有命令的模板

    子类需要定义:
    - name: 命令名称
    - description: 命令描述
    - type: 命令类型（默认 LOCAL）
    - aliases: 命令别名列表
    - enabled: 是否启用
    """
    name: str
    description: str
    type: CommandType = CommandType.LOCAL
    aliases: List[str] = []
    enabled: bool = True

    @classmethod
    def is_enabled(cls, config: Config) -> bool:
        """检查命令是否启用 - 子类可覆写此方法实现动态启用/禁用"""
        return cls.enabled


class CommandManager:
    """
    命令管理器 - 负责命令的加载、注册、查找和过滤

    核心功能:
    - load_commands(): 加载所有内置和动态命令
    - register_commands(cli): 将命令注册到 CLI 框架
    - get_command(name): 按名称或别名获取命令
    - list_commands(type): 列出所有命令，可按类型过滤
    - find_commands(pattern): 按关键词搜索命令

    使用方式:
        manager = CommandManager(config)
        manager.load_commands()
        commands = manager.list_commands()
    """

    def __init__(self, config: Config):
        self.config = config
        self.commands: dict[str, Any] = {}  # 命令名 -> 命令模块或命令类
        self._loaded = False  # 是否已完成加载，防止重复加载
        self._command_types: dict[str, CommandType] = {}  # 命令名 -> 命令类型
        self._command_aliases: dict[str, str] = {}  # 别名 -> 命令名的映射

    def load_commands(self):
        """加载所有命令 - 先加载内置命令，再加载动态命令"""
        # 已加载过则跳过，避免重复加载
        if self._loaded:
            return

        # 加载内置命令
        self._load_builtin_commands()

        # 加载动态命令（基于配置）
        self._load_dynamic_commands()

        self._loaded = True

    def _load_builtin_commands(self):
        """
        加载内置命令 - 扫描 commands 目录下的所有 .py 文件

        自动发现规则:
        - 跳过以 _ 开头的文件（如 __init__.py）
        - 模块必须定义 register_command 函数才会被注册
        - 可选定义 COMMAND_TYPE 和 COMMAND_ALIASES
        """
        commands_dir = os.path.dirname(__file__)

        for filename in os.listdir(commands_dir):
            # 跳过非 Python 文件和私有文件
            if filename.endswith('.py') and not filename.startswith('_'):
                module_name = f'foxcode.commands.{filename[:-3]}'
                try:
                    module = importlib.import_module(module_name)

                    # 只注册有 register_command 函数的模块
                    if hasattr(module, 'register_command'):
                        command_name = filename[:-3]
                        self.commands[command_name] = module

                        # 记录命令类型，未定义则默认为 LOCAL
                        if hasattr(module, 'COMMAND_TYPE'):
                            self._command_types[command_name] = module.COMMAND_TYPE
                        else:
                            self._command_types[command_name] = CommandType.LOCAL

                        # 注册命令别名
                        if hasattr(module, 'COMMAND_ALIASES'):
                            for alias in module.COMMAND_ALIASES:
                                self._command_aliases[alias] = command_name
                except Exception as e:
                    # 加载失败不中断，打印错误继续加载其他命令
                    print(f"加载命令 {filename} 失败: {e}")

    def _load_dynamic_commands(self):
        """
        加载动态命令 - 从配置中读取需要启用的命令

        配置格式:
        config.commands.enabled = {"command_name": True/False}
        """
        if hasattr(self.config, 'commands') and hasattr(self.config.commands, 'enabled'):
            enabled_commands = self.config.commands.enabled
            for command_name, enabled in enabled_commands.items():
                # 只加载配置中启用的命令
                if not enabled:
                    continue
                try:
                    module_name = f'foxcode.commands.{command_name}'
                    module = importlib.import_module(module_name)
                    if hasattr(module, 'register_command'):
                        self.commands[command_name] = module
                except Exception as e:
                    print(f"加载动态命令 {command_name} 失败: {e}")

    def register_commands(self, cli):
        """
        注册所有命令到 CLI 框架

        Args:
            cli: Click CLI 实例
        """
        self.load_commands()

        for command_name, module in self.commands.items():
            if hasattr(module, 'register_command'):
                module.register_command(cli)

    def get_command(self, name: str) -> Optional[Any]:
        """
        获取命令 - 支持通过别名查找

        Args:
            name: 命令名称或别名

        Returns:
            命令类或模块，找不到返回 None
        """
        self.load_commands()

        # 先查别名映射表
        if name in self._command_aliases:
            name = self._command_aliases[name]

        if name in self.commands:
            module = self.commands[name]
            # 尝试获取命令类（如 HelpCommand、ToolCommand）
            command_class_name = f'{name.capitalize()}Command'
            if hasattr(module, command_class_name):
                return getattr(module, command_class_name)
            return module

        return None

    def list_commands(self, command_type: Optional[CommandType] = None) -> List[str]:
        """
        列出所有可用命令 - 可按类型过滤

        Args:
            command_type: 命令类型过滤，None 表示列出全部

        Returns:
            排序后的命令名称列表
        """
        self.load_commands()

        commands = []
        for command_name in self.commands:
            # 按类型过滤
            if command_type and self._command_types.get(command_name) != command_type:
                continue
            commands.append(command_name)

        commands.sort()
        return commands

    def find_commands(self, pattern: str) -> List[str]:
        """
        查找匹配模式的命令 - 不区分大小写的模糊搜索

        Args:
            pattern: 搜索关键词

        Returns:
            匹配的命令名称列表
        """
        self.load_commands()

        # 不区分大小写的模糊匹配
        matches = [
            command_name
            for command_name in self.commands
            if pattern.lower() in command_name.lower()
        ]

        matches.sort()
        return matches

    def filter_commands(self, predicate: Callable[[str, Any], bool]) -> List[str]:
        """
        根据谓词过滤命令 - 支持自定义过滤逻辑

        Args:
            predicate: 过滤函数，接收 (命令名, 模块) 返回 bool

        Returns:
            过滤后的命令名称列表
        """
        self.load_commands()

        filtered = [
            command_name
            for command_name, module in self.commands.items()
            if predicate(command_name, module)
        ]

        filtered.sort()
        return filtered


# 全局命令管理器实例 - 单例模式，整个程序共享一个
command_manager = None


def get_command_manager(config: Config = None) -> CommandManager:
    """
    获取命令管理器实例 - 延迟初始化的单例模式

    首次调用时需要传入 config，后续调用无需再传。

    Args:
        config: 配置实例（仅首次调用时需要）

    Returns:
        命令管理器实例
    """
    global command_manager

    if command_manager is None and config:
        command_manager = CommandManager(config)

    return command_manager
