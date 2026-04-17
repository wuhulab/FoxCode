"""
命令管理命令

用于管理和操作命令
"""

import click

from foxcode.core.config import Config
from foxcode.commands import CommandType, get_command_manager

# 命令类型
COMMAND_TYPE = CommandType.LOCAL

# 命令别名
COMMAND_ALIASES = ['cmd']


def register_command(cli):
    """注册命令管理命令"""
    @cli.command('command')
    @click.option('--list', '-l', is_flag=True, help='列出所有可用命令')
    @click.option('--type', '-t', type=click.Choice(['local', 'prompt', 'jsx']), help='按命令类型过滤')
    @click.option('--find', '-f', help='查找匹配模式的命令')
    def command_command(list=False, type=None, find=None):
        """管理和操作命令
        
        使用 --list 选项列出所有可用命令
        使用 --type 选项按命令类型过滤
        使用 --find 选项查找匹配模式的命令
        """
        from foxcode.core.config import get_config
        config = get_config()
        command_manager = get_command_manager(config)
        
        if list:
            # 列出所有可用命令
            if type:
                # 按命令类型过滤
                commands = command_manager.list_commands(CommandType(type))
                print(f"可用的 {type} 命令:")
            else:
                # 列出所有命令
                commands = command_manager.list_commands()
                print("可用的命令:")
            
            for command in commands:
                print(f"  - {command}")
        elif find:
            # 查找匹配模式的命令
            matches = command_manager.find_commands(find)
            print(f"匹配 '{find}' 的命令:")
            for command in matches:
                print(f"  - {command}")
        else:
            # 显示帮助信息
            print("命令管理工具")
            print("使用 --list 选项列出所有可用命令")
            print("使用 --type 选项按命令类型过滤")
            print("使用 --find 选项查找匹配模式的命令")


class CommandCommand:
    """命令管理命令类"""
    name = 'command'
    description = '管理和操作命令'
    type = CommandType.LOCAL
    aliases = COMMAND_ALIASES
    enabled = True

    def __init__(self, config: Config):
        self.config = config

    def execute(self, list=False, type=None, find=None):
        """执行命令管理命令
        
        Args:
            list: 是否列出所有可用命令
            type: 命令类型过滤
            find: 查找匹配模式的命令
            
        Returns:
            命令执行结果
        """
        command_manager = get_command_manager(self.config)
        
        if list:
            # 列出所有可用命令
            if type:
                # 按命令类型过滤
                commands = command_manager.list_commands(CommandType(type))
                result = f"可用的 {type} 命令:\n"
            else:
                # 列出所有命令
                commands = command_manager.list_commands()
                result = "可用的命令:\n"
            
            for command in commands:
                result += f"  - {command}\n"
            return result
        elif find:
            # 查找匹配模式的命令
            matches = command_manager.find_commands(find)
            result = f"匹配 '{find}' 的命令:\n"
            for command in matches:
                result += f"  - {command}\n"
            return result
        else:
            # 显示帮助信息
            return "命令管理工具\n使用 --list 选项列出所有可用命令\n使用 --type 选项按命令类型过滤\n使用 --find 选项查找匹配模式的命令"
    
    @classmethod
    def is_enabled(cls, config):
        """检查命令是否启用"""
        return cls.enabled