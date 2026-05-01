"""
FoxCode 命令管理模块 - 命令行命令的管理和调度

这个文件实现了FoxCode的命令系统：
1. 命令注册：注册新的命令行命令
2. 命令发现：自动发现可用的命令
3. 命令调度：根据用户输入调度到对应的命令处理器
4. 命令别名：支持命令的短名称

命令类型：
- LOCAL: 本地命令，在本地执行
- PROMPT: 提示词命令，生成提示词
- JSX: JSX命令，生成JSX代码

使用方式：
    # 命令行使用
    foxcode command --list          # 列出所有命令
    foxcode command --type local    # 列出本地命令
    foxcode command --find test     # 查找包含test的命令

命令开发：
    1. 定义命令类
    2. 实现execute方法
    3. 注册到命令管理器
    
    class MyCommand:
        name = 'my_command'
        description = '我的命令'
        
        def execute(self, *args):
            # 命令逻辑
            return "执行完成"

关键特性：
- 支持命令别名
- 支持命令过滤和搜索
- 支持多种命令类型
- 自动命令发现
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