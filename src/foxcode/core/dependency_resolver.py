"""
FoxCode 依赖关系解析器

提供多语言依赖解析、版本冲突检测和过时依赖检测功能。

主要功能：
- Python 依赖解析 (requirements.txt, pyproject.toml)
- Node.js 依赖解析 (package.json)
- 依赖版本冲突检测
- 过时依赖检测
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DependencyType(str, Enum):
    """依赖类型"""
    PRODUCTION = "production"    # 生产依赖
    DEVELOPMENT = "development"  # 开发依赖
    OPTIONAL = "optional"        # 可选依赖
    PEER = "peer"               # 同级依赖


class Language(str, Enum):
    """编程语言"""
    PYTHON = "python"
    NODEJS = "nodejs"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    UNKNOWN = "unknown"


@dataclass
class Dependency:
    """
    依赖项
    
    Attributes:
        name: 包名
        version: 版本约束
        version_resolved: 已解析的版本
        dependency_type: 依赖类型
        source: 来源文件
        is_direct: 是否直接依赖
        extras: 额外特性
        markers: 环境标记
    """
    name: str
    version: str = ""
    version_resolved: str = ""
    dependency_type: DependencyType = DependencyType.PRODUCTION
    source: str = ""
    is_direct: bool = True
    extras: list[str] = field(default_factory=list)
    markers: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "version_resolved": self.version_resolved,
            "dependency_type": self.dependency_type.value,
            "source": self.source,
            "is_direct": self.is_direct,
            "extras": self.extras,
            "markers": self.markers,
        }


@dataclass
class Conflict:
    """
    版本冲突
    
    Attributes:
        package: 包名
        required_versions: 需求版本列表
        conflict_type: 冲突类型
        description: 描述
        resolution: 解决方案建议
    """
    package: str
    required_versions: list[tuple[str, str]] = field(default_factory=list)  # (source, version)
    conflict_type: str = "version"
    description: str = ""
    resolution: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "package": self.package,
            "required_versions": self.required_versions,
            "conflict_type": self.conflict_type,
            "description": self.description,
            "resolution": self.resolution,
        }


@dataclass
class OutdatedPackage:
    """
    过时包
    
    Attributes:
        name: 包名
        current_version: 当前版本
        latest_version: 最新版本
        wanted_version: 兼容的最新版本
        deprecated: 是否已弃用
        security_issue: 是否有安全问题
    """
    name: str
    current_version: str
    latest_version: str = ""
    wanted_version: str = ""
    deprecated: bool = False
    security_issue: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "current_version": self.current_version,
            "latest_version": self.latest_version,
            "wanted_version": self.wanted_version,
            "deprecated": self.deprecated,
            "security_issue": self.security_issue,
        }


@dataclass
class DependencyReport:
    """
    依赖报告
    
    Attributes:
        project_path: 项目路径
        language: 语言
        dependencies: 依赖列表
        conflicts: 冲突列表
        outdated: 过时包列表
        total_count: 总数
        production_count: 生产依赖数
        development_count: 开发依赖数
        scan_time: 扫描时间
    """
    project_path: str = ""
    language: Language = Language.UNKNOWN
    dependencies: list[Dependency] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    outdated: list[OutdatedPackage] = field(default_factory=list)
    total_count: int = 0
    production_count: int = 0
    development_count: int = 0
    scan_time: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "project_path": self.project_path,
            "language": self.language.value,
            "dependencies": [d.to_dict() for d in self.dependencies],
            "conflicts": [c.to_dict() for c in self.conflicts],
            "outdated": [o.to_dict() for o in self.outdated],
            "total_count": self.total_count,
            "production_count": self.production_count,
            "development_count": self.development_count,
            "scan_time": self.scan_time.isoformat(),
        }


class DependencyConfig(BaseModel):
    """
    依赖解析配置
    
    Attributes:
        check_outdated: 是否检查过时依赖
        check_vulnerabilities: 是否检查漏洞
        include_transitive: 是否包含传递依赖
        registry_url: 包仓库 URL
    """
    check_outdated: bool = True
    check_vulnerabilities: bool = True
    include_transitive: bool = False
    registry_url: str = ""


class DependencyResolver:
    """
    依赖关系解析器
    
    提供多语言依赖解析、版本冲突检测和过时依赖检测功能。
    
    Example:
        >>> resolver = DependencyResolver()
        >>> report = await resolver.resolve_project(Path("./myproject"))
        >>> print(f"发现 {len(report.dependencies)} 个依赖")
    """
    
    # 版本比较操作符
    VERSION_OPERATORS = [">=", "<=", "==", "!=", "~=", ">", "<", "==="]
    
    def __init__(self, config: DependencyConfig | None = None):
        """
        初始化解析器
        
        Args:
            config: 解析配置
        """
        self.config = config or DependencyConfig()
        logger.info("依赖关系解析器初始化完成")
    
    async def resolve_project(self, project_path: Path) -> DependencyReport:
        """
        解析项目依赖
        
        Args:
            project_path: 项目路径
            
        Returns:
            依赖报告
        """
        report = DependencyReport(project_path=str(project_path))
        
        # 检测项目类型
        language = self._detect_language(project_path)
        report.language = language
        
        # 根据语言解析依赖
        if language == Language.PYTHON:
            await self._resolve_python(project_path, report)
        elif language == Language.NODEJS:
            await self._resolve_nodejs(project_path, report)
        elif language == Language.GO:
            await self._resolve_go(project_path, report)
        elif language == Language.RUST:
            await self._resolve_rust(project_path, report)
        
        # 检测冲突
        report.conflicts = self.detect_conflicts(report.dependencies)
        
        # 检查过时依赖
        if self.config.check_outdated:
            report.outdated = await self.check_outdated(report.dependencies)
        
        # 统计
        report.total_count = len(report.dependencies)
        report.production_count = sum(
            1 for d in report.dependencies
            if d.dependency_type == DependencyType.PRODUCTION
        )
        report.development_count = sum(
            1 for d in report.dependencies
            if d.dependency_type == DependencyType.DEVELOPMENT
        )
        
        return report
    
    def _detect_language(self, project_path: Path) -> Language:
        """检测项目语言"""
        # Python 项目标志
        if (project_path / "pyproject.toml").exists():
            return Language.PYTHON
        if (project_path / "requirements.txt").exists():
            return Language.PYTHON
        if (project_path / "setup.py").exists():
            return Language.PYTHON
        
        # Node.js 项目标志
        if (project_path / "package.json").exists():
            return Language.NODEJS
        
        # Go 项目标志
        if (project_path / "go.mod").exists():
            return Language.GO
        
        # Rust 项目标志
        if (project_path / "Cargo.toml").exists():
            return Language.RUST
        
        # Java 项目标志
        if (project_path / "pom.xml").exists():
            return Language.JAVA
        if (project_path / "build.gradle").exists():
            return Language.JAVA
        
        return Language.UNKNOWN
    
    async def _resolve_python(self, project_path: Path, report: DependencyReport) -> None:
        """解析 Python 依赖"""
        # 解析 requirements.txt
        req_file = project_path / "requirements.txt"
        if req_file.exists():
            deps = self.parse_requirements(req_file)
            report.dependencies.extend(deps)
        
        # 解析 pyproject.toml
        pyproject_file = project_path / "pyproject.toml"
        if pyproject_file.exists():
            deps = self.parse_pyproject(pyproject_file)
            report.dependencies.extend(deps)
        
        # 解析 setup.py（简化版）
        setup_file = project_path / "setup.py"
        if setup_file.exists():
            deps = self._parse_setup_py(setup_file)
            report.dependencies.extend(deps)
    
    async def _resolve_nodejs(self, project_path: Path, report: DependencyReport) -> None:
        """解析 Node.js 依赖"""
        pkg_file = project_path / "package.json"
        if pkg_file.exists():
            deps = self.parse_package_json(pkg_file)
            report.dependencies.extend(deps)
    
    async def _resolve_go(self, project_path: Path, report: DependencyReport) -> None:
        """解析 Go 依赖"""
        go_mod = project_path / "go.mod"
        if go_mod.exists():
            deps = self._parse_go_mod(go_mod)
            report.dependencies.extend(deps)
    
    async def _resolve_rust(self, project_path: Path, report: DependencyReport) -> None:
        """解析 Rust 依赖"""
        cargo_toml = project_path / "Cargo.toml"
        if cargo_toml.exists():
            deps = self._parse_cargo_toml(cargo_toml)
            report.dependencies.extend(deps)
    
    def parse_requirements(self, file_path: Path) -> list[Dependency]:
        """
        解析 requirements.txt
        
        Args:
            file_path: 文件路径
            
        Returns:
            依赖列表
        """
        dependencies = []
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    
                    # 跳过空行和注释
                    if not line or line.startswith("#"):
                        continue
                    
                    # 解析依赖
                    dep = self._parse_requirement_line(line)
                    if dep:
                        dep.source = str(file_path)
                        dependencies.append(dep)
                        
        except Exception as e:
            logger.error(f"解析 requirements.txt 失败: {e}")
        
        return dependencies
    
    def _parse_requirement_line(self, line: str) -> Dependency | None:
        """解析单行 requirement"""
        # 处理环境标记
        markers = ""
        if ";" in line:
            line, markers = line.split(";", 1)
            markers = markers.strip()
        
        # 处理 extras
        extras = []
        if "[" in line and "]" in line:
            match = re.match(r"([a-zA-Z0-9_-]+)\[([^\]]+)\]", line)
            if match:
                name = match.group(1)
                extras = [e.strip() for e in match.group(2).split(",")]
                line = name + line[match.end():]
        
        # 解析包名和版本
        for op in self.VERSION_OPERATORS:
            if op in line:
                parts = line.split(op, 1)
                name = parts[0].strip()
                version = op + parts[1].strip()
                return Dependency(
                    name=name,
                    version=version,
                    extras=extras,
                    markers=markers,
                )
        
        # 没有版本约束
        return Dependency(
            name=line.strip(),
            extras=extras,
            markers=markers,
        )
    
    def parse_pyproject(self, file_path: Path) -> list[Dependency]:
        """
        解析 pyproject.toml
        
        Args:
            file_path: 文件路径
            
        Returns:
            依赖列表
        """
        dependencies = []
        
        try:
            import tomli
            with open(file_path, "rb") as f:
                data = tomli.load(f)
            
            # 解析 project.dependencies
            project = data.get("project", {})
            for dep_str in project.get("dependencies", []):
                dep = self._parse_requirement_line(dep_str)
                if dep:
                    dep.source = str(file_path)
                    dependencies.append(dep)
            
            # 解析 project.optional-dependencies
            for group, deps in project.get("optional-dependencies", {}).items():
                for dep_str in deps:
                    dep = self._parse_requirement_line(dep_str)
                    if dep:
                        dep.source = str(file_path)
                        dep.dependency_type = DependencyType.OPTIONAL
                        dependencies.append(dep)
            
            # 解析 tool.poetry.dependencies
            poetry = data.get("tool", {}).get("poetry", {})
            for name, version in poetry.get("dependencies", {}).items():
                if name.lower() == "python":
                    continue
                dep = Dependency(
                    name=name,
                    version=str(version) if version != "*" else "",
                    source=str(file_path),
                )
                dependencies.append(dep)
            
            for name, version in poetry.get("dev-dependencies", {}).items():
                dep = Dependency(
                    name=name,
                    version=str(version) if version != "*" else "",
                    dependency_type=DependencyType.DEVELOPMENT,
                    source=str(file_path),
                )
                dependencies.append(dep)
                
        except ImportError:
            logger.warning("tomli 未安装，无法解析 pyproject.toml")
        except Exception as e:
            logger.error(f"解析 pyproject.toml 失败: {e}")
        
        return dependencies
    
    def _parse_setup_py(self, file_path: Path) -> list[Dependency]:
        """解析 setup.py（简化版）"""
        dependencies = []
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 简单正则匹配 install_requires
            match = re.search(r"install_requires\s*=\s*\[([^\]]+)\]", content)
            if match:
                deps_str = match.group(1)
                for dep_match in re.finditer(r"['\"]([^'\"]+)['\"]", deps_str):
                    dep = self._parse_requirement_line(dep_match.group(1))
                    if dep:
                        dep.source = str(file_path)
                        dependencies.append(dep)
                        
        except Exception as e:
            logger.error(f"解析 setup.py 失败: {e}")
        
        return dependencies
    
    def parse_package_json(self, file_path: Path) -> list[Dependency]:
        """
        解析 package.json
        
        Args:
            file_path: 文件路径
            
        Returns:
            依赖列表
        """
        dependencies = []
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # 生产依赖
            for name, version in data.get("dependencies", {}).items():
                dependencies.append(Dependency(
                    name=name,
                    version=version,
                    dependency_type=DependencyType.PRODUCTION,
                    source=str(file_path),
                ))
            
            # 开发依赖
            for name, version in data.get("devDependencies", {}).items():
                dependencies.append(Dependency(
                    name=name,
                    version=version,
                    dependency_type=DependencyType.DEVELOPMENT,
                    source=str(file_path),
                ))
            
            # 同级依赖
            for name, version in data.get("peerDependencies", {}).items():
                dependencies.append(Dependency(
                    name=name,
                    version=version,
                    dependency_type=DependencyType.PEER,
                    source=str(file_path),
                ))
            
            # 可选依赖
            for name, version in data.get("optionalDependencies", {}).items():
                dependencies.append(Dependency(
                    name=name,
                    version=version,
                    dependency_type=DependencyType.OPTIONAL,
                    source=str(file_path),
                ))
                
        except Exception as e:
            logger.error(f"解析 package.json 失败: {e}")
        
        return dependencies
    
    def _parse_go_mod(self, file_path: Path) -> list[Dependency]:
        """解析 go.mod"""
        dependencies = []
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 匹配 require 块
            require_pattern = r"require\s*\(([^)]+)\)"
            for match in re.finditer(require_pattern, content, re.DOTALL):
                block = match.group(1)
                for line in block.strip().split("\n"):
                    line = line.strip()
                    if line and not line.startswith("//"):
                        parts = line.split()
                        if len(parts) >= 2:
                            dependencies.append(Dependency(
                                name=parts[0],
                                version=parts[1],
                                source=str(file_path),
                            ))
            
            # 匹配单个 require
            single_pattern = r"require\s+(\S+)\s+(\S+)"
            for match in re.finditer(single_pattern, content):
                dependencies.append(Dependency(
                    name=match.group(1),
                    version=match.group(2),
                    source=str(file_path),
                ))
                
        except Exception as e:
            logger.error(f"解析 go.mod 失败: {e}")
        
        return dependencies
    
    def _parse_cargo_toml(self, file_path: Path) -> list[Dependency]:
        """解析 Cargo.toml"""
        dependencies = []
        
        try:
            import tomli
            with open(file_path, "rb") as f:
                data = tomli.load(f)
            
            # 生产依赖
            for name, version in data.get("dependencies", {}).items():
                if isinstance(version, str):
                    dependencies.append(Dependency(
                        name=name,
                        version=version,
                        source=str(file_path),
                    ))
                elif isinstance(version, dict):
                    dependencies.append(Dependency(
                        name=name,
                        version=version.get("version", ""),
                        source=str(file_path),
                    ))
            
            # 开发依赖
            for name, version in data.get("dev-dependencies", {}).items():
                if isinstance(version, str):
                    dependencies.append(Dependency(
                        name=name,
                        version=version,
                        dependency_type=DependencyType.DEVELOPMENT,
                        source=str(file_path),
                    ))
                
        except ImportError:
            logger.warning("tomli 未安装，无法解析 Cargo.toml")
        except Exception as e:
            logger.error(f"解析 Cargo.toml 失败: {e}")
        
        return dependencies
    
    def detect_conflicts(self, dependencies: list[Dependency]) -> list[Conflict]:
        """
        检测版本冲突
        
        Args:
            dependencies: 依赖列表
            
        Returns:
            冲突列表
        """
        conflicts = []
        
        # 按包名分组
        by_name: dict[str, list[Dependency]] = {}
        for dep in dependencies:
            name_lower = dep.name.lower()
            if name_lower not in by_name:
                by_name[name_lower] = []
            by_name[name_lower].append(dep)
        
        # 检查冲突
        for name, deps in by_name.items():
            if len(deps) > 1:
                versions = [(d.source, d.version) for d in deps if d.version]
                unique_versions = set(v for _, v in versions)
                
                if len(unique_versions) > 1:
                    conflicts.append(Conflict(
                        package=name,
                        required_versions=versions,
                        conflict_type="version",
                        description=f"包 '{name}' 有多个版本要求",
                        resolution=f"统一 '{name}' 的版本要求，建议使用兼容版本范围",
                    ))
        
        return conflicts
    
    async def check_outdated(self, dependencies: list[Dependency]) -> list[OutdatedPackage]:
        """
        检查过时依赖
        
        Args:
            dependencies: 依赖列表
            
        Returns:
            过时包列表
        """
        outdated = []
        
        # 模拟检查（实际应该调用包仓库 API）
        known_latest = {
            # Python 包
            "django": "4.2.0",
            "flask": "3.0.0",
            "requests": "2.31.0",
            "numpy": "1.26.0",
            "pandas": "2.1.0",
            "pytest": "7.4.0",
            "black": "23.0.0",
            "ruff": "0.1.0",
            # Node.js 包
            "express": "4.18.0",
            "react": "18.2.0",
            "vue": "3.3.0",
            "typescript": "5.2.0",
            "lodash": "4.17.21",
            "axios": "1.5.0",
        }
        
        for dep in dependencies:
            name_lower = dep.name.lower().replace("@", "").replace("/", "-")
            
            if name_lower in known_latest:
                latest = known_latest[name_lower]
                current = self._extract_version(dep.version)
                
                if current and current != latest:
                    outdated.append(OutdatedPackage(
                        name=dep.name,
                        current_version=current,
                        latest_version=latest,
                    ))
        
        return outdated
    
    def _extract_version(self, version_constraint: str) -> str:
        """从版本约束中提取版本号"""
        if not version_constraint:
            return ""
        
        # 移除操作符
        for op in self.VERSION_OPERATORS:
            if version_constraint.startswith(op):
                version_constraint = version_constraint[len(op):]
                break
        
        # 清理
        version_constraint = version_constraint.strip()
        version_constraint = version_constraint.strip("^~>=<")
        
        # 提取版本号部分
        match = re.match(r"(\d+\.\d+\.\d+|\d+\.\d+|\d+)", version_constraint)
        if match:
            return match.group(1)
        
        return version_constraint
    
    def get_dependency_tree(self, dependencies: list[Dependency]) -> dict[str, Any]:
        """
        获取依赖树
        
        Args:
            dependencies: 依赖列表
            
        Returns:
            依赖树结构
        """
        tree = {
            "production": [],
            "development": [],
            "optional": [],
            "peer": [],
        }
        
        for dep in dependencies:
            type_key = dep.dependency_type.value
            if type_key in tree:
                tree[type_key].append(dep.to_dict())
        
        return tree


# 创建默认解析器实例
dependency_resolver = DependencyResolver()
