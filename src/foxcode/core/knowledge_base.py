"""
FoxCode 知识库管理系统

提供知识的存储、检索、分类和共享功能。
支持知识向量化和语义检索，实现跨会话知识共享。

主要功能：
- 知识存储和检索
- 知识分类和标签系统
- 知识向量化和语义检索
- 知识过期和更新机制
- 跨会话知识共享
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class KnowledgeCategory(str, Enum):
    """知识类别"""
    CODE_PATTERN = "code_pattern"          # 代码模式
    API_USAGE = "api_usage"                # API 使用
    ERROR_SOLUTION = "error_solution"      # 错误解决方案
    BEST_PRACTICE = "best_practice"        # 最佳实践
    PROJECT_SPECIFIC = "project_specific"  # 项目特定
    ARCHITECTURE = "architecture"          # 架构设计
    CONFIGURATION = "configuration"        # 配置相关
    DEPENDENCY = "dependency"              # 依赖相关


class KnowledgePriority(str, Enum):
    """知识优先级"""
    CRITICAL = "critical"    # 关键知识
    HIGH = "high"           # 高优先级
    NORMAL = "normal"       # 普通优先级
    LOW = "low"             # 低优先级


@dataclass
class Knowledge:
    """
    知识数据结构
    
    存储单个知识项的所有信息，包括内容、分类、标签、来源等。
    
    Attributes:
        id: 知识唯一标识符
        content: 知识内容
        title: 知识标题
        category: 知识类别
        tags: 标签列表
        priority: 优先级
        source: 知识来源（文件路径、会话ID等）
        created_at: 创建时间
        updated_at: 更新时间
        expires_at: 过期时间（可选）
        access_count: 访问次数
        embedding: 向量嵌入（可选）
        metadata: 额外元数据
    """
    id: str
    content: str
    title: str = ""
    category: KnowledgeCategory = KnowledgeCategory.PROJECT_SPECIFIC
    tags: list[str] = field(default_factory=list)
    priority: KnowledgePriority = KnowledgePriority.NORMAL
    source: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime | None = None
    access_count: int = 0
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "content": self.content,
            "title": self.title,
            "category": self.category.value,
            "tags": self.tags,
            "priority": self.priority.value,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "access_count": self.access_count,
            "embedding": self.embedding,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Knowledge":
        """从字典创建"""
        data["category"] = KnowledgeCategory(data["category"])
        data["priority"] = KnowledgePriority(data["priority"])
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if data.get("expires_at"):
            data["expires_at"] = datetime.fromisoformat(data["expires_at"])
        return cls(**data)
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    def touch(self) -> None:
        """更新访问时间和计数"""
        self.access_count += 1
        self.updated_at = datetime.now()


class KnowledgeBaseConfig(BaseModel):
    """
    知识库配置
    
    Attributes:
        storage_path: 知识库存储路径
        max_knowledge_items: 最大知识项数量
        default_expiry_days: 默认过期天数（0 表示永不过期）
        enable_embeddings: 是否启用向量嵌入
        embedding_model: 嵌入模型名称
        auto_expire: 是否自动清理过期知识
        similarity_threshold: 语义检索相似度阈值
    """
    storage_path: str = ".foxcode/knowledge_base"
    max_knowledge_items: int = Field(default=10000, ge=100)
    default_expiry_days: int = Field(default=0, ge=0)
    enable_embeddings: bool = True
    embedding_model: str = "text-embedding-3-small"
    auto_expire: bool = True
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class KnowledgeBase:
    """
    知识库管理系统
    
    提供知识的存储、检索、分类和共享功能。
    支持向量化和语义检索，实现跨会话知识共享。
    
    Example:
        >>> config = KnowledgeBaseConfig(storage_path="./knowledge")
        >>> kb = KnowledgeBase(config)
        >>> knowledge = Knowledge(
        ...     id="kb-001",
        ...     content="使用 asyncio.gather 并发执行多个协程",
        ...     title="asyncio 并发模式",
        ...     category=KnowledgeCategory.CODE_PATTERN,
        ...     tags=["asyncio", "concurrency", "python"]
        ... )
        >>> await kb.store(knowledge)
        >>> results = await kb.retrieve("如何实现并发")
    """
    
    def __init__(self, config: KnowledgeBaseConfig | None = None):
        """
        初始化知识库
        
        Args:
            config: 知识库配置，None 则使用默认配置
        """
        self.config = config or KnowledgeBaseConfig()
        self._knowledge: dict[str, Knowledge] = {}
        self._tag_index: dict[str, set[str]] = {}  # tag -> knowledge_ids
        self._category_index: dict[KnowledgeCategory, set[str]] = {}  # category -> knowledge_ids
        self._session_shares: dict[str, set[str]] = {}  # session_id -> knowledge_ids
        self._embedding_model = None
        self._initialized = False
        
        self._ensure_storage_dir()
        logger.info(f"知识库初始化完成，存储路径: {self.config.storage_path}")
    
    def _ensure_storage_dir(self) -> None:
        """确保存储目录存在"""
        storage_path = Path(self.config.storage_path)
        storage_path.mkdir(parents=True, exist_ok=True)
    
    async def initialize(self) -> None:
        """
        异步初始化知识库
        
        加载已有知识，初始化嵌入模型
        """
        if self._initialized:
            return
        
        try:
            # 加载已有知识
            await self._load_knowledge()
            
            # 初始化嵌入模型
            if self.config.enable_embeddings:
                await self._init_embedding_model()
            
            self._initialized = True
            logger.info(f"知识库异步初始化完成，已加载 {len(self._knowledge)} 条知识")
            
        except Exception as e:
            logger.error(f"知识库初始化失败: {e}")
            raise
    
    async def _init_embedding_model(self) -> None:
        """初始化嵌入模型"""
        try:
            # 尝试使用 OpenAI 嵌入
            import openai
            self._embedding_model = "openai"
            logger.debug("使用 OpenAI 嵌入模型")
        except ImportError:
            # 尝试使用本地模型
            try:
                from sentence_transformers import SentenceTransformer
                self._embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                logger.debug("使用本地嵌入模型")
            except ImportError:
                logger.warning("未找到嵌入模型，语义检索功能将受限")
                self._embedding_model = None
    
    async def _load_knowledge(self) -> None:
        """从存储加载知识"""
        storage_path = Path(self.config.storage_path)
        knowledge_file = storage_path / "knowledge.json"
        
        if not knowledge_file.exists():
            return
        
        try:
            with open(knowledge_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for item in data.get("knowledge", []):
                knowledge = Knowledge.from_dict(item)
                self._knowledge[knowledge.id] = knowledge
                self._update_indexes(knowledge)
            
            logger.info(f"已加载 {len(self._knowledge)} 条知识")
            
        except Exception as e:
            logger.error(f"加载知识失败: {e}")
    
    def _update_indexes(self, knowledge: Knowledge) -> None:
        """更新索引"""
        # 更新标签索引
        for tag in knowledge.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(knowledge.id)
        
        # 更新类别索引
        if knowledge.category not in self._category_index:
            self._category_index[knowledge.category] = set()
        self._category_index[knowledge.category].add(knowledge.id)
    
    def _remove_from_indexes(self, knowledge: Knowledge) -> None:
        """从索引中移除"""
        # 从标签索引移除
        for tag in knowledge.tags:
            if tag in self._tag_index:
                self._tag_index[tag].discard(knowledge.id)
        
        # 从类别索引移除
        if knowledge.category in self._category_index:
            self._category_index[knowledge.category].discard(knowledge.id)
    
    async def _generate_embedding(self, text: str) -> list[float] | None:
        """
        生成文本嵌入向量
        
        Args:
            text: 要嵌入的文本
            
        Returns:
            嵌入向量，失败返回 None
        """
        if not self._embedding_model:
            return None
        
        try:
            if self._embedding_model == "openai":
                import openai
                client = openai.OpenAI()
                response = client.embeddings.create(
                    model=self.config.embedding_model,
                    input=text
                )
                return response.data[0].embedding
            else:
                # 本地模型
                embedding = self._embedding_model.encode(text)
                return embedding.tolist()
        except Exception as e:
            logger.warning(f"生成嵌入失败: {e}")
            return None
    
    async def store(self, knowledge: Knowledge) -> str:
        """
        存储知识
        
        Args:
            knowledge: 要存储的知识
            
        Returns:
            知识 ID
        """
        if not self._initialized:
            await self.initialize()
        
        # 检查数量限制
        if len(self._knowledge) >= self.config.max_knowledge_items:
            # 清理最旧或最低优先级的知识
            await self._cleanup_old_knowledge()
        
        # 设置过期时间
        if knowledge.expires_at is None and self.config.default_expiry_days > 0:
            knowledge.expires_at = datetime.now() + timedelta(days=self.config.default_expiry_days)
        
        # 生成嵌入
        if self.config.enable_embeddings and knowledge.embedding is None:
            knowledge.embedding = await self._generate_embedding(knowledge.content)
        
        # 存储
        self._knowledge[knowledge.id] = knowledge
        self._update_indexes(knowledge)
        
        logger.debug(f"存储知识: {knowledge.id} - {knowledge.title}")
        return knowledge.id
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        category: KnowledgeCategory | None = None,
        tags: list[str] | None = None,
    ) -> list[Knowledge]:
        """
        检索知识
        
        Args:
            query: 查询字符串
            top_k: 返回结果数量
            category: 限定类别
            tags: 限定标签
            
        Returns:
            匹配的知识列表
        """
        if not self._initialized:
            await self.initialize()
        
        # 获取候选集
        candidates = self._get_candidates(category, tags)
        
        # 过期检查
        candidates = [k for k in candidates if not k.is_expired()]
        
        # 如果有嵌入模型，使用语义检索
        if self.config.enable_embeddings and self._embedding_model:
            query_embedding = await self._generate_embedding(query)
            if query_embedding:
                results = self._semantic_search(candidates, query_embedding, top_k)
                # 更新访问计数
                for k in results:
                    k.touch()
                return results
        
        # 回退到关键词搜索
        results = self._keyword_search(candidates, query, top_k)
        for k in results:
            k.touch()
        return results
    
    def _get_candidates(
        self,
        category: KnowledgeCategory | None = None,
        tags: list[str] | None = None,
    ) -> list[Knowledge]:
        """获取候选知识集"""
        if category and tags:
            # 取交集
            category_ids = self._category_index.get(category, set())
            tag_ids = set.intersection(*[self._tag_index.get(t, set()) for t in tags])
            ids = category_ids & tag_ids
        elif category:
            ids = self._category_index.get(category, set())
        elif tags:
            ids = set.union(*[self._tag_index.get(t, set()) for t in tags])
        else:
            ids = set(self._knowledge.keys())
        
        return [self._knowledge[kid] for kid in ids if kid in self._knowledge]
    
    def _semantic_search(
        self,
        candidates: list[Knowledge],
        query_embedding: list[float],
        top_k: int,
    ) -> list[Knowledge]:
        """语义搜索"""
        import numpy as np
        
        # 计算相似度
        scores = []
        query_vec = np.array(query_embedding)
        
        for knowledge in candidates:
            if knowledge.embedding:
                knowledge_vec = np.array(knowledge.embedding)
                similarity = np.dot(query_vec, knowledge_vec) / (
                    np.linalg.norm(query_vec) * np.linalg.norm(knowledge_vec)
                )
                scores.append((knowledge, similarity))
        
        # 排序
        scores.sort(key=lambda x: x[1], reverse=True)
        
        # 过滤低相似度结果
        results = [
            k for k, s in scores[:top_k]
            if s >= self.config.similarity_threshold
        ]
        
        return results
    
    def _keyword_search(
        self,
        candidates: list[Knowledge],
        query: str,
        top_k: int,
    ) -> list[Knowledge]:
        """关键词搜索"""
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        scores = []
        for knowledge in candidates:
            content_lower = knowledge.content.lower()
            title_lower = knowledge.title.lower()
            
            # 计算匹配分数
            score = 0
            for word in query_words:
                if word in title_lower:
                    score += 3  # 标题匹配权重更高
                if word in content_lower:
                    score += 1
                if word in knowledge.tags:
                    score += 2  # 标签匹配
            
            scores.append((knowledge, score))
        
        # 排序
        scores.sort(key=lambda x: x[1], reverse=True)
        
        return [k for k, s in scores[:top_k] if s > 0]
    
    def add_tag(self, knowledge_id: str, tag: str) -> bool:
        """
        添加标签
        
        Args:
            knowledge_id: 知识 ID
            tag: 标签
            
        Returns:
            是否成功
        """
        knowledge = self._knowledge.get(knowledge_id)
        if not knowledge:
            return False
        
        if tag not in knowledge.tags:
            knowledge.tags.append(tag)
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(knowledge_id)
            knowledge.updated_at = datetime.now()
        
        return True
    
    def remove_tag(self, knowledge_id: str, tag: str) -> bool:
        """
        移除标签
        
        Args:
            knowledge_id: 知识 ID
            tag: 标签
            
        Returns:
            是否成功
        """
        knowledge = self._knowledge.get(knowledge_id)
        if not knowledge:
            return False
        
        if tag in knowledge.tags:
            knowledge.tags.remove(tag)
            if tag in self._tag_index:
                self._tag_index[tag].discard(knowledge_id)
            knowledge.updated_at = datetime.now()
        
        return True
    
    def get_by_category(self, category: KnowledgeCategory) -> list[Knowledge]:
        """
        按类别获取知识
        
        Args:
            category: 知识类别
            
        Returns:
            该类别的知识列表
        """
        ids = self._category_index.get(category, set())
        return [self._knowledge[kid] for kid in ids if kid in self._knowledge]
    
    def get_by_tag(self, tag: str) -> list[Knowledge]:
        """
        按标签获取知识
        
        Args:
            tag: 标签
            
        Returns:
            包含该标签的知识列表
        """
        ids = self._tag_index.get(tag, set())
        return [self._knowledge[kid] for kid in ids if kid in self._knowledge]
    
    def get(self, knowledge_id: str) -> Knowledge | None:
        """
        获取单个知识
        
        Args:
            knowledge_id: 知识 ID
            
        Returns:
            知识对象，不存在返回 None
        """
        knowledge = self._knowledge.get(knowledge_id)
        if knowledge:
            knowledge.touch()
        return knowledge
    
    def delete(self, knowledge_id: str) -> bool:
        """
        删除知识
        
        Args:
            knowledge_id: 知识 ID
            
        Returns:
            是否成功
        """
        knowledge = self._knowledge.pop(knowledge_id, None)
        if knowledge:
            self._remove_from_indexes(knowledge)
            logger.debug(f"删除知识: {knowledge_id}")
            return True
        return False
    
    def expire_old_knowledge(self, max_age_days: int = 30) -> int:
        """
        清理过期知识
        
        Args:
            max_age_days: 最大保留天数
            
        Returns:
            清理的知识数量
        """
        cutoff = datetime.now() - timedelta(days=max_age_days)
        expired_ids = []
        
        for kid, knowledge in self._knowledge.items():
            if knowledge.is_expired() or knowledge.updated_at < cutoff:
                expired_ids.append(kid)
        
        for kid in expired_ids:
            self.delete(kid)
        
        if expired_ids:
            logger.info(f"清理了 {len(expired_ids)} 条过期知识")
        
        return len(expired_ids)
    
    async def _cleanup_old_knowledge(self) -> None:
        """清理旧知识以腾出空间"""
        # 按优先级和访问时间排序
        items = list(self._knowledge.items())
        items.sort(key=lambda x: (
            # 优先级排序：LOW < NORMAL < HIGH < CRITICAL
            {"low": 0, "normal": 1, "high": 2, "critical": 3}.get(x[1].priority.value, 1),
            # 访问时间
            x[1].access_count,
            x[1].updated_at,
        ))
        
        # 删除 10% 的低优先级知识
        to_remove = max(1, len(items) // 10)
        for kid, _ in items[:to_remove]:
            self.delete(kid)
        
        logger.info(f"清理了 {to_remove} 条低优先级知识")
    
    async def share_to_session(self, knowledge_id: str, session_id: str) -> bool:
        """
        共享知识到会话
        
        Args:
            knowledge_id: 知识 ID
            session_id: 会话 ID
            
        Returns:
            是否成功
        """
        if knowledge_id not in self._knowledge:
            return False
        
        if session_id not in self._session_shares:
            self._session_shares[session_id] = set()
        
        self._session_shares[session_id].add(knowledge_id)
        logger.debug(f"共享知识 {knowledge_id} 到会话 {session_id}")
        return True
    
    def get_session_knowledge(self, session_id: str) -> list[Knowledge]:
        """
        获取会话共享的知识
        
        Args:
            session_id: 会话 ID
            
        Returns:
            共享的知识列表
        """
        ids = self._session_shares.get(session_id, set())
        return [self._knowledge[kid] for kid in ids if kid in self._knowledge]
    
    async def save(self) -> bool:
        """
        保存知识库
        
        Returns:
            是否成功
        """
        storage_path = Path(self.config.storage_path)
        knowledge_file = storage_path / "knowledge.json"
        
        try:
            data = {
                "knowledge": [k.to_dict() for k in self._knowledge.values()],
                "session_shares": {
                    sid: list(kids) for sid, kids in self._session_shares.items()
                },
                "metadata": {
                    "saved_at": datetime.now().isoformat(),
                    "total_count": len(self._knowledge),
                }
            }
            
            with open(knowledge_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"知识库已保存，共 {len(self._knowledge)} 条知识")
            return True
            
        except Exception as e:
            logger.error(f"保存知识库失败: {e}")
            return False
    
    def get_statistics(self) -> dict[str, Any]:
        """
        获取知识库统计信息
        
        Returns:
            统计信息字典
        """
        categories = {}
        for cat in KnowledgeCategory:
            categories[cat.value] = len(self._category_index.get(cat, set()))
        
        return {
            "total_knowledge": len(self._knowledge),
            "total_tags": len(self._tag_index),
            "categories": categories,
            "shared_sessions": len(self._session_shares),
            "storage_path": str(self.config.storage_path),
        }


# 创建默认知识库实例
knowledge_base = KnowledgeBase()
