"""
AI 工具模块

提供与 AI 相关的工具
"""

from typing import Any

from foxcode.tools import BaseTool, ToolParameter, ToolResult, ToolCategory, tool


@tool
class AIChatTool(BaseTool):
    """AI 聊天工具
    
    用于与 AI 模型进行对话
    """
    name = "ai_chat"
    description = "与 AI 模型进行对话"
    category = ToolCategory.AI
    parameters = [
        ToolParameter(
            name="message",
            type="string",
            description="聊天消息",
            required=True
        ),
        ToolParameter(
            name="model",
            type="string",
            description="AI 模型名称",
            required=False,
            default="gpt-4"
        ),
        ToolParameter(
            name="temperature",
            type="number",
            description="生成温度",
            required=False,
            default=0.7
        ),
    ]
    dangerous = False

    async def execute(self, message: str, model: str = "gpt-4", temperature: float = 0.7) -> ToolResult:
        """
        执行 AI 聊天
        
        Args:
            message: 聊天消息
            model: AI 模型名称
            temperature: 生成温度
            
        Returns:
            执行结果
        """
        try:
            # 这里只是一个示例，实际实现需要调用具体的 AI API
            response = f"AI 模型 {model} 回复: 你好！我收到了你的消息: {message}"
            return ToolResult(
                success=True,
                output=response
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )


@tool
class AICodeTool(BaseTool):
    """AI 代码生成工具
    
    用于生成代码
    """
    name = "ai_code"
    description = "生成代码"
    category = ToolCategory.AI
    parameters = [
        ToolParameter(
            name="prompt",
            type="string",
            description="代码生成提示",
            required=True
        ),
        ToolParameter(
            name="language",
            type="string",
            description="编程语言",
            required=False,
            default="python"
        ),
        ToolParameter(
            name="model",
            type="string",
            description="AI 模型名称",
            required=False,
            default="gpt-4"
        ),
    ]
    dangerous = False

    async def execute(self, prompt: str, language: str = "python", model: str = "gpt-4") -> ToolResult:
        """
        执行代码生成
        
        Args:
            prompt: 代码生成提示
            language: 编程语言
            model: AI 模型名称
            
        Returns:
            执行结果
        """
        try:
            # 这里只是一个示例，实际实现需要调用具体的 AI API
            response = f"AI 模型 {model} 生成的 {language} 代码: \n```python\ndef hello():\n    print('Hello, World!')\n```"
            return ToolResult(
                success=True,
                output=response
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )


@tool
class AISummarizeTool(BaseTool):
    """AI 摘要工具
    
    用于生成文本摘要
    """
    name = "ai_summarize"
    description = "生成文本摘要"
    category = ToolCategory.AI
    parameters = [
        ToolParameter(
            name="text",
            type="string",
            description="要摘要的文本",
            required=True
        ),
        ToolParameter(
            name="max_length",
            type="integer",
            description="摘要最大长度",
            required=False,
            default=150
        ),
        ToolParameter(
            name="model",
            type="string",
            description="AI 模型名称",
            required=False,
            default="gpt-4"
        ),
    ]
    dangerous = False

    async def execute(self, text: str, max_length: int = 150, model: str = "gpt-4") -> ToolResult:
        """
        执行文本摘要
        
        Args:
            text: 要摘要的文本
            max_length: 摘要最大长度
            model: AI 模型名称
            
        Returns:
            执行结果
        """
        try:
            # 这里只是一个示例，实际实现需要调用具体的 AI API
            response = f"AI 模型 {model} 生成的摘要: 这是对输入文本的摘要，长度限制为 {max_length} 个字符。"
            return ToolResult(
                success=True,
                output=response
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )