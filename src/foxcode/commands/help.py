"""
帮助命令 - 显示可用命令和使用说明

这个文件提供 FoxCode 的帮助系统:
1. 列出所有可用命令
2. 显示指定命令的详细帮助

命令类型: LOCAL（本地命令）
命令别名: h, ?

使用方式:
    foxcode help           # 显示所有命令
    foxcode help command   # 显示 command 命令的详细帮助
    foxcode h              # 使用别名
"""

import click

from foxcode.core.config import Config
from foxcode.commands import CommandType

# 命令类型
COMMAND_TYPE = CommandType.LOCAL

# 命令别名
COMMAND_ALIASES = ['h', '?']


def register_command(cli):
    """注册帮助命令"""
    @cli.command('help')
    @click.argument('command', required=False)
    def help_command(command=None):
        """显示帮助信息
        
        如果指定了命令，则显示该命令的详细帮助信息
        否则显示所有可用命令的列表
        """
        if command:
            # 显示指定命令的帮助
            cmd = cli.get_command(None, command)
            if cmd:
                cmd.get_help(None)
            else:
                print(f"命令 '{command}' 不存在")
        else:
            # 显示所有命令的帮助
            cli.get_help(None)


class HelpCommand:
    """帮助命令类"""
    name = 'help'
    description = '显示帮助信息'
    type = CommandType.LOCAL
    aliases = COMMAND_ALIASES
    enabled = True

    def __init__(self, config: Config):
        self.config = config

    def execute(self, command=None):
        """执行帮助命令
        
        Args:
            command: 命令名称（可选）
            
        Returns:
            帮助信息
        """
        from foxcode.cli import cli

        if command:
            cmd = cli.get_command(None, command)
            if cmd:
                return cmd.get_help(None)
            else:
                return f"命令 '{command}' 不存在"
        else:
            return cli.get_help(None)
    
    @classmethod
    def is_enabled(cls, config):
        """检查命令是否启用"""
        return cls.enabled
