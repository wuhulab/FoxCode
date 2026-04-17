"""
命令模块

管理所有命令的加载和注册
"""

import importlib
import os
import sys
from typing import Dict, List, Type, Optional, Callable, Any

from foxcode.core.config import Config


class CommandType:
    """命令类型"""
    LOCAL = "local"  # 本地命令
    PROMPT = "prompt"  # 提示命令
    JSX = "jsx"  # JSX命令（如果支持）


class Command:
    """命令基类"""
    name: str
    description: str
    type: CommandType = CommandType.LOCAL
    aliases: List[str] = []
    enabled: bool = True
    
    @classmethod
    def is_enabled(cls, config: Config) -> bool:
        """检查命令是否启用"""
        return cls.enabled


class CommandManager:
    """命令管理器"""

    def __init__(self, config: Config):
        self.config = config
        self.commands: dict[str, Any] = {}  # 存储命令模块或命令类
        self._loaded = False
        self._command_types: dict[str, CommandType] = {}
        self._command_aliases: dict[str, str] = {}  # 别名到命令名的映射

    def load_commands(self):
        """加载所有命令"""
        if self._loaded:
            return

        # 加载内置命令
        self._load_builtin_commands()
        
        # 加载动态命令（基于配置）
        self._load_dynamic_commands()

        self._loaded = True

    def _load_builtin_commands(self):
        """加载内置命令"""
        commands_dir = os.path.dirname(__file__)

        for filename in os.listdir(commands_dir):
            if filename.endswith('.py') and not filename.startswith('_'):
                module_name = f'foxcode.commands.{filename[:-3]}'
                try:
                    module = importlib.import_module(module_name)
                    if hasattr(module, 'register_command'):
                        command_name = filename[:-3]
                        self.commands[command_name] = module
                        
                        # 检查命令类型
                        if hasattr(module, 'COMMAND_TYPE'):
                            self._command_types[command_name] = module.COMMAND_TYPE
                        else:
                            self._command_types[command_name] = CommandType.LOCAL
                        
                        # 检查命令别名
                        if hasattr(module, 'COMMAND_ALIASES'):
                            for alias in module.COMMAND_ALIASES:
                                self._command_aliases[alias] = command_name
                except Exception as e:
                    print(f"加载命令 {filename} 失败: {e}")

    def _load_dynamic_commands(self):
        """加载动态命令"""
        # 从配置中加载命令
        if hasattr(self.config, 'commands') and hasattr(self.config.commands, 'enabled'):
            enabled_commands = self.config.commands.enabled
            for command_name, enabled in enabled_commands.items():
                if enabled:
                    try:
                        # 尝试动态导入命令
                        module_name = f'foxcode.commands.{command_name}'
                        module = importlib.import_module(module_name)
                        if hasattr(module, 'register_command'):
                            self.commands[command_name] = module
                    except Exception as e:
                        print(f"加载动态命令 {command_name} 失败: {e}")

    def register_commands(self, cli):
        """注册所有命令到 CLI"""
        self.load_commands()

        for command_name, module in self.commands.items():
            if hasattr(module, 'register_command'):
                module.register_command(cli)

    def get_command(self, name: str) -> Optional[Any]:
        """获取命令类或模块
        
        Args:
            name: 命令名称或别名
            
        Returns:
            命令类或模块，或 None
        """
        self.load_commands()

        # 检查别名
        if name in self._command_aliases:
            name = self._command_aliases[name]

        if name in self.commands:
            module = self.commands[name]
            # 尝试获取命令类
            command_class_name = f'{name.capitalize()}Command'
            if hasattr(module, command_class_name):
                return getattr(module, command_class_name)
            return module

        return None

    def list_commands(self, command_type: Optional[CommandType] = None) -> List[str]:
        """列出所有可用命令
        
        Args:
            command_type: 命令类型过滤
            
        Returns:
            命令名称列表
        """
        self.load_commands()
        
        commands = []
        for command_name in self.commands:
            if command_type and self._command_types.get(command_name) != command_type:
                continue
            commands.append(command_name)
        
        # 按命令名称排序
        commands.sort()
        return commands

    def find_commands(self, pattern: str) -> List[str]:
        """查找匹配模式的命令
        
        Args:
            pattern: 搜索模式
            
        Returns:
            匹配的命令名称列表
        """
        self.load_commands()
        
        matches = []
        for command_name in self.commands:
            if pattern.lower() in command_name.lower():
                matches.append(command_name)
        
        # 按命令名称排序
        matches.sort()
        return matches

    def filter_commands(self, predicate: Callable[[str, Any], bool]) -> List[str]:
        """根据谓词过滤命令
        
        Args:
            predicate: 过滤谓词
            
        Returns:
            过滤后的命令名称列表
        """
        self.load_commands()
        
        filtered = []
        for command_name, module in self.commands.items():
            if predicate(command_name, module):
                filtered.append(command_name)
        
        # 按命令名称排序
        filtered.sort()
        return filtered


# 全局命令管理器实例
command_manager = None


def get_command_manager(config: Config = None) -> CommandManager:
    """获取命令管理器实例
    
    Args:
        config: 配置实例
        
    Returns:
        命令管理器实例
    """
    global command_manager

    if command_manager is None and config:
        command_manager = CommandManager(config)

    return command_manager
