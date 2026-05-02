"""
FoxCode 语义代码索引系统 - 基于向量的代码语义搜索

这个文件提供代码的语义搜索功能:
1. 代码解析：解析代码结构（AST 分析）
2. 代码向量化：将代码片段转换为向量表示
3. 语义搜索：用自然语言查询搜索相关代码
4. 依赖分析：分析代码间的依赖关系
5. 索引持久化：保存和加载索引，支持增量更新

支持的嵌入模型:
- OpenAI embeddings
- 本地模型（无需 API 调用）

使用方式:
    from foxcode.core.semantic_index import SemanticCodeIndex

    index = SemanticCodeIndex(working_dir=Path("."))
    await index.build_index()
    results = await index.search("用户登录相关代码")
"""

from __future__ import annotations

import ast
import asyncio
import hashlib
import json
import logging
import os
import pickle
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

import aiofiles
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger(__name__)

T = TypeVar("T")


class EmbeddingModelType(str, Enum):
    """嵌入模型类型枚举"""
    OPENAI = "openai"
    LOCAL = "local"
    HUGGINGFACE = "huggingface"


class CodeLanguage(str, Enum):
    """支持的编程语言"""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    GO = "go"
    RUST = "rust"
    CPP = "cpp"
    C = "c"
    UNKNOWN = "unknown"


class DependencyType(str, Enum):
    """依赖类型"""
    IMPORT = "import"
    IMPORT_FROM = "import_from"
    FUNCTION_CALL = "function_call"
    CLASS_INHERITANCE = "class_inheritance"
    VARIABLE_REFERENCE = "variable_reference"


class SemanticIndexConfig(BaseModel):
    """
    语义索引配置

    配置语义代码索引系统的各项参数，包括嵌入模型设置、
    索引存储路径、文件过滤规则等。

    Attributes:
        embedding_model_type: 嵌入模型类型
        embedding_model_name: 嵌入模型名称
        embedding_dimension: 嵌入向量维度
        openai_api_key: OpenAI API Key（使用 OpenAI 模型时需要）
        openai_base_url: OpenAI API 基础 URL
        index_dir: 索引存储目录
        max_chunk_size: 最大代码块大小（字符数）
        chunk_overlap: 代码块重叠大小
        supported_extensions: 支持的文件扩展名
        exclude_patterns: 排除的文件模式
        enable_cache: 是否启用缓存
        cache_ttl: 缓存过期时间（秒）
        batch_size: 批处理大小
        max_workers: 最大工作线程数
    """
    model_config = ConfigDict(protected_namespaces=())

    embedding_model_type: EmbeddingModelType = EmbeddingModelType.OPENAI
    embedding_model_name: str = "text-embedding-ada-002"
    embedding_dimension: int = Field(default=1536, ge=64, le=4096)
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    index_dir: str = ".foxcode/semantic_index"
    max_chunk_size: int = Field(default=1000, ge=100, le=10000)
    chunk_overlap: int = Field(default=100, ge=0, le=500)
    supported_extensions: list[str] = Field(
        default_factory=lambda: [
            ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs",
            ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
            ".kt", ".scala", ".lua", ".r", ".sql", ".sh", ".bash",
        ]
    )
    exclude_patterns: list[str] = Field(
        default_factory=lambda: [
            "node_modules", "venv", ".venv", "__pycache__", ".git",
            "dist", "build", "*.min.js", "*.pyc", ".mypy_cache",
        ]
    )
    enable_cache: bool = True
    cache_ttl: int = Field(default=3600, ge=60, description="缓存过期时间（秒）")
    batch_size: int = Field(default=32, ge=1, le=256)
    max_workers: int = Field(default=4, ge=1, le=16)

    @field_validator("supported_extensions", mode="before")
    @classmethod
    def validate_extensions(cls, v: list[str] | None) -> list[str]:
        """验证文件扩展名格式"""
        if v is None:
            return []
        validated = []
        for ext in v:
            if not ext:
                continue
            if not ext.startswith('.'):
                ext = '.' + ext
            validated.append(ext.lower())
        return validated


@dataclass
class CodeChunk:
    """
    代码块数据结构

    表示代码中的一个语义单元，可以是函数、类、模块等。

    Attributes:
        id: 代码块唯一标识符
        file_path: 文件路径
        content: 代码内容
        start_line: 起始行号
        end_line: 结束行号
        language: 编程语言
        chunk_type: 代码块类型（function, class, module 等）
        name: 代码块名称
        docstring: 文档字符串
        embedding: 嵌入向量
        metadata: 额外元数据
        hash: 内容哈希值
        created_at: 创建时间
        modified_at: 修改时间
    """
    id: str
    file_path: Path
    content: str
    start_line: int
    end_line: int
    language: CodeLanguage
    chunk_type: str
    name: str
    docstring: str | None = None
    embedding: np.ndarray | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    hash: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        """初始化后计算哈希值"""
        if not self.hash:
            self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """计算内容哈希值"""
        content_hash = hashlib.sha256(self.content.encode()).hexdigest()[:16]
        return f"{self.file_path.stem}_{self.chunk_type}_{self.start_line}_{content_hash}"

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "file_path": str(self.file_path),
            "content": self.content,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "language": self.language.value,
            "chunk_type": self.chunk_type,
            "name": self.name,
            "docstring": self.docstring,
            "embedding": self.embedding.tolist() if self.embedding is not None else None,
            "metadata": self.metadata,
            "hash": self.hash,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CodeChunk:
        """从字典创建实例"""
        embedding_data = data.get("embedding")
        embedding = np.array(embedding_data) if embedding_data else None

        return cls(
            id=data["id"],
            file_path=Path(data["file_path"]),
            content=data["content"],
            start_line=data["start_line"],
            end_line=data["end_line"],
            language=CodeLanguage(data["language"]),
            chunk_type=data["chunk_type"],
            name=data["name"],
            docstring=data.get("docstring"),
            embedding=embedding,
            metadata=data.get("metadata", {}),
            hash=data.get("hash", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            modified_at=datetime.fromisoformat(data["modified_at"]) if data.get("modified_at") else datetime.now(),
        )


@dataclass
class SearchResult:
    """
    搜索结果数据结构

    表示一次语义搜索的结果，包含匹配的代码块和相关性信息。

    Attributes:
        chunk: 匹配的代码块
        score: 相似度分数（0-1）
        highlights: 高亮片段
        context: 上下文信息
    """
    chunk: CodeChunk
    score: float
    highlights: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "chunk": self.chunk.to_dict(),
            "score": self.score,
            "highlights": self.highlights,
            "context": self.context,
        }


@dataclass
class Dependency:
    """
    依赖关系数据结构

    表示代码之间的依赖关系，包括导入、函数调用、类继承等。

    Attributes:
        source_file: 源文件路径
        target_file: 目标文件路径
        source_name: 源名称（函数名、类名等）
        target_name: 目标名称
        dependency_type: 依赖类型
        line_number: 行号
        column: 列号
        metadata: 额外元数据
    """
    source_file: Path
    target_file: Path | None
    source_name: str
    target_name: str
    dependency_type: DependencyType
    line_number: int
    column: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "source_file": str(self.source_file),
            "target_file": str(self.target_file) if self.target_file else None,
            "source_name": self.source_name,
            "target_name": self.target_name,
            "dependency_type": self.dependency_type.value,
            "line_number": self.line_number,
            "column": self.column,
            "metadata": self.metadata,
        }


@dataclass
class CallGraph:
    """
    函数调用图数据结构

    表示函数之间的调用关系图。

    Attributes:
        function_name: 函数名称
        file_path: 文件路径
        callers: 调用该函数的函数列表
        callees: 该函数调用的函数列表
        complexity: 复杂度评分
        metadata: 额外元数据
    """
    function_name: str
    file_path: Path
    callers: list[str] = field(default_factory=list)
    callees: list[str] = field(default_factory=list)
    complexity: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "function_name": self.function_name,
            "file_path": str(self.file_path),
            "callers": self.callers,
            "callees": self.callees,
            "complexity": self.complexity,
            "metadata": self.metadata,
        }


@dataclass
class FileIndex:
    """
    文件索引数据结构

    存储单个文件的索引信息，用于增量更新。

    Attributes:
        file_path: 文件路径
        hash: 文件内容哈希
        chunks: 代码块列表
        dependencies: 依赖关系列表
        last_modified: 最后修改时间
        language: 编程语言
    """
    file_path: Path
    hash: str
    chunks: list[CodeChunk] = field(default_factory=list)
    dependencies: list[Dependency] = field(default_factory=list)
    last_modified: datetime = field(default_factory=datetime.now)
    language: CodeLanguage = CodeLanguage.UNKNOWN

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "file_path": str(self.file_path),
            "hash": self.hash,
            "chunks": [c.to_dict() for c in self.chunks],
            "dependencies": [d.to_dict() for d in self.dependencies],
            "last_modified": self.last_modified.isoformat(),
            "language": self.language.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FileIndex:
        """从字典创建实例"""
        return cls(
            file_path=Path(data["file_path"]),
            hash=data["hash"],
            chunks=[CodeChunk.from_dict(c) for c in data.get("chunks", [])],
            dependencies=[
                Dependency(
                    source_file=Path(d["source_file"]),
                    target_file=Path(d["target_file"]) if d.get("target_file") else None,
                    source_name=d["source_name"],
                    target_name=d["target_name"],
                    dependency_type=DependencyType(d["dependency_type"]),
                    line_number=d["line_number"],
                    column=d.get("column", 0),
                    metadata=d.get("metadata", {}),
                )
                for d in data.get("dependencies", [])
            ],
            last_modified=datetime.fromisoformat(data["last_modified"]) if data.get("last_modified") else datetime.now(),
            language=CodeLanguage(data.get("language", "unknown")),
        )


class BaseEmbeddingModel(ABC):
    """
    嵌入模型基类

    定义嵌入模型的抽象接口，所有嵌入模型实现都需要继承此类。
    """

    @abstractmethod
    async def embed_text(self, text: str) -> np.ndarray:
        """
        将文本转换为嵌入向量

        Args:
            text: 输入文本

        Returns:
            嵌入向量
        """
        pass

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """
        批量将文本转换为嵌入向量

        Args:
            texts: 输入文本列表

        Returns:
            嵌入向量列表
        """
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """
        获取嵌入向量维度

        Returns:
            向量维度
        """
        pass


class OpenAIEmbeddingModel(BaseEmbeddingModel):
    """
    OpenAI 嵌入模型实现

    使用 OpenAI API 进行文本嵌入。
    """

    def __init__(
        self,
        model_name: str = "text-embedding-3-small",
        api_key: str | None = None,
        base_url: str | None = None,
        dimension: int = 1536,
    ) -> None:
        """
        初始化 OpenAI 嵌入模型

        Args:
            model_name: 模型名称
            api_key: API Key
            base_url: API 基础 URL
            dimension: 向量维度
        """
        self.model_name = model_name
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.base_url = base_url
        self.dimension = dimension
        self._client = None
        logger.info(f"初始化 OpenAI 嵌入模型: {model_name}, 维度: {dimension}")

    def _get_client(self) -> Any:
        """延迟初始化 OpenAI 客户端"""
        if self._client is None:
            try:
                from openai import AsyncOpenAI

                client_kwargs: dict[str, Any] = {}
                if self.api_key:
                    client_kwargs["api_key"] = self.api_key
                if self.base_url:
                    client_kwargs["base_url"] = self.base_url

                self._client = AsyncOpenAI(**client_kwargs)
                logger.debug("OpenAI 客户端初始化成功")
            except ImportError as e:
                logger.error("未安装 openai 库，请运行: pip install openai")
                raise ImportError("未安装 openai 库") from e
        return self._client

    async def embed_text(self, text: str) -> np.ndarray:
        """
        将文本转换为嵌入向量

        Args:
            text: 输入文本

        Returns:
            嵌入向量
        """
        try:
            client = self._get_client()
            response = await client.embeddings.create(
                model=self.model_name,
                input=text,
                dimensions=self.dimension,
            )
            embedding = np.array(response.data[0].embedding, dtype=np.float32)
            logger.debug(f"生成嵌入向量，维度: {len(embedding)}")
            return embedding
        except Exception as e:
            logger.error(f"生成嵌入向量失败: {e}")
            raise

    async def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """
        批量将文本转换为嵌入向量

        Args:
            texts: 输入文本列表

        Returns:
            嵌入向量列表
        """
        if not texts:
            return []

        try:
            client = self._get_client()
            response = await client.embeddings.create(
                model=self.model_name,
                input=texts,
                dimensions=self.dimension,
            )
            embeddings = [np.array(item.embedding, dtype=np.float32) for item in response.data]
            logger.debug(f"批量生成 {len(embeddings)} 个嵌入向量")
            return embeddings
        except Exception as e:
            logger.error(f"批量生成嵌入向量失败: {e}")
            raise

    def get_dimension(self) -> int:
        """获取嵌入向量维度"""
        return self.dimension


class LocalEmbeddingModel(BaseEmbeddingModel):
    """
    本地嵌入模型实现

    使用本地模型（如 sentence-transformers）进行文本嵌入。
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        dimension: int = 384,
        device: str | None = None,
    ) -> None:
        """
        初始化本地嵌入模型

        Args:
            model_name: 模型名称
            dimension: 向量维度
            device: 运行设备（cuda, cpu, mps）
        """
        self.model_name = model_name
        self.dimension = dimension
        self.device = device
        self._model = None
        logger.info(f"初始化本地嵌入模型: {model_name}, 维度: {dimension}")

    def _get_model(self) -> Any:
        """延迟初始化模型"""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name, device=self.device)
                logger.debug(f"本地模型 {self.model_name} 加载成功")
            except ImportError as e:
                logger.error("未安装 sentence-transformers 库，请运行: pip install sentence-transformers")
                raise ImportError("未安装 sentence-transformers 库") from e
        return self._model

    async def embed_text(self, text: str) -> np.ndarray:
        """
        将文本转换为嵌入向量

        Args:
            text: 输入文本

        Returns:
            嵌入向量
        """
        try:
            model = self._get_model()
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None,
                lambda: model.encode(text, convert_to_numpy=True)
            )
            logger.debug(f"生成嵌入向量，维度: {len(embedding)}")
            return embedding.astype(np.float32)
        except Exception as e:
            logger.error(f"生成嵌入向量失败: {e}")
            raise

    async def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """
        批量将文本转换为嵌入向量

        Args:
            texts: 输入文本列表

        Returns:
            嵌入向量列表
        """
        if not texts:
            return []

        try:
            model = self._get_model()
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None,
                lambda: model.encode(texts, convert_to_numpy=True)
            )
            result = [e.astype(np.float32) for e in embeddings]
            logger.debug(f"批量生成 {len(result)} 个嵌入向量")
            return result
        except Exception as e:
            logger.error(f"批量生成嵌入向量失败: {e}")
            raise

    def get_dimension(self) -> int:
        """获取嵌入向量维度"""
        return self.dimension


def create_embedding_model(config: SemanticIndexConfig) -> BaseEmbeddingModel:
    """
    创建嵌入模型实例

    根据配置创建相应的嵌入模型。

    Args:
        config: 语义索引配置

    Returns:
        嵌入模型实例
    """
    if config.embedding_model_type == EmbeddingModelType.OPENAI:
        return OpenAIEmbeddingModel(
            model_name=config.embedding_model_name,
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
            dimension=config.embedding_dimension,
        )
    elif config.embedding_model_type == EmbeddingModelType.LOCAL or config.embedding_model_type == EmbeddingModelType.HUGGINGFACE:
        return LocalEmbeddingModel(
            model_name=config.embedding_model_name,
            dimension=config.embedding_dimension,
        )
    else:
        raise ValueError(f"不支持的嵌入模型类型: {config.embedding_model_type}")


class PythonCodeParser:
    """
    Python 代码解析器

    使用 AST 解析 Python 代码，提取函数、类等代码块。
    """

    @staticmethod
    def get_language() -> CodeLanguage:
        """获取支持的语言"""
        return CodeLanguage.PYTHON

    @staticmethod
    def parse_file(file_path: Path) -> list[CodeChunk]:
        """
        解析 Python 文件

        Args:
            file_path: 文件路径

        Returns:
            代码块列表
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)
        except SyntaxError as e:
            logger.warning(f"解析文件 {file_path} 时发生语法错误: {e}")
            return []
        except Exception as e:
            logger.error(f"读取文件 {file_path} 失败: {e}")
            return []

        chunks = []
        lines = content.splitlines(keepends=True)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                chunk = PythonCodeParser._extract_function(file_path, node, lines)
                if chunk:
                    chunks.append(chunk)
            elif isinstance(node, ast.ClassDef):
                chunk = PythonCodeParser._extract_class(file_path, node, lines)
                if chunk:
                    chunks.append(chunk)

        if not chunks:
            module_chunk = PythonCodeParser._extract_module(file_path, tree, lines)
            if module_chunk:
                chunks.append(module_chunk)

        logger.debug(f"从 {file_path} 提取了 {len(chunks)} 个代码块")
        return chunks

    @staticmethod
    def _extract_function(
        file_path: Path,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        lines: list[str],
    ) -> CodeChunk | None:
        """提取函数代码块"""
        try:
            start_line = node.lineno - 1
            end_line = node.end_lineno if node.end_lineno else start_line + 1

            content = "".join(lines[start_line:end_line])

            docstring = ast.get_docstring(node)

            return CodeChunk(
                id=f"{file_path.stem}_func_{node.name}_{start_line}",
                file_path=file_path,
                content=content,
                start_line=start_line + 1,
                end_line=end_line,
                language=CodeLanguage.PYTHON,
                chunk_type="function",
                name=node.name,
                docstring=docstring,
                metadata={
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                    "args": [arg.arg for arg in node.args.args],
                    "decorators": [d.id if isinstance(d, ast.Name) else str(d) for d in node.decorator_list],
                },
            )
        except Exception as e:
            logger.warning(f"提取函数 {node.name} 失败: {e}")
            return None

    @staticmethod
    def _extract_class(
        file_path: Path,
        node: ast.ClassDef,
        lines: list[str],
    ) -> CodeChunk | None:
        """提取类代码块"""
        try:
            start_line = node.lineno - 1
            end_line = node.end_lineno if node.end_lineno else start_line + 1

            content = "".join(lines[start_line:end_line])

            docstring = ast.get_docstring(node)

            bases = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    bases.append(f"{base.value.id}.{base.attr}" if isinstance(base.value, ast.Name) else str(base))

            return CodeChunk(
                id=f"{file_path.stem}_class_{node.name}_{start_line}",
                file_path=file_path,
                content=content,
                start_line=start_line + 1,
                end_line=end_line,
                language=CodeLanguage.PYTHON,
                chunk_type="class",
                name=node.name,
                docstring=docstring,
                metadata={
                    "bases": bases,
                    "decorators": [d.id if isinstance(d, ast.Name) else str(d) for d in node.decorator_list],
                },
            )
        except Exception as e:
            logger.warning(f"提取类 {node.name} 失败: {e}")
            return None

    @staticmethod
    def _extract_module(
        file_path: Path,
        tree: ast.Module,
        lines: list[str],
    ) -> CodeChunk | None:
        """提取模块代码块"""
        try:
            content = "".join(lines)
            docstring = ast.get_docstring(tree)

            return CodeChunk(
                id=f"{file_path.stem}_module_0",
                file_path=file_path,
                content=content,
                start_line=1,
                end_line=len(lines),
                language=CodeLanguage.PYTHON,
                chunk_type="module",
                name=file_path.stem,
                docstring=docstring,
            )
        except Exception as e:
            logger.warning(f"提取模块 {file_path} 失败: {e}")
            return None

    @staticmethod
    def extract_dependencies(file_path: Path) -> list[Dependency]:
        """
        提取文件依赖关系

        Args:
            file_path: 文件路径

        Returns:
            依赖关系列表
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)
        except Exception as e:
            logger.error(f"解析文件 {file_path} 失败: {e}")
            return []

        dependencies = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    dependencies.append(Dependency(
                        source_file=file_path,
                        target_file=None,
                        source_name=file_path.stem,
                        target_name=alias.name,
                        dependency_type=DependencyType.IMPORT,
                        line_number=node.lineno,
                        column=node.col_offset,
                        metadata={"alias": alias.asname},
                    ))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    dependencies.append(Dependency(
                        source_file=file_path,
                        target_file=None,
                        source_name=file_path.stem,
                        target_name=f"{module}.{alias.name}" if module else alias.name,
                        dependency_type=DependencyType.IMPORT_FROM,
                        line_number=node.lineno,
                        column=node.col_offset,
                        metadata={"module": module, "alias": alias.asname},
                    ))

        logger.debug(f"从 {file_path} 提取了 {len(dependencies)} 个依赖关系")
        return dependencies


class JavaScriptCodeParser:
    """
    JavaScript/TypeScript 代码解析器

    使用正则表达式进行简单解析（实际项目中可使用 tree-sitter）。
    """

    @staticmethod
    def get_language() -> CodeLanguage:
        """获取支持的语言"""
        return CodeLanguage.JAVASCRIPT

    @staticmethod
    def parse_file(file_path: Path) -> list[CodeChunk]:
        """
        解析 JavaScript/TypeScript 文件

        Args:
            file_path: 文件路径

        Returns:
            代码块列表
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"读取文件 {file_path} 失败: {e}")
            return []

        chunks = []
        lines = content.splitlines(keepends=True)

        func_pattern = r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\([^)]*\)\s*\{'
        for match in re.finditer(func_pattern, content):
            func_name = match.group(1)
            start_pos = match.start()
            start_line = content[:start_pos].count('\n')

            brace_count = 0
            end_pos = start_pos
            in_function = False

            for i, char in enumerate(content[start_pos:], start_pos):
                if char == '{':
                    brace_count += 1
                    in_function = True
                elif char == '}':
                    brace_count -= 1
                    if in_function and brace_count == 0:
                        end_pos = i + 1
                        break

            end_line = content[:end_pos].count('\n')
            func_content = "".join(lines[start_line:end_line + 1])

            chunks.append(CodeChunk(
                id=f"{file_path.stem}_func_{func_name}_{start_line}",
                file_path=file_path,
                content=func_content,
                start_line=start_line + 1,
                end_line=end_line + 1,
                language=CodeLanguage.JAVASCRIPT,
                chunk_type="function",
                name=func_name,
            ))

        class_pattern = r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+\w+)?\s*\{'
        for match in re.finditer(class_pattern, content):
            class_name = match.group(1)
            start_pos = match.start()
            start_line = content[:start_pos].count('\n')

            brace_count = 0
            end_pos = start_pos
            in_class = False

            for i, char in enumerate(content[start_pos:], start_pos):
                if char == '{':
                    brace_count += 1
                    in_class = True
                elif char == '}':
                    brace_count -= 1
                    if in_class and brace_count == 0:
                        end_pos = i + 1
                        break

            end_line = content[:end_pos].count('\n')
            class_content = "".join(lines[start_line:end_line + 1])

            chunks.append(CodeChunk(
                id=f"{file_path.stem}_class_{class_name}_{start_line}",
                file_path=file_path,
                content=class_content,
                start_line=start_line + 1,
                end_line=end_line + 1,
                language=CodeLanguage.JAVASCRIPT,
                chunk_type="class",
                name=class_name,
            ))

        logger.debug(f"从 {file_path} 提取了 {len(chunks)} 个代码块")
        return chunks


def get_parser_for_file(file_path: Path) -> PythonCodeParser | JavaScriptCodeParser | None:
    """
    根据文件扩展名获取对应的解析器

    Args:
        file_path: 文件路径

    Returns:
        代码解析器实例
    """
    ext = file_path.suffix.lower()

    if ext == ".py":
        return PythonCodeParser()
    elif ext in (".js", ".jsx", ".ts", ".tsx"):
        return JavaScriptCodeParser()

    return None


def detect_language(file_path: Path) -> CodeLanguage:
    """
    检测文件语言

    Args:
        file_path: 文件路径

    Returns:
        编程语言
    """
    ext = file_path.suffix.lower()

    language_map = {
        ".py": CodeLanguage.PYTHON,
        ".js": CodeLanguage.JAVASCRIPT,
        ".jsx": CodeLanguage.JAVASCRIPT,
        ".ts": CodeLanguage.TYPESCRIPT,
        ".tsx": CodeLanguage.TYPESCRIPT,
        ".java": CodeLanguage.JAVA,
        ".go": CodeLanguage.GO,
        ".rs": CodeLanguage.RUST,
        ".c": CodeLanguage.C,
        ".cpp": CodeLanguage.CPP,
        ".cc": CodeLanguage.CPP,
        ".cxx": CodeLanguage.CPP,
    }

    return language_map.get(ext, CodeLanguage.UNKNOWN)


class VectorStore:
    """
    向量存储

    使用 NumPy 实现简单的向量存储和相似度搜索。
    对于大规模应用，可替换为 FAISS、Milvus 等。
    """

    def __init__(self, dimension: int) -> None:
        """
        初始化向量存储

        Args:
            dimension: 向量维度
        """
        self.dimension = dimension
        self.vectors: np.ndarray = np.array([], dtype=np.float32).reshape(0, dimension)
        self.ids: list[str] = []
        self.metadata: dict[str, dict[str, Any]] = {}
        logger.info(f"初始化向量存储，维度: {dimension}")

    def add(self, id: str, vector: np.ndarray, metadata: dict[str, Any] | None = None) -> None:
        """
        添加向量

        Args:
            id: 向量 ID
            vector: 向量
            metadata: 元数据
        """
        if vector.shape[0] != self.dimension:
            raise ValueError(f"向量维度不匹配: 期望 {self.dimension}, 实际 {vector.shape[0]}")

        self.vectors = np.vstack([self.vectors, vector.reshape(1, -1)])
        self.ids.append(id)
        self.metadata[id] = metadata or {}
        logger.debug(f"添加向量 {id}, 当前共 {len(self.ids)} 个向量")

    def search(self, query_vector: np.ndarray, top_k: int = 10) -> list[tuple[str, float]]:
        """
        搜索最相似的向量

        Args:
            query_vector: 查询向量
            top_k: 返回数量

        Returns:
            (id, score) 列表
        """
        if len(self.ids) == 0:
            return []

        if query_vector.shape[0] != self.dimension:
            raise ValueError(f"向量维度不匹配: 期望 {self.dimension}, 实际 {query_vector.shape[0]}")

        query_norm = np.linalg.norm(query_vector)
        if query_norm == 0:
            return []

        query_normalized = query_vector / query_norm

        vectors_norm = np.linalg.norm(self.vectors, axis=1, keepdims=True)
        vectors_norm[vectors_norm == 0] = 1
        vectors_normalized = self.vectors / vectors_norm

        similarities = np.dot(vectors_normalized, query_normalized)

        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = [(self.ids[i], float(similarities[i])) for i in top_indices]
        logger.debug(f"搜索返回 {len(results)} 个结果")
        return results

    def remove(self, id: str) -> bool:
        """
        移除向量

        Args:
            id: 向量 ID

        Returns:
            是否成功
        """
        if id not in self.ids:
            return False

        index = self.ids.index(id)
        self.vectors = np.delete(self.vectors, index, axis=0)
        self.ids.pop(index)
        del self.metadata[id]
        logger.debug(f"移除向量 {id}")
        return True

    def clear(self) -> None:
        """清空所有向量"""
        self.vectors = np.array([], dtype=np.float32).reshape(0, self.dimension)
        self.ids = []
        self.metadata = {}
        logger.debug("清空向量存储")

    def save(self, path: Path) -> bool:
        """
        保存向量存储到文件

        Args:
            path: 文件路径

        Returns:
            是否成功
        """
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "dimension": self.dimension,
                "vectors": self.vectors.tolist(),
                "ids": self.ids,
                "metadata": self.metadata,
            }
            with open(path, "wb") as f:
                pickle.dump(data, f)
            logger.info(f"向量存储已保存到 {path}")
            return True
        except Exception as e:
            logger.error(f"保存向量存储失败: {e}")
            return False

    def load(self, path: Path) -> bool:
        """
        从文件加载向量存储

        Args:
            path: 文件路径

        Returns:
            是否成功
        """
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)

            self.dimension = data["dimension"]
            self.vectors = np.array(data["vectors"], dtype=np.float32)
            self.ids = data["ids"]
            self.metadata = data["metadata"]
            logger.info(f"从 {path} 加载了 {len(self.ids)} 个向量")
            return True
        except FileNotFoundError:
            logger.warning(f"向量存储文件不存在: {path}")
            return False
        except Exception as e:
            logger.error(f"加载向量存储失败: {e}")
            return False

    def __len__(self) -> int:
        """返回向量数量"""
        return len(self.ids)


class SemanticCodeIndex:
    """
    语义代码索引系统

    提供代码的语义搜索、结构分析和依赖关系管理功能。
    支持多种嵌入模型，包括 OpenAI embeddings 和本地模型。

    主要功能：
    - 代码解析和向量化
    - 语义搜索（自然语言查询）
    - 代码结构分析（AST 和依赖图）
    - 索引持久化和增量更新

    Example:
        >>> config = SemanticIndexConfig(
        ...     embedding_model_type=EmbeddingModelType.OPENAI,
        ...     openai_api_key="your-api-key",
        ... )
        >>> index = SemanticCodeIndex(config)
        >>> await index.index_directory(Path("./src"))
        >>> results = await index.search("查找处理用户认证的函数")
    """

    def __init__(self, config: SemanticIndexConfig) -> None:
        """
        初始化语义代码索引系统

        Args:
            config: 语义索引配置
        """
        self.config = config
        self.embedding_model = create_embedding_model(config)
        self.vector_store = VectorStore(config.embedding_dimension)
        self.file_indices: dict[str, FileIndex] = {}
        self.chunks: dict[str, CodeChunk] = {}
        self.call_graphs: dict[str, CallGraph] = {}
        self._index_path = Path(config.index_dir)

        logger.info(
            f"初始化语义代码索引系统，模型类型: {config.embedding_model_type}, "
            f"模型名称: {config.embedding_model_name}"
        )

    def _should_index_file(self, file_path: Path) -> bool:
        """
        判断文件是否应该被索引

        Args:
            file_path: 文件路径

        Returns:
            是否应该索引
        """
        if file_path.suffix.lower() not in self.config.supported_extensions:
            return False

        path_str = str(file_path)
        for pattern in self.config.exclude_patterns:
            if pattern.startswith("*"):
                if path_str.endswith(pattern[1:]):
                    return False
            elif pattern in path_str:
                return False

        return True

    def _compute_file_hash(self, file_path: Path) -> str:
        """
        计算文件哈希值

        Args:
            file_path: 文件路径

        Returns:
            哈希值
        """
        try:
            content = file_path.read_bytes()
            return hashlib.sha256(content).hexdigest()
        except Exception as e:
            logger.error(f"计算文件哈希失败: {e}")
            return ""

    async def index_directory(self, path: Path) -> int:
        """
        索引目录下的所有代码文件

        递归遍历目录，对所有符合条件的代码文件进行索引。
        支持增量更新，只处理新增或修改的文件。

        Args:
            path: 目录路径

        Returns:
            索引的文件数量
        """
        if not path.exists():
            logger.error(f"目录不存在: {path}")
            raise FileNotFoundError(f"目录不存在: {path}")

        if not path.is_dir():
            logger.error(f"路径不是目录: {path}")
            raise ValueError(f"路径不是目录: {path}")

        logger.info(f"开始索引目录: {path}")

        files_to_index = []
        for file_path in path.rglob("*"):
            if file_path.is_file() and self._should_index_file(file_path):
                files_to_index.append(file_path)

        logger.info(f"发现 {len(files_to_index)} 个文件需要索引")

        indexed_count = 0
        for i, file_path in enumerate(files_to_index):
            try:
                success = await self.index_file(file_path)
                if success:
                    indexed_count += 1

                if (i + 1) % 10 == 0:
                    logger.info(f"进度: {i + 1}/{len(files_to_index)}")
            except Exception as e:
                logger.error(f"索引文件 {file_path} 失败: {e}")
                continue

        logger.info(f"目录索引完成，共索引 {indexed_count} 个文件")
        return indexed_count

    async def index_file(self, file_path: Path) -> bool:
        """
        索引单个文件

        解析文件、提取代码块、生成嵌入向量并存储到索引中。
        支持增量更新，如果文件未修改则跳过。

        Args:
            file_path: 文件路径

        Returns:
            是否成功索引
        """
        if not file_path.exists():
            logger.error(f"文件不存在: {file_path}")
            return False

        file_hash = self._compute_file_hash(file_path)
        file_key = str(file_path.resolve())

        existing_index = self.file_indices.get(file_key)
        if existing_index and existing_index.hash == file_hash:
            logger.debug(f"文件未修改，跳过索引: {file_path}")
            return True

        logger.info(f"索引文件: {file_path}")

        parser = get_parser_for_file(file_path)
        if parser is None:
            logger.warning(f"不支持的文件类型: {file_path}")
            return False

        chunks = parser.parse_file(file_path)
        if not chunks:
            logger.debug(f"文件无有效代码块: {file_path}")
            return True

        texts = []
        for chunk in chunks:
            text_parts = []
            if chunk.docstring:
                text_parts.append(chunk.docstring)
            text_parts.append(chunk.content)
            texts.append("\n\n".join(text_parts))

        try:
            embeddings = await self.embedding_model.embed_batch(texts)
        except Exception as e:
            logger.error(f"生成嵌入向量失败: {e}")
            return False

        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding
            self.chunks[chunk.id] = chunk
            self.vector_store.add(
                id=chunk.id,
                vector=embedding,
                metadata={
                    "file_path": str(chunk.file_path),
                    "name": chunk.name,
                    "chunk_type": chunk.chunk_type,
                    "language": chunk.language.value,
                },
            )

        dependencies = []
        if isinstance(parser, PythonCodeParser):
            dependencies = parser.extract_dependencies(file_path)

        file_index = FileIndex(
            file_path=file_path,
            hash=file_hash,
            chunks=chunks,
            dependencies=dependencies,
            last_modified=datetime.now(),
            language=detect_language(file_path),
        )
        self.file_indices[file_key] = file_index

        self._update_call_graphs(file_path, chunks)

        logger.info(f"成功索引文件 {file_path}，共 {len(chunks)} 个代码块")
        return True

    def _update_call_graphs(self, file_path: Path, chunks: list[CodeChunk]) -> None:
        """
        更新调用图

        Args:
            file_path: 文件路径
            chunks: 代码块列表
        """
        for chunk in chunks:
            if chunk.chunk_type == "function":
                callees = self._extract_callees(chunk.content)
                self.call_graphs[chunk.name] = CallGraph(
                    function_name=chunk.name,
                    file_path=file_path,
                    callers=[],
                    callees=callees,
                    metadata={"chunk_id": chunk.id},
                )

        for func_name, call_graph in self.call_graphs.items():
            for callee in call_graph.callees:
                if callee in self.call_graphs:
                    self.call_graphs[callee].callers.append(func_name)

    def _extract_callees(self, content: str) -> list[str]:
        """
        从代码内容中提取被调用的函数

        Args:
            content: 代码内容

        Returns:
            被调用的函数名列表
        """
        callees = set()

        call_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
        for match in re.finditer(call_pattern, content):
            func_name = match.group(1)
            if func_name not in ('if', 'for', 'while', 'with', 'except', 'def', 'class', 'print'):
                callees.add(func_name)

        return list(callees)

    async def search(self, query: str, top_k: int = 10) -> list[SearchResult]:
        """
        语义搜索代码

        使用自然语言查询进行语义搜索，返回最相关的代码块。

        Args:
            query: 查询字符串
            top_k: 返回结果数量

        Returns:
            搜索结果列表，按相关性排序
        """
        if not query.strip():
            logger.warning("查询字符串为空")
            return []

        logger.info(f"执行语义搜索: {query[:50]}...")

        try:
            query_embedding = await self.embedding_model.embed_text(query)
        except Exception as e:
            logger.error(f"生成查询嵌入向量失败: {e}")
            return []

        results = self.vector_store.search(query_embedding, top_k)

        search_results = []
        for chunk_id, score in results:
            chunk = self.chunks.get(chunk_id)
            if chunk:
                highlights = self._extract_highlights(chunk.content, query)
                search_results.append(SearchResult(
                    chunk=chunk,
                    score=score,
                    highlights=highlights,
                    context={
                        "file_path": str(chunk.file_path),
                        "language": chunk.language.value,
                        "chunk_type": chunk.chunk_type,
                    },
                ))

        logger.info(f"搜索返回 {len(search_results)} 个结果")
        return search_results

    def _extract_highlights(self, content: str, query: str) -> list[str]:
        """
        提取高亮片段

        Args:
            content: 代码内容
            query: 查询字符串

        Returns:
            高亮片段列表
        """
        highlights = []
        query_words = set(query.lower().split())

        lines = content.split('\n')
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(word in line_lower for word in query_words):
                context_start = max(0, i - 1)
                context_end = min(len(lines), i + 2)
                highlight = '\n'.join(lines[context_start:context_end])
                highlights.append(highlight)
                if len(highlights) >= 3:
                    break

        return highlights

    def get_call_graph(self, function_name: str) -> CallGraph | None:
        """
        获取函数调用图

        返回指定函数的调用关系图，包括调用者和被调用者。

        Args:
            function_name: 函数名称

        Returns:
            调用图，如果函数不存在则返回 None
        """
        call_graph = self.call_graphs.get(function_name)
        if call_graph:
            logger.debug(f"获取函数 {function_name} 的调用图")
            return call_graph

        logger.warning(f"未找到函数 {function_name} 的调用图")
        return None

    def get_dependencies(self, file_path: Path) -> list[Dependency]:
        """
        获取文件依赖关系

        返回指定文件的所有依赖关系，包括导入、函数调用等。

        Args:
            file_path: 文件路径

        Returns:
            依赖关系列表
        """
        file_key = str(file_path.resolve())
        file_index = self.file_indices.get(file_key)

        if file_index:
            logger.debug(f"获取文件 {file_path} 的依赖关系")
            return file_index.dependencies

        logger.warning(f"未找到文件 {file_path} 的索引")
        return []

    def get_reverse_dependencies(self, file_path: Path) -> list[Dependency]:
        """
        获取反向依赖关系

        返回依赖于指定文件的所有其他文件。

        Args:
            file_path: 文件路径

        Returns:
            反向依赖关系列表
        """
        reverse_deps = []
        target_path = file_path.resolve()

        for file_index in self.file_indices.values():
            for dep in file_index.dependencies:
                if dep.target_file and Path(dep.target_file).resolve() == target_path:
                    reverse_deps.append(dep)

        logger.debug(f"获取文件 {file_path} 的反向依赖: {len(reverse_deps)} 个")
        return reverse_deps

    async def save_index(self, path: Path | None = None) -> bool:
        """
        保存索引到文件

        将当前索引状态持久化到磁盘，包括向量存储、
        文件索引、代码块和调用图。

        Args:
            path: 保存路径，如果为 None 则使用配置中的路径

        Returns:
            是否成功保存
        """
        save_path = path or self._index_path
        save_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"保存索引到: {save_path}")

        try:
            vector_store_path = save_path / "vector_store.pkl"
            self.vector_store.save(vector_store_path)

            chunks_data = {chunk_id: chunk.to_dict() for chunk_id, chunk in self.chunks.items()}
            chunks_path = save_path / "chunks.json"
            async with aiofiles.open(chunks_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(chunks_data, ensure_ascii=False, indent=2))

            file_indices_data = {
                file_key: file_index.to_dict()
                for file_key, file_index in self.file_indices.items()
            }
            file_indices_path = save_path / "file_indices.json"
            async with aiofiles.open(file_indices_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(file_indices_data, ensure_ascii=False, indent=2))

            call_graphs_data = {
                func_name: call_graph.to_dict()
                for func_name, call_graph in self.call_graphs.items()
            }
            call_graphs_path = save_path / "call_graphs.json"
            async with aiofiles.open(call_graphs_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(call_graphs_data, ensure_ascii=False, indent=2))

            config_path = save_path / "config.json"
            async with aiofiles.open(config_path, "w", encoding="utf-8") as f:
                await f.write(self.config.model_dump_json(indent=2))

            logger.info("索引保存成功")
            return True
        except Exception as e:
            logger.error(f"保存索引失败: {e}")
            return False

    async def load_index(self, path: Path | None = None) -> bool:
        """
        从文件加载索引

        从磁盘加载之前保存的索引状态。

        Args:
            path: 加载路径，如果为 None 则使用配置中的路径

        Returns:
            是否成功加载
        """
        load_path = path or self._index_path

        if not load_path.exists():
            logger.warning(f"索引目录不存在: {load_path}")
            return False

        logger.info(f"从 {load_path} 加载索引")

        try:
            vector_store_path = load_path / "vector_store.pkl"
            if vector_store_path.exists():
                self.vector_store.load(vector_store_path)

            chunks_path = load_path / "chunks.json"
            if chunks_path.exists():
                async with aiofiles.open(chunks_path, encoding="utf-8") as f:
                    chunks_data = json.loads(await f.read())
                self.chunks = {
                    chunk_id: CodeChunk.from_dict(chunk_data)
                    for chunk_id, chunk_data in chunks_data.items()
                }

            file_indices_path = load_path / "file_indices.json"
            if file_indices_path.exists():
                async with aiofiles.open(file_indices_path, encoding="utf-8") as f:
                    file_indices_data = json.loads(await f.read())
                self.file_indices = {
                    file_key: FileIndex.from_dict(file_index_data)
                    for file_key, file_index_data in file_indices_data.items()
                }

            call_graphs_path = load_path / "call_graphs.json"
            if call_graphs_path.exists():
                async with aiofiles.open(call_graphs_path, encoding="utf-8") as f:
                    call_graphs_data = json.loads(await f.read())
                self.call_graphs = {
                    func_name: CallGraph(
                        function_name=data["function_name"],
                        file_path=Path(data["file_path"]),
                        callers=data["callers"],
                        callees=data["callees"],
                        complexity=data.get("complexity", 0),
                        metadata=data.get("metadata", {}),
                    )
                    for func_name, data in call_graphs_data.items()
                }

            logger.info(
                f"索引加载成功: {len(self.chunks)} 个代码块, "
                f"{len(self.file_indices)} 个文件, "
                f"{len(self.call_graphs)} 个调用图"
            )
            return True
        except Exception as e:
            logger.error(f"加载索引失败: {e}")
            return False

    def remove_file(self, file_path: Path) -> bool:
        """
        从索引中移除文件

        删除指定文件的所有索引数据。

        Args:
            file_path: 文件路径

        Returns:
            是否成功移除
        """
        file_key = str(file_path.resolve())
        file_index = self.file_indices.get(file_key)

        if not file_index:
            logger.warning(f"文件不在索引中: {file_path}")
            return False

        logger.info(f"从索引中移除文件: {file_path}")

        for chunk in file_index.chunks:
            self.vector_store.remove(chunk.id)
            if chunk.id in self.chunks:
                del self.chunks[chunk.id]

        del self.file_indices[file_key]

        for func_name, call_graph in list(self.call_graphs.items()):
            if call_graph.file_path.resolve() == file_path.resolve():
                del self.call_graphs[func_name]

        logger.info(f"文件 {file_path} 已从索引中移除")
        return True

    def get_statistics(self) -> dict[str, Any]:
        """
        获取索引统计信息

        Returns:
            统计信息字典
        """
        language_counts: dict[str, int] = {}
        chunk_type_counts: dict[str, int] = {}

        for chunk in self.chunks.values():
            lang = chunk.language.value
            language_counts[lang] = language_counts.get(lang, 0) + 1

            chunk_type = chunk.chunk_type
            chunk_type_counts[chunk_type] = chunk_type_counts.get(chunk_type, 0) + 1

        return {
            "total_files": len(self.file_indices),
            "total_chunks": len(self.chunks),
            "total_vectors": len(self.vector_store),
            "total_call_graphs": len(self.call_graphs),
            "languages": language_counts,
            "chunk_types": chunk_type_counts,
            "embedding_model": self.config.embedding_model_name,
            "embedding_dimension": self.config.embedding_dimension,
        }

    def clear(self) -> None:
        """清空所有索引数据"""
        self.vector_store.clear()
        self.chunks.clear()
        self.file_indices.clear()
        self.call_graphs.clear()
        logger.info("索引已清空")


async def main() -> None:
    """测试入口"""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    config = SemanticIndexConfig(
        embedding_model_type=EmbeddingModelType.LOCAL,
        embedding_model_name="all-MiniLM-L6-v2",
        embedding_dimension=384,
    )

    index = SemanticCodeIndex(config)

    test_dir = Path(__file__).parent
    count = await index.index_directory(test_dir)
    print(f"索引了 {count} 个文件")

    results = await index.search("查找配置相关的代码")
    for result in results:
        print(f"\n分数: {result.score:.4f}")
        print(f"文件: {result.chunk.file_path}")
        print(f"名称: {result.chunk.name}")
        print(f"类型: {result.chunk.chunk_type}")
        print(f"内容预览: {result.chunk.content[:100]}...")

    stats = index.get_statistics()
    print(f"\n统计信息: {json.dumps(stats, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    asyncio.run(main())
