"""
命令模块

管理所有命令的加载和注册
"""

import importlib
import os
from typing import Dict, List, Type

from foxcode.core.config import Config


class CommandManager:
    """命令管理器"""

    def __init__(self, config: Config):
        self.config = config
        self.commands: dict[str, type] = {}
        self._loaded = False

    def load_commands(self):
        """加载所有命令"""
        if self._loaded:
            return

        # 加载内置命令
        commands_dir = os.path.dirname(__file__)

        for filename in os.listdir(commands_dir):
            if filename.endswith('.py') and not filename.startswith('_'):
                module_name = f'foxcode.commands.{filename[:-3]}'
                try:
                    module = importlib.import_module(module_name)
                    if hasattr(module, 'register_command'):
                        self.commands[filename[:-3]] = module
                except Exception as e:
                    print(f"加载命令 {filename} 失败: {e}")

        self._loaded = True

    def register_commands(self, cli):
        """注册所有命令到 CLI"""
        self.load_commands()

        for command_name, module in self.commands.items():
            if hasattr(module, 'register_command'):
                module.register_command(cli)

    def get_command(self, name: str) -> type | None:
        """获取命令类
        
        Args:
            name: 命令名称
            
        Returns:
            命令类或 None
        """
        self.load_commands()

        if name in self.commands:
            module = self.commands[name]
            if hasattr(module, f'{name.capitalize()}Command'):
                return getattr(module, f'{name.capitalize()}Command')

        return None

    def list_commands(self) -> list[str]:
        """列出所有可用命令
        
        Returns:
            命令名称列表
        """
        self.load_commands()
        return list(self.commands.keys())


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
