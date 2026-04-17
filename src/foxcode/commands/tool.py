"""
工具管理命令

用于管理和操作工具
"""

import click

from foxcode.core.config import Config
from foxcode.commands import CommandType
from foxcode.tools import registry, ToolCategory

# 命令类型
COMMAND_TYPE = CommandType.LOCAL

# 命令别名
COMMAND_ALIASES = ['t']


def register_command(cli):
    """注册工具管理命令"""
    @cli.command('tool')
    @click.option('--list', '-l', is_flag=True, help='列出所有可用工具')
    @click.option('--category', '-c', type=click.Choice([c.value for c in ToolCategory]), help='按工具类别过滤')
    @click.option('--find', '-f', help='查找匹配模式的工具')
    @click.option('--categories', '-C', is_flag=True, help='列出所有工具类别')
    def tool_command(list=False, category=None, find=None, categories=False):
        """管理和操作工具
        
        使用 --list 选项列出所有可用工具
        使用 --category 选项按工具类别过滤
        使用 --find 选项查找匹配模式的工具
        使用 --categories 选项列出所有工具类别
        """
        if list:
            # 列出所有可用工具
            if category:
                # 按工具类别过滤
                tools = registry.list_tools(ToolCategory(category))
                print(f"可用的 {category} 工具:")
            else:
                # 列出所有工具
                tools = registry.list_tools()
                print("可用的工具:")
            
            for tool in tools:
                print(f"  - {tool['name']} ({tool['category']}): {tool['description']}")
        elif find:
            # 查找匹配模式的工具
            matches = registry.find_tools(find)
            print(f"匹配 '{find}' 的工具:")
            for tool in matches:
                print(f"  - {tool['name']} ({tool['category']}): {tool['description']}")
        elif categories:
            # 列出所有工具类别
            cats = registry.get_tool_categories()
            print("可用的工具类别:")
            for cat in cats:
                print(f"  - {cat}")
        else:
            # 显示帮助信息
            print("工具管理工具")
            print("使用 --list 选项列出所有可用工具")
            print("使用 --category 选项按工具类别过滤")
            print("使用 --find 选项查找匹配模式的工具")
            print("使用 --categories 选项列出所有工具类别")


class ToolCommand:
    """工具管理命令类"""
    name = 'tool'
    description = '管理和操作工具'
    type = CommandType.LOCAL
    aliases = COMMAND_ALIASES
    enabled = True

    def __init__(self, config: Config):
        self.config = config

    def execute(self, list=False, category=None, find=None, categories=False):
        """执行工具管理命令
        
        Args:
            list: 是否列出所有可用工具
            category: 工具类别过滤
            find: 查找匹配模式的工具
            categories: 是否列出所有工具类别
            
        Returns:
            命令执行结果
        """
        if list:
            # 列出所有可用工具
            if category:
                # 按工具类别过滤
                tools = registry.list_tools(ToolCategory(category))
                result = f"可用的 {category} 工具:\n"
            else:
                # 列出所有工具
                tools = registry.list_tools()
                result = "可用的工具:\n"
            
            for tool in tools:
                result += f"  - {tool['name']} ({tool['category']}): {tool['description']}\n"
            return result
        elif find:
            # 查找匹配模式的工具
            matches = registry.find_tools(find)
            result = f"匹配 '{find}' 的工具:\n"
            for tool in matches:
                result += f"  - {tool['name']} ({tool['category']}): {tool['description']}\n"
            return result
        elif categories:
            # 列出所有工具类别
            cats = registry.get_tool_categories()
            result = "可用的工具类别:\n"
            for cat in cats:
                result += f"  - {cat}\n"
            return result
        else:
            # 显示帮助信息
            return "工具管理工具\n使用 --list 选项列出所有可用工具\n使用 --category 选项按工具类别过滤\n使用 --find 选项查找匹配模式的工具\n使用 --categories 选项列出所有工具类别"
    
    @classmethod
    def is_enabled(cls, config):
        """检查命令是否启用"""
        return cls.enabled