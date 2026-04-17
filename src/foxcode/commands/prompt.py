"""
提示命令

用于生成提示模板
"""

import click

from foxcode.core.config import Config
from foxcode.commands import CommandType

# 命令类型
COMMAND_TYPE = CommandType.PROMPT

# 命令别名
COMMAND_ALIASES = ['p']


def register_command(cli):
    """注册提示命令"""
    @cli.command('prompt')
    @click.argument('template', required=False)
    @click.option('--list', '-l', is_flag=True, help='列出可用的提示模板')
    def prompt_command(template=None, list=False):
        """生成提示模板
        
        如果指定了模板名称，则生成该模板的提示
        如果使用 --list 选项，则列出所有可用的提示模板
        否则显示默认提示模板
        """
        if list:
            # 列出可用的提示模板
            print("可用的提示模板:")
            print("  default - 默认提示模板")
            print("  code - 代码生成提示模板")
            print("  debug - 调试提示模板")
        elif template:
            # 生成指定模板的提示
            prompt = generate_prompt(template)
            print(f"生成的提示模板 '{template}':")
            print(prompt)
        else:
            # 显示默认提示模板
            prompt = generate_prompt('default')
            print("默认提示模板:")
            print(prompt)


def generate_prompt(template):
    """生成提示模板
    
    Args:
        template: 模板名称
        
    Returns:
        提示模板内容
    """
    templates = {
        'default': "请帮我解决以下问题:\n\n{problem}",
        'code': "请帮我编写以下代码:\n\n{description}\n\n要求:\n- 代码要简洁明了\n- 要有适当的注释\n- 要处理边界情况",
        'debug': "请帮我调试以下代码:\n\n{code}\n\n问题:\n{problem}\n\n请分析问题并提供解决方案",
    }
    
    return templates.get(template, templates['default'])


class PromptCommand:
    """提示命令类"""
    name = 'prompt'
    description = '生成提示模板'
    type = CommandType.PROMPT
    aliases = COMMAND_ALIASES
    enabled = True

    def __init__(self, config: Config):
        self.config = config

    def execute(self, template=None, list=False):
        """执行提示命令
        
        Args:
            template: 模板名称（可选）
            list: 是否列出可用的提示模板
            
        Returns:
            提示模板内容
        """
        if list:
            # 列出可用的提示模板
            return "可用的提示模板:\n  default - 默认提示模板\n  code - 代码生成提示模板\n  debug - 调试提示模板"
        elif template:
            # 生成指定模板的提示
            prompt = generate_prompt(template)
            return f"生成的提示模板 '{template}':\n{prompt}"
        else:
            # 显示默认提示模板
            prompt = generate_prompt('default')
            return f"默认提示模板:\n{prompt}"
    
    @classmethod
    def is_enabled(cls, config):
        """检查命令是否启用"""
        return cls.enabled