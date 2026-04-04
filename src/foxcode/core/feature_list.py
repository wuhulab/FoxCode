"""
FoxCode 功能列表管理模块

管理功能需求列表，支持功能的添加、更新、验证和持久化
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class FeatureStatus(str, Enum):
    """功能状态枚举"""
    PENDING = "pending"           # 待处理
    IN_PROGRESS = "in_progress"   # 进行中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
    BLOCKED = "blocked"           # 阻塞


class FeaturePriority(str, Enum):
    """功能优先级枚举"""
    CRITICAL = "critical"   # 关键
    HIGH = "high"           # 高
    MEDIUM = "medium"       # 中
    LOW = "low"             # 低


@dataclass
class Feature:
    """
    单个功能项数据结构
    
    Attributes:
        id: 功能唯一标识符，如 FEATURE-001
        title: 功能标题
        description: 功能详细描述
        status: 功能状态
        priority: 优先级
        category: 功能分类
        acceptance_criteria: 验收标准列表
        dependencies: 依赖的其他功能 ID 列表
        created_at: 创建时间
        updated_at: 更新时间
        completed_at: 完成时间
        verification: 验证结果
        notes: 备注信息
    """
    id: str
    title: str
    description: str = ""
    status: FeatureStatus = FeatureStatus.PENDING
    priority: FeaturePriority = FeaturePriority.MEDIUM
    category: str = "核心功能"
    acceptance_criteria: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    verification: str = ""
    notes: str = ""
    
    def __post_init__(self) -> None:
        """初始化后处理，确保时间字段为 datetime 类型"""
        if isinstance(self.created_at, str):
            self.created_at = datetime.fromisoformat(self.created_at)
        if isinstance(self.updated_at, str):
            self.updated_at = datetime.fromisoformat(self.updated_at)
        if self.completed_at and isinstance(self.completed_at, str):
            self.completed_at = datetime.fromisoformat(self.completed_at)
    
    def to_dict(self) -> dict[str, Any]:
        """
        将功能项转换为字典
        
        Returns:
            包含功能项所有属性的字典
        """
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "category": self.category,
            "acceptance_criteria": self.acceptance_criteria,
            "dependencies": self.dependencies,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "verification": self.verification,
            "notes": self.notes,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Feature":
        """
        从字典创建功能项
        
        Args:
            data: 包含功能项属性的字典
            
        Returns:
            功能项实例
        """
        return cls(
            id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            status=FeatureStatus(data.get("status", "pending")),
            priority=FeaturePriority(data.get("priority", "medium")),
            category=data.get("category", "核心功能"),
            acceptance_criteria=data.get("acceptance_criteria", []),
            dependencies=data.get("dependencies", []),
            created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data.get("created_at"), str) else data.get("created_at", datetime.now()),
            updated_at=datetime.fromisoformat(data["updated_at"]) if isinstance(data.get("updated_at"), str) else data.get("updated_at", datetime.now()),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            verification=data.get("verification", ""),
            notes=data.get("notes", ""),
        )
    
    def is_completed(self) -> bool:
        """检查功能是否已完成"""
        return self.status == FeatureStatus.COMPLETED
    
    def is_pending(self) -> bool:
        """检查功能是否待处理"""
        return self.status == FeatureStatus.PENDING
    
    def is_in_progress(self) -> bool:
        """检查功能是否进行中"""
        return self.status == FeatureStatus.IN_PROGRESS


class FeatureList:
    """
    功能列表管理类
    
    管理功能需求列表，支持创建、加载、更新和导出功能列表
    """
    
    def __init__(self, file_path: Path | None = None):
        """
        初始化功能列表
        
        Args:
            file_path: 功能列表文件路径，默认为 .foxcode/features.md
        """
        self.file_path = file_path or Path.cwd() / ".foxcode" / "features.md"
        self.features: dict[str, Feature] = {}
        self.metadata: dict[str, Any] = {
            "project_name": "",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "version": "1.0",
        }
        logger.debug(f"功能列表管理器初始化完成，文件路径: {self.file_path}")
    
    def add_feature(
        self,
        feature_id: str,
        title: str,
        description: str = "",
        priority: FeaturePriority = FeaturePriority.MEDIUM,
        category: str = "核心功能",
        acceptance_criteria: list[str] | None = None,
        dependencies: list[str] | None = None,
        notes: str = "",
    ) -> Feature:
        """
        添加新功能
        
        Args:
            feature_id: 功能唯一标识符
            title: 功能标题
            description: 功能描述
            priority: 优先级
            category: 分类
            acceptance_criteria: 验收标准
            dependencies: 依赖项
            notes: 备注
            
        Returns:
            创建的功能项
            
        Raises:
            ValueError: 功能 ID 已存在
        """
        if feature_id in self.features:
            logger.error(f"功能 ID 已存在: {feature_id}")
            raise ValueError(f"功能 ID 已存在: {feature_id}")
        
        feature = Feature(
            id=feature_id,
            title=title,
            description=description,
            priority=priority,
            category=category,
            acceptance_criteria=acceptance_criteria or [],
            dependencies=dependencies or [],
            notes=notes,
        )
        
        self.features[feature_id] = feature
        self._update_timestamp()
        logger.info(f"已添加功能: {feature_id} - {title}")
        
        return feature
    
    def update_status(
        self,
        feature_id: str,
        status: FeatureStatus,
        verification: str = "",
    ) -> Feature:
        """
        更新功能状态
        
        Args:
            feature_id: 功能 ID
            status: 新状态
            verification: 验证结果
            
        Returns:
            更新后的功能项
            
        Raises:
            KeyError: 功能不存在
        """
        if feature_id not in self.features:
            logger.error(f"功能不存在: {feature_id}")
            raise KeyError(f"功能不存在: {feature_id}")
        
        feature = self.features[feature_id]
        old_status = feature.status
        feature.status = status
        feature.updated_at = datetime.now()
        
        if verification:
            feature.verification = verification
        
        if status == FeatureStatus.COMPLETED:
            feature.completed_at = datetime.now()
            logger.info(f"功能 {feature_id} 已标记为完成")
        else:
            logger.info(f"功能 {feature_id} 状态从 {old_status.value} 更新为 {status.value}")
        
        self._update_timestamp()
        return feature
    
    def mark_completed(self, feature_id: str, verification: str = "") -> Feature:
        """
        标记功能为已完成
        
        Args:
            feature_id: 功能 ID
            verification: 验证结果
            
        Returns:
            更新后的功能项
        """
        return self.update_status(feature_id, FeatureStatus.COMPLETED, verification)
    
    def mark_in_progress(self, feature_id: str) -> Feature:
        """
        标记功能为进行中
        
        Args:
            feature_id: 功能 ID
            
        Returns:
            更新后的功能项
        """
        return self.update_status(feature_id, FeatureStatus.IN_PROGRESS)
    
    def mark_failed(self, feature_id: str, reason: str = "") -> Feature:
        """
        标记功能为失败
        
        Args:
            feature_id: 功能 ID
            reason: 失败原因
            
        Returns:
            更新后的功能项
        """
        return self.update_status(feature_id, FeatureStatus.FAILED, reason)
    
    def get_feature(self, feature_id: str) -> Feature | None:
        """
        获取指定功能
        
        Args:
            feature_id: 功能 ID
            
        Returns:
            功能项，不存在则返回 None
        """
        return self.features.get(feature_id)
    
    def get_pending_features(self) -> list[Feature]:
        """
        获取所有待处理功能
        
        Returns:
            待处理功能列表，按优先级排序
        """
        pending = [f for f in self.features.values() if f.is_pending()]
        return self._sort_by_priority(pending)
    
    def get_in_progress_features(self) -> list[Feature]:
        """
        获取所有进行中的功能
        
        Returns:
            进行中功能列表
        """
        return [f for f in self.features.values() if f.is_in_progress()]
    
    def get_completed_features(self) -> list[Feature]:
        """
        获取所有已完成功能
        
        Returns:
            已完成功能列表
        """
        return [f for f in self.features.values() if f.is_completed()]
    
    def get_next_feature(self) -> Feature | None:
        """
        获取下一个建议处理的功能
        
        优先选择进行中的功能，其次选择高优先级的待处理功能
        
        Returns:
            建议的功能项，如果没有则返回 None
        """
        # 优先返回进行中的功能
        in_progress = self.get_in_progress_features()
        if in_progress:
            return in_progress[0]
        
        # 返回最高优先级的待处理功能
        pending = self.get_pending_features()
        if pending:
            # 检查依赖是否满足
            for feature in pending:
                if self._check_dependencies(feature):
                    return feature
        
        return None
    
    def get_features_by_category(self, category: str) -> list[Feature]:
        """
        获取指定分类的功能
        
        Args:
            category: 分类名称
            
        Returns:
            该分类下的功能列表
        """
        return [f for f in self.features.values() if f.category == category]
    
    def get_categories(self) -> list[str]:
        """
        获取所有分类
        
        Returns:
            分类列表
        """
        return list(set(f.category for f in self.features.values()))
    
    def get_statistics(self) -> dict[str, Any]:
        """
        获取功能统计信息
        
        Returns:
            统计信息字典
        """
        total = len(self.features)
        if total == 0:
            return {
                "total": 0,
                "pending": 0,
                "in_progress": 0,
                "completed": 0,
                "failed": 0,
                "blocked": 0,
                "completion_rate": 0.0,
            }
        
        status_counts = {
            FeatureStatus.PENDING: 0,
            FeatureStatus.IN_PROGRESS: 0,
            FeatureStatus.COMPLETED: 0,
            FeatureStatus.FAILED: 0,
            FeatureStatus.BLOCKED: 0,
        }
        
        for feature in self.features.values():
            status_counts[feature.status] += 1
        
        return {
            "total": total,
            "pending": status_counts[FeatureStatus.PENDING],
            "in_progress": status_counts[FeatureStatus.IN_PROGRESS],
            "completed": status_counts[FeatureStatus.COMPLETED],
            "failed": status_counts[FeatureStatus.FAILED],
            "blocked": status_counts[FeatureStatus.BLOCKED],
            "completion_rate": round(status_counts[FeatureStatus.COMPLETED] / total * 100, 2),
        }
    
    def create(self, project_name: str = "") -> None:
        """
        创建新的功能列表文件
        
        Args:
            project_name: 项目名称
        """
        self.metadata["project_name"] = project_name
        self.metadata["created_at"] = datetime.now().isoformat()
        self._update_timestamp()
        
        # 确保目录存在
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.save()
        logger.info(f"已创建功能列表文件: {self.file_path}")
    
    def load(self) -> None:
        """
        加载现有功能列表文件
        
        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 文件格式错误
        """
        if not self.file_path.exists():
            logger.error(f"功能列表文件不存在: {self.file_path}")
            raise FileNotFoundError(f"功能列表文件不存在: {self.file_path}")
        
        try:
            content = self.file_path.read_text(encoding="utf-8")
            self.from_markdown(content)
            logger.info(f"已加载功能列表: {self.file_path}")
        except Exception as e:
            logger.error(f"加载功能列表失败: {e}")
            raise
    
    def save(self) -> None:
        """
        保存功能列表到文件
        """
        try:
            content = self.to_markdown()
            self.file_path.write_text(content, encoding="utf-8")
            logger.debug(f"功能列表已保存: {self.file_path}")
        except Exception as e:
            logger.error(f"保存功能列表失败: {e}")
            raise
    
    def to_markdown(self) -> str:
        """
        导出为 Markdown 格式
        
        Returns:
            Markdown 格式的功能列表
        """
        lines = [
            "# 功能需求列表",
            "",
            f"> 项目: {self.metadata.get('project_name', '未命名')}",
            f"> 创建时间: {self.metadata.get('created_at', '')}",
            f"> 更新时间: {self.metadata.get('updated_at', '')}",
            "",
            "## 统计信息",
            "",
        ]
        
        stats = self.get_statistics()
        lines.extend([
            f"- 总计: {stats['total']} 个功能",
            f"- 待处理: {stats['pending']} 个",
            f"- 进行中: {stats['in_progress']} 个",
            f"- 已完成: {stats['completed']} 个",
            f"- 完成率: {stats['completion_rate']}%",
            "",
        ])
        
        # 按分类组织功能
        categories = self.get_categories()
        for category in categories:
            features = self.get_features_by_category(category)
            lines.append(f"## {category}")
            lines.append("")
            
            for feature in features:
                # 状态标记
                checkbox = "[x]" if feature.is_completed() else "[ ]"
                
                lines.append(f"- {checkbox} {feature.id}: {feature.title}")
                lines.append(f"  - 状态: {feature.status.value}")
                lines.append(f"  - 优先级: {feature.priority.value}")
                
                if feature.description:
                    lines.append(f"  - 描述: {feature.description}")
                
                if feature.acceptance_criteria:
                    lines.append("  - 验收标准:")
                    for criteria in feature.acceptance_criteria:
                        lines.append(f"    - {criteria}")
                
                if feature.dependencies:
                    lines.append(f"  - 依赖: {', '.join(feature.dependencies)}")
                
                if feature.completed_at:
                    lines.append(f"  - 完成时间: {feature.completed_at.isoformat()}")
                
                if feature.verification:
                    lines.append(f"  - 验证: {feature.verification}")
                
                if feature.notes:
                    lines.append(f"  - 备注: {feature.notes}")
                
                lines.append("")
        
        return "\n".join(lines)
    
    def from_markdown(self, content: str) -> None:
        """
        从 Markdown 格式导入
        
        Args:
            content: Markdown 格式的功能列表内容
            
        Raises:
            ValueError: 格式错误
        """
        try:
            lines = content.split("\n")
            current_category = "核心功能"
            current_feature: dict[str, Any] | None = None
            features_data: list[dict[str, Any]] = []
            
            # 解析元数据
            for line in lines:
                if line.startswith("> 项目:"):
                    self.metadata["project_name"] = line.split(":", 1)[1].strip()
                elif line.startswith("> 创建时间:"):
                    self.metadata["created_at"] = line.split(":", 1)[1].strip()
                elif line.startswith("> 更新时间:"):
                    self.metadata["updated_at"] = line.split(":", 1)[1].strip()
            
            # 解析功能项
            for line in lines:
                line = line.rstrip()
                
                # 分类标题
                if line.startswith("## ") and not line.startswith("## 统计"):
                    if current_feature:
                        features_data.append(current_feature)
                        current_feature = None
                    current_category = line[3:].strip()
                    continue
                
                # 功能项开始
                feature_match = re.match(r"- \[([ x])\] ([A-Z]+-\d+): (.+)", line)
                if feature_match:
                    if current_feature:
                        features_data.append(current_feature)
                    
                    is_completed = feature_match.group(1) == "x"
                    feature_id = feature_match.group(2)
                    title = feature_match.group(3)
                    
                    current_feature = {
                        "id": feature_id,
                        "title": title,
                        "status": "completed" if is_completed else "pending",
                        "category": current_category,
                        "acceptance_criteria": [],
                        "dependencies": [],
                    }
                    continue
                
                # 功能属性
                if current_feature:
                    if line.strip().startswith("- 状态:"):
                        current_feature["status"] = line.split(":", 1)[1].strip()
                    elif line.strip().startswith("- 优先级:"):
                        current_feature["priority"] = line.split(":", 1)[1].strip()
                    elif line.strip().startswith("- 描述:"):
                        current_feature["description"] = line.split(":", 1)[1].strip()
                    elif line.strip().startswith("- 完成时间:"):
                        current_feature["completed_at"] = line.split(":", 1)[1].strip()
                    elif line.strip().startswith("- 验证:"):
                        current_feature["verification"] = line.split(":", 1)[1].strip()
                    elif line.strip().startswith("- 备注:"):
                        current_feature["notes"] = line.split(":", 1)[1].strip()
                    elif line.strip().startswith("- 依赖:"):
                        deps = line.split(":", 1)[1].strip()
                        current_feature["dependencies"] = [d.strip() for d in deps.split(",")]
                    elif line.strip().startswith("- ") and "验收标准" not in line:
                        # 验收标准项
                        criteria = line.strip()[2:]
                        if criteria and not criteria.startswith("状态") and not criteria.startswith("优先级"):
                            current_feature["acceptance_criteria"].append(criteria)
            
            # 添加最后一个功能
            if current_feature:
                features_data.append(current_feature)
            
            # 创建功能对象
            self.features.clear()
            for data in features_data:
                feature = Feature.from_dict(data)
                self.features[feature.id] = feature
            
            logger.info(f"已从 Markdown 导入 {len(self.features)} 个功能")
            
        except Exception as e:
            logger.error(f"解析 Markdown 失败: {e}")
            raise ValueError(f"解析 Markdown 失败: {e}")
    
    def delete_feature(self, feature_id: str) -> bool:
        """
        删除功能
        
        Args:
            feature_id: 功能 ID
            
        Returns:
            是否删除成功
        """
        if feature_id in self.features:
            del self.features[feature_id]
            self._update_timestamp()
            logger.info(f"已删除功能: {feature_id}")
            return True
        return False
    
    def clear(self) -> None:
        """清空所有功能"""
        self.features.clear()
        self._update_timestamp()
        logger.info("已清空功能列表")
    
    def _update_timestamp(self) -> None:
        """更新时间戳"""
        self.metadata["updated_at"] = datetime.now().isoformat()
    
    def _sort_by_priority(self, features: list[Feature]) -> list[Feature]:
        """
        按优先级排序功能
        
        Args:
            features: 功能列表
            
        Returns:
            排序后的功能列表
        """
        priority_order = {
            FeaturePriority.CRITICAL: 0,
            FeaturePriority.HIGH: 1,
            FeaturePriority.MEDIUM: 2,
            FeaturePriority.LOW: 3,
        }
        return sorted(features, key=lambda f: priority_order.get(f.priority, 2))
    
    def _check_dependencies(self, feature: Feature) -> bool:
        """
        检查功能依赖是否满足
        
        Args:
            feature: 功能项
            
        Returns:
            依赖是否满足
        """
        for dep_id in feature.dependencies:
            dep_feature = self.features.get(dep_id)
            if not dep_feature or not dep_feature.is_completed():
                return False
        return True
    
    # ==================== 异步方法 ====================
    
    async def add_feature_async(self, *args: Any, **kwargs: Any) -> Feature:
        """
        异步添加功能
        
        Returns:
            创建的功能项
        """
        return await asyncio.to_thread(self.add_feature, *args, **kwargs)
    
    async def update_status_async(
        self,
        feature_id: str,
        status: FeatureStatus,
        verification: str = "",
    ) -> Feature:
        """
        异步更新功能状态
        
        Returns:
            更新后的功能项
        """
        return await asyncio.to_thread(self.update_status, feature_id, status, verification)
    
    async def load_async(self) -> None:
        """异步加载功能列表"""
        await asyncio.to_thread(self.load)
    
    async def save_async(self) -> None:
        """异步保存功能列表"""
        await asyncio.to_thread(self.save)
    
    async def get_next_feature_async(self) -> Feature | None:
        """
        异步获取下一个建议功能
        
        Returns:
            建议的功能项
        """
        return await asyncio.to_thread(self.get_next_feature)
    
    def __len__(self) -> int:
        """返回功能数量"""
        return len(self.features)
    
    def __contains__(self, feature_id: str) -> bool:
        """检查功能是否存在"""
        return feature_id in self.features
    
    def __iter__(self):
        """迭代功能项"""
        return iter(self.features.values())
    
    def __repr__(self) -> str:
        """字符串表示"""
        stats = self.get_statistics()
        return (
            f"FeatureList("
            f"total={stats['total']}, "
            f"pending={stats['pending']}, "
            f"in_progress={stats['in_progress']}, "
            f"completed={stats['completed']})"
        )
