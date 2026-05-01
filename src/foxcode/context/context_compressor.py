"""
FoxCode 上下文智能压缩器 - 减少token使用，保留关键信息

这个文件提供对话历史和代码上下文的智能压缩功能：
1. 对话压缩：将长对话压缩为简短摘要
2. 代码压缩：提取代码的关键信息
3. 知识蒸馏：从对话中提取关键知识点
4. Token估算：估算压缩前后的token数

为什么需要上下文压缩？
上下文窗口有限，长对话会消耗大量token：
- 成本：token越多，API调用越贵
- 性能：上下文越长，响应越慢
- 限制：模型有最大上下文长度限制

压缩策略：
- LOW: 保留大部分细节，压缩比低
- MEDIUM: 平衡细节和压缩比
- HIGH: 只保留关键信息
- AGGRESSIVE: 最大压缩，只保留核心要点

使用方式：
    from foxcode.context.context_compressor import ContextCompressor
    
    compressor = ContextCompressor()
    
    # 压缩对话
    compressed = compressor.compress_conversation(
        messages=conversation_history,
        level=CompressionLevel.MEDIUM
    )
    
    print(f"压缩比: {compressed.compression_ratio}")
    print(f"摘要: {compressed.summary}")

关键特性：
- 智能提取关键信息
- 保留重要实体（函数名、类名）
- 支持多种压缩级别
- Token使用估算
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CompressionLevel(str, Enum):
    """压缩级别"""
    LOW = "low"          # 低压缩，保留更多细节
    MEDIUM = "medium"    # 中等压缩
    HIGH = "high"        # 高压缩，只保留关键信息
    AGGRESSIVE = "aggressive"  # 激进压缩


class ContentType(str, Enum):
    """内容类型"""
    CONVERSATION = "conversation"  # 对话
    CODE = "code"                  # 代码
    DOCUMENTATION = "documentation"  # 文档
    ERROR = "error"                # 错误信息
    COMMAND = "command"            # 命令输出


@dataclass
class CompressedContext:
    """
    压缩后的上下文
    
    Attributes:
        summary: 压缩后的摘要
        key_points: 关键点列表
        original_length: 原始长度
        compressed_length: 压缩后长度
        compression_ratio: 压缩比
        preserved_entities: 保留的实体（函数名、类名等）
        metadata: 元数据
    """
    summary: str
    key_points: list[str] = field(default_factory=list)
    original_length: int = 0
    compressed_length: int = 0
    compression_ratio: float = 0.0
    preserved_entities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "summary": self.summary,
            "key_points": self.key_points,
            "original_length": self.original_length,
            "compressed_length": self.compressed_length,
            "compression_ratio": self.compression_ratio,
            "preserved_entities": self.preserved_entities,
            "metadata": self.metadata,
        }


@dataclass
class Knowledge:
    """从对话中蒸馏出的知识"""
    id: str
    content: str
    title: str
    category: str
    tags: list[str]
    source_session: str
    created_at: datetime = field(default_factory=datetime.now)
    confidence: float = 1.0


class CompressorConfig(BaseModel):
    """
    压缩器配置
    
    Attributes:
        compression_level: 压缩级别
        max_summary_length: 最大摘要长度
        preserve_code_blocks: 是否保留代码块
        preserve_function_names: 是否保留函数名
        preserve_class_names: 是否保留类名
        enable_knowledge_distillation: 是否启用知识蒸馏
        target_compression_ratio: 目标压缩比
    """
    compression_level: CompressionLevel = CompressionLevel.MEDIUM
    max_summary_length: int = Field(default=2000, ge=100)
    preserve_code_blocks: bool = True
    preserve_function_names: bool = True
    preserve_class_names: bool = True
    enable_knowledge_distillation: bool = True
    target_compression_ratio: float = Field(default=0.3, ge=0.1, le=0.9)


class ContextCompressor:
    """
    上下文智能压缩器
    
    提供对话历史和代码上下文的智能压缩功能，
    支持知识蒸馏，从对话中提取关键知识点。
    
    Example:
        >>> config = CompressorConfig(compression_level=CompressionLevel.HIGH)
        >>> compressor = ContextCompressor(config)
        >>> compressed = compressor.compress_conversation(messages)
        >>> print(f"压缩比: {compressed.compression_ratio:.2%}")
    """

    # 关键词权重配置
    IMPORTANT_KEYWORDS = {
        "error": 3, "错误": 3, "exception": 3, "异常": 3,
        "fix": 2, "修复": 2, "solve": 2, "解决": 2,
        "important": 2, "重要": 2, "critical": 3, "关键": 2,
        "todo": 1, "note": 1, "注意": 1,
        "function": 1, "函数": 1, "class": 1, "类": 1,
        "api": 2, "config": 1, "配置": 1,
    }

    # 代码关键模式
    CODE_PATTERNS = [
        r'def\s+\w+',           # 函数定义
        r'class\s+\w+',         # 类定义
        r'import\s+\w+',        # 导入
        r'from\s+\w+\s+import', # 从...导入
        r'@\w+',                # 装饰器
        r'async\s+def',         # 异步函数
        r'raise\s+\w+',         # 抛出异常
        r'try:',                # try 块
        r'except\s+\w*:',       # except 块
    ]

    def __init__(self, config: CompressorConfig | None = None):
        """
        初始化压缩器
        
        Args:
            config: 压缩器配置
        """
        self.config = config or CompressorConfig()
        self._compiled_patterns = [
            re.compile(p) for p in self.CODE_PATTERNS
        ]
        logger.info(f"上下文压缩器初始化完成，压缩级别: {self.config.compression_level.value}")

    def compress_conversation(
        self,
        messages: list[dict[str, Any]],
        content_type: ContentType = ContentType.CONVERSATION,
    ) -> CompressedContext:
        """
        压缩对话历史
        
        Args:
            messages: 消息列表，每条消息包含 role 和 content
            content_type: 内容类型
            
        Returns:
            压缩后的上下文
        """
        if not messages:
            return CompressedContext(summary="", key_points=[])

        # 合并所有消息
        full_text = self._merge_messages(messages)
        original_length = len(full_text)

        # 提取关键点
        key_points = self.extract_key_points(full_text)

        # 提取保留实体
        preserved_entities = self._extract_entities(full_text)

        # 生成摘要
        summary = self._generate_summary(messages, key_points)

        # 计算压缩比
        compressed_length = len(summary)
        compression_ratio = 1 - (compressed_length / original_length) if original_length > 0 else 0

        return CompressedContext(
            summary=summary,
            key_points=key_points,
            original_length=original_length,
            compressed_length=compressed_length,
            compression_ratio=compression_ratio,
            preserved_entities=preserved_entities,
            metadata={
                "message_count": len(messages),
                "content_type": content_type.value,
                "compression_level": self.config.compression_level.value,
            }
        )

    def _merge_messages(self, messages: list[dict[str, Any]]) -> str:
        """合并消息"""
        parts = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            parts.append(f"[{role}]: {content}")
        return "\n\n".join(parts)

    def compress_code_context(
        self,
        code: str,
        max_length: int = 2000,
        preserve_signatures: bool = True,
    ) -> str:
        """
        压缩代码上下文
        
        Args:
            code: 代码字符串
            max_length: 最大长度
            preserve_signatures: 是否保留函数/类签名
            
        Returns:
            压缩后的代码
        """
        if len(code) <= max_length:
            return code

        try:
            # 尝试解析为 Python 代码
            tree = ast.parse(code)

            # 提取关键结构
            structures = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    structures.append(self._extract_function_signature(node, code))
                elif isinstance(node, ast.ClassDef):
                    structures.append(self._extract_class_signature(node, code))

            if structures:
                compressed = "\n\n".join(structures)
                if len(compressed) <= max_length:
                    return compressed

        except SyntaxError:
            pass

        # 回退到简单截断
        return self._smart_truncate(code, max_length)

    def _extract_function_signature(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        source: str,
    ) -> str:
        """提取函数签名和文档字符串"""
        lines = []

        # 装饰器
        for decorator in node.decorator_list:
            lines.append(f"@{ast.unparse(decorator)}")

        # 函数定义
        func_def = f"def {node.name}({ast.unparse(node.args)})"
        if node.returns:
            func_def += f" -> {ast.unparse(node.returns)}"
        func_def += ":"
        lines.append(func_def)

        # 文档字符串
        if (node.body and isinstance(node.body[0], ast.Expr) and
                isinstance(node.body[0].value, ast.Constant) and
                isinstance(node.body[0].value.value, str)):
            docstring = node.body[0].value.value
            # 只保留文档字符串的第一行
            first_line = docstring.split("\n")[0][:100]
            lines.append(f'    """{first_line}..."""')
        else:
            lines.append("    ...")

        return "\n".join(lines)

    def _extract_class_signature(self, node: ast.ClassDef, source: str) -> str:
        """提取类签名"""
        lines = []

        # 装饰器
        for decorator in node.decorator_list:
            lines.append(f"@{ast.unparse(decorator)}")

        # 类定义
        bases = [ast.unparse(base) for base in node.bases]
        class_def = f"class {node.name}"
        if bases:
            class_def += f"({', '.join(bases)})"
        class_def += ":"
        lines.append(class_def)

        # 方法和属性列表
        members = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                members.append(f"    def {item.name}(...)")
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        members.append(f"    {target.name} = ...")

        if members:
            lines.extend(members[:10])  # 最多显示 10 个成员
            if len(members) > 10:
                lines.append(f"    # ... and {len(members) - 10} more members")
        else:
            lines.append("    ...")

        return "\n".join(lines)

    def _smart_truncate(self, text: str, max_length: int) -> str:
        """智能截断文本"""
        if len(text) <= max_length:
            return text

        # 按段落分割
        paragraphs = text.split("\n\n")

        # 计算每个段落的重要性分数
        scored_paragraphs = []
        for para in paragraphs:
            score = self._calculate_importance(para)
            scored_paragraphs.append((para, score))

        # 按重要性排序
        scored_paragraphs.sort(key=lambda x: x[1], reverse=True)

        # 选择段落直到达到长度限制
        selected = []
        current_length = 0

        for para, score in scored_paragraphs:
            if current_length + len(para) + 2 <= max_length:
                selected.append(para)
                current_length += len(para) + 2
            elif current_length == 0:
                # 如果第一个段落就太长，截断它
                selected.append(para[:max_length - 3] + "...")
                break

        return "\n\n".join(selected)

    def _calculate_importance(self, text: str) -> float:
        """计算文本重要性分数"""
        score = 0.0
        text_lower = text.lower()

        # 关键词权重
        for keyword, weight in self.IMPORTANT_KEYWORDS.items():
            if keyword in text_lower:
                score += weight

        # 代码模式
        for pattern in self._compiled_patterns:
            if pattern.search(text):
                score += 1

        # 长度惩罚（过长的文本降低分数）
        if len(text) > 1000:
            score *= 0.8

        return score

    def extract_key_points(self, text: str) -> list[str]:
        """
        提取关键点
        
        Args:
            text: 文本内容
            
        Returns:
            关键点列表
        """
        key_points = []

        # 按句子分割
        sentences = re.split(r'[。！？.!?]\s*', text)

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # 检查是否包含关键信息
            score = self._calculate_importance(sentence)

            # 根据压缩级别调整阈值
            threshold = {
                CompressionLevel.LOW: 2.0,
                CompressionLevel.MEDIUM: 3.0,
                CompressionLevel.HIGH: 4.0,
                CompressionLevel.AGGRESSIVE: 5.0,
            }.get(self.config.compression_level, 3.0)

            if score >= threshold:
                key_points.append(sentence)

        return key_points[:20]  # 最多返回 20 个关键点

    def _extract_entities(self, text: str) -> list[str]:
        """提取实体（函数名、类名等）"""
        entities = []

        # 提取函数名
        func_pattern = r'def\s+(\w+)\s*\('
        entities.extend(re.findall(func_pattern, text))

        # 提取类名
        class_pattern = r'class\s+(\w+)'
        entities.extend(re.findall(class_pattern, text))

        # 提取变量名（大写开头的可能是常量或类）
        const_pattern = r'\b([A-Z][A-Z_0-9]+)\b'
        entities.extend(re.findall(const_pattern, text))

        # 去重并保持顺序
        seen = set()
        unique = []
        for e in entities:
            if e not in seen:
                seen.add(e)
                unique.append(e)

        return unique[:50]  # 最多返回 50 个实体

    def _generate_summary(
        self,
        messages: list[dict[str, Any]],
        key_points: list[str],
    ) -> str:
        """生成摘要"""
        parts = []

        # 根据压缩级别决定摘要结构
        if self.config.compression_level == CompressionLevel.AGGRESSIVE:
            # 激进压缩：只保留关键点
            if key_points:
                parts.append("## 关键信息\n")
                for i, point in enumerate(key_points[:10], 1):
                    parts.append(f"{i}. {point}")
            return "\n".join(parts)

        # 统计信息
        user_msgs = sum(1 for m in messages if m.get("role") == "user")
        assistant_msgs = sum(1 for m in messages if m.get("role") == "assistant")

        parts.append("## 对话摘要\n")
        parts.append(f"- 用户消息: {user_msgs} 条")
        parts.append(f"- 助手消息: {assistant_msgs} 条")
        parts.append(f"- 关键点: {len(key_points)} 个")
        parts.append("")

        # 关键点
        if key_points:
            parts.append("## 关键信息\n")
            for i, point in enumerate(key_points[:15], 1):
                # 截断过长的关键点
                if len(point) > 200:
                    point = point[:200] + "..."
                parts.append(f"{i}. {point}")

        summary = "\n".join(parts)

        # 确保不超过最大长度
        if len(summary) > self.config.max_summary_length:
            summary = summary[:self.config.max_summary_length - 3] + "..."

        return summary

    def distill_knowledge(
        self,
        conversation: list[dict[str, Any]],
        session_id: str = "",
    ) -> list[Knowledge]:
        """
        从对话中蒸馏知识
        
        Args:
            conversation: 对话消息列表
            session_id: 会话 ID
            
        Returns:
            提取的知识列表
        """
        if not self.config.enable_knowledge_distillation:
            return []

        knowledge_list = []

        # 合并对话
        full_text = self._merge_messages(conversation)

        # 提取代码模式
        code_knowledge = self._extract_code_patterns(full_text, session_id)
        knowledge_list.extend(code_knowledge)

        # 提取错误解决方案
        error_knowledge = self._extract_error_solutions(full_text, session_id)
        knowledge_list.extend(error_knowledge)

        # 提取配置信息
        config_knowledge = self._extract_config_info(full_text, session_id)
        knowledge_list.extend(config_knowledge)

        logger.info(f"从对话中蒸馏出 {len(knowledge_list)} 条知识")
        return knowledge_list

    def _extract_code_patterns(self, text: str, session_id: str) -> list[Knowledge]:
        """提取代码模式知识"""
        knowledge_list = []

        # 查找代码块
        code_blocks = re.findall(r'```[\w]*\n(.*?)```', text, re.DOTALL)

        for i, code in enumerate(code_blocks):
            if len(code) < 50:  # 忽略太短的代码块
                continue

            # 分析代码特征
            features = []
            if "async def" in code or "await" in code:
                features.append("async")
            if "class " in code:
                features.append("oop")
            if "try:" in code or "except" in code:
                features.append("error-handling")
            if "@" in code and "def" in code:
                features.append("decorator")

            if features:
                knowledge = Knowledge(
                    id=f"kb-{session_id}-code-{i}",
                    content=code[:500],  # 截断
                    title=f"代码模式: {', '.join(features)}",
                    category="code_pattern",
                    tags=features,
                    source_session=session_id,
                )
                knowledge_list.append(knowledge)

        return knowledge_list

    def _extract_error_solutions(self, text: str, session_id: str) -> list[Knowledge]:
        """提取错误解决方案"""
        knowledge_list = []

        # 查找错误和解决方案对
        error_patterns = [
            (r'(Error|Exception|错误|异常)[:：]\s*(.+?)(?=\n)', "error"),
            (r'(Fix|Solution|解决|修复)[:：]\s*(.+?)(?=\n)', "solution"),
        ]

        errors = []
        solutions = []

        for pattern, kind in error_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                content = match[1].strip() if len(match) > 1 else match[0]
                if kind == "error":
                    errors.append(content)
                else:
                    solutions.append(content)

        # 配对错误和解决方案
        for i, (error, solution) in enumerate(zip(errors, solutions)):
            knowledge = Knowledge(
                id=f"kb-{session_id}-error-{i}",
                content=f"错误: {error}\n解决: {solution}",
                title=f"错误解决方案: {error[:50]}",
                category="error_solution",
                tags=["error", "solution"],
                source_session=session_id,
            )
            knowledge_list.append(knowledge)

        return knowledge_list

    def _extract_config_info(self, text: str, session_id: str) -> list[Knowledge]:
        """提取配置信息"""
        knowledge_list = []

        # 查找配置模式
        config_patterns = [
            r'(\w+)\s*=\s*["\']?([^"\'\n]+)["\']?',
            r'(\w+):\s*["\']?([^"\'\n]+)["\']?',
        ]

        configs = []
        for pattern in config_patterns:
            matches = re.findall(pattern, text)
            configs.extend(matches)

        # 过滤掉常见的非配置项
        ignore_keys = {"def", "class", "if", "else", "for", "while", "return", "import", "from"}

        for i, (key, value) in enumerate(configs):
            key = key.strip()
            value = value.strip()

            if key.lower() in ignore_keys:
                continue
            if len(value) < 2 or len(value) > 100:
                continue

            knowledge = Knowledge(
                id=f"kb-{session_id}-config-{i}",
                content=f"{key} = {value}",
                title=f"配置: {key}",
                category="configuration",
                tags=["config", key],
                source_session=session_id,
            )
            knowledge_list.append(knowledge)

        return knowledge_list[:10]  # 最多返回 10 条配置

    def summarize_messages(self, messages: list[dict[str, Any]]) -> str:
        """
        生成消息摘要
        
        Args:
            messages: 消息列表
            
        Returns:
            摘要文本
        """
        compressed = self.compress_conversation(messages)
        return compressed.summary

    def estimate_tokens(self, text: str) -> int:
        """
        估算 token 数量
        
        使用简单的启发式方法估算 token 数量。
        
        Args:
            text: 文本内容
            
        Returns:
            估算的 token 数量
        """
        if not text:
            return 0

        # 基础估算：英文约 4 字符 = 1 token，中文约 2 字符 = 1 token
        # 这是一个粗略的估算

        # 统计中英文字符
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        english_chars = len(text) - chinese_chars

        # 估算 token
        tokens = (chinese_chars / 2) + (english_chars / 4)

        # 代码通常有更多的 token
        if '```' in text or 'def ' in text or 'class ' in text:
            tokens *= 1.2

        return int(tokens)

    def get_compression_stats(self) -> dict[str, Any]:
        """获取压缩统计信息"""
        return {
            "compression_level": self.config.compression_level.value,
            "max_summary_length": self.config.max_summary_length,
            "target_compression_ratio": self.config.target_compression_ratio,
            "knowledge_distillation_enabled": self.config.enable_knowledge_distillation,
        }


# 创建默认压缩器实例
context_compressor = ContextCompressor()
