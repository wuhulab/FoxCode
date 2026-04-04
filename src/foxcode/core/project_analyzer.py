"""
FoxCode 项目分析器模块

提供项目结构分析、技术栈识别、依赖关系解析和代码质量评分功能。
"""

from __future__ import annotations

import ast
import json
import logging
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

logger = logging.getLogger(__name__)


class ProjectType(str, Enum):
    """项目类型枚举"""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    GO = "go"
    RUST = "rust"
    CPP = "cpp"
    CSHARP = "csharp"
    PHP = "php"
    RUBY = "ruby"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class LanguageType(str, Enum):
    """编程语言类型"""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    GO = "go"
    RUST = "rust"
    CPP = "cpp"
    C = "c"
    CSHARP = "csharp"
    PHP = "php"
    RUBY = "ruby"
    KOTLIN = "kotlin"
    SWIFT = "swift"
    SCALA = "scala"
    LUA = "lua"
    SQL = "sql"
    HTML = "html"
    CSS = "css"
    JSON = "json"
    YAML = "yaml"
    MARKDOWN = "markdown"
    SHELL = "shell"
    OTHER = "other"


@dataclass
class FileInfo:
    """
    文件信息

    Attributes:
        path: 文件路径
        name: 文件名
        extension: 文件扩展名
        size: 文件大小（字节）
        lines: 总行数
        language: 编程语言
        is_test: 是否为测试文件
        is_config: 是否为配置文件
        is_documentation: 是否为文档文件
    """
    path: Path
    name: str
    extension: str
    size: int
    lines: int
    language: LanguageType
    is_test: bool = False
    is_config: bool = False
    is_documentation: bool = False

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "path": str(self.path),
            "name": self.name,
            "extension": self.extension,
            "size": self.size,
            "lines": self.lines,
            "language": self.language.value,
            "is_test": self.is_test,
            "is_config": self.is_config,
            "is_documentation": self.is_documentation,
        }


@dataclass
class DirectoryInfo:
    """
    目录信息

    Attributes:
        path: 目录路径
        name: 目录名
        files: 文件列表
        subdirectories: 子目录列表
        total_files: 总文件数
        total_size: 总大小
    """
    path: Path
    name: str
    files: list[FileInfo] = field(default_factory=list)
    subdirectories: list[DirectoryInfo] = field(default_factory=list)
    total_files: int = 0
    total_size: int = 0

    def calculate_totals(self) -> None:
        """计算总计"""
        self.total_files = len(self.files)
        self.total_size = sum(f.size for f in self.files)

        for subdir in self.subdirectories:
            subdir.calculate_totals()
            self.total_files += subdir.total_files
            self.total_size += subdir.total_size

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "path": str(self.path),
            "name": self.name,
            "files": [f.to_dict() for f in self.files],
            "subdirectories": [s.to_dict() for s in self.subdirectories],
            "total_files": self.total_files,
            "total_size": self.total_size,
        }


@dataclass
class DependencyInfo:
    """
    依赖信息

    Attributes:
        name: 依赖名称
        version: 版本要求
        is_dev: 是否为开发依赖
        source: 依赖来源文件
    """
    name: str
    version: str | None = None
    is_dev: bool = False
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "name": self.name,
            "version": self.version,
            "is_dev": self.is_dev,
            "source": self.source,
        }


@dataclass
class TechStack:
    """
    技术栈信息

    Attributes:
        project_type: 项目类型
        primary_language: 主要编程语言
        languages: 语言分布
        frameworks: 框架列表
        databases: 数据库列表
        tools: 工具列表
        runtime: 运行时环境
    """
    project_type: ProjectType = ProjectType.UNKNOWN
    primary_language: LanguageType = LanguageType.OTHER
    languages: dict[LanguageType, int] = field(default_factory=dict)
    frameworks: list[str] = field(default_factory=list)
    databases: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    runtime: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "project_type": self.project_type.value,
            "primary_language": self.primary_language.value,
            "languages": {k.value: v for k, v in self.languages.items()},
            "frameworks": self.frameworks,
            "databases": self.databases,
            "tools": self.tools,
            "runtime": self.runtime,
        }


@dataclass
class StructureInfo:
    """
    项目结构信息

    Attributes:
        root: 根目录信息
        total_files: 总文件数
        total_directories: 总目录数
        total_size: 总大小
        total_lines: 总代码行数
        file_types: 文件类型分布
        directory_depth: 最大目录深度
        has_tests: 是否有测试
        has_docs: 是否有文档
        has_ci: 是否有 CI 配置
    """
    root: DirectoryInfo | None = None
    total_files: int = 0
    total_directories: int = 0
    total_size: int = 0
    total_lines: int = 0
    file_types: dict[str, int] = field(default_factory=dict)
    directory_depth: int = 0
    has_tests: bool = False
    has_docs: bool = False
    has_ci: bool = False

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "root": self.root.to_dict() if self.root else None,
            "total_files": self.total_files,
            "total_directories": self.total_directories,
            "total_size": self.total_size,
            "total_lines": self.total_lines,
            "file_types": self.file_types,
            "directory_depth": self.directory_depth,
            "has_tests": self.has_tests,
            "has_docs": self.has_docs,
            "has_ci": self.has_ci,
        }


@dataclass
class QualityScore:
    """
    代码质量评分

    Attributes:
        overall: 总体评分 (0-100)
        code_style: 代码风格评分
        documentation: 文档评分
        test_coverage: 测试覆盖评分
        complexity: 复杂度评分
        maintainability: 可维护性评分
        security: 安全性评分
        details: 详细评分信息
    """
    overall: float = 0.0
    code_style: float = 0.0
    documentation: float = 0.0
    test_coverage: float = 0.0
    complexity: float = 0.0
    maintainability: float = 0.0
    security: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)

    def calculate_overall(self) -> None:
        """计算总体评分"""
        weights = {
            "code_style": 0.2,
            "documentation": 0.15,
            "test_coverage": 0.2,
            "complexity": 0.15,
            "maintainability": 0.2,
            "security": 0.1,
        }

        self.overall = sum(
            getattr(self, name) * weight
            for name, weight in weights.items()
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "overall": round(self.overall, 2),
            "code_style": round(self.code_style, 2),
            "documentation": round(self.documentation, 2),
            "test_coverage": round(self.test_coverage, 2),
            "complexity": round(self.complexity, 2),
            "maintainability": round(self.maintainability, 2),
            "security": round(self.security, 2),
            "details": self.details,
        }


@dataclass
class ProjectReport:
    """
    项目分析报告

    Attributes:
        project_path: 项目路径
        project_name: 项目名称
        analyzed_at: 分析时间
        tech_stack: 技术栈信息
        structure: 项目结构信息
        dependencies: 依赖列表
        quality_score: 质量评分
        recommendations: 改进建议
        errors: 错误列表
    """
    project_path: Path
    project_name: str
    analyzed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    tech_stack: TechStack = field(default_factory=TechStack)
    structure: StructureInfo = field(default_factory=StructureInfo)
    dependencies: list[DependencyInfo] = field(default_factory=list)
    quality_score: QualityScore = field(default_factory=QualityScore)
    recommendations: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "project_path": str(self.project_path),
            "project_name": self.project_name,
            "analyzed_at": self.analyzed_at,
            "tech_stack": self.tech_stack.to_dict(),
            "structure": self.structure.to_dict(),
            "dependencies": [d.to_dict() for d in self.dependencies],
            "quality_score": self.quality_score.to_dict(),
            "recommendations": self.recommendations,
            "errors": self.errors,
        }


class ProjectAnalyzerConfig(BaseModel):
    """
    项目分析器配置

    Attributes:
        max_file_size: 最大文件大小（字节）
        exclude_dirs: 排除的目录
        exclude_files: 排除的文件模式
        include_hidden: 是否包含隐藏文件
        analyze_depth: 分析深度
        enable_quality_analysis: 是否启用质量分析
        enable_dependency_analysis: 是否启用依赖分析
    """
    max_file_size: int = Field(default=10 * 1024 * 1024, description="最大文件大小（字节）")
    exclude_dirs: list[str] = Field(
        default_factory=lambda: [
            "__pycache__", ".git", ".svn", ".hg", "node_modules",
            "venv", ".venv", "env", ".env", "dist", "build",
            ".idea", ".vscode", "*.egg-info", ".tox", ".mypy_cache",
            ".pytest_cache", ".ruff_cache", "target", "bin", "obj",
        ],
        description="排除的目录",
    )
    exclude_files: list[str] = Field(
        default_factory=lambda: [
            "*.pyc", "*.pyo", "*.so", "*.dll", "*.dylib",
            "*.exe", "*.bin", "*.lock", "*.log",
        ],
        description="排除的文件模式",
    )
    include_hidden: bool = Field(default=False, description="是否包含隐藏文件")
    analyze_depth: int = Field(default=10, ge=1, le=50, description="分析深度")
    enable_quality_analysis: bool = Field(default=True, description="是否启用质量分析")
    enable_dependency_analysis: bool = Field(default=True, description="是否启用依赖分析")


# 语言扩展名映射
LANGUAGE_EXTENSIONS: dict[str, LanguageType] = {
    ".py": LanguageType.PYTHON,
    ".pyw": LanguageType.PYTHON,
    ".js": LanguageType.JAVASCRIPT,
    ".mjs": LanguageType.JAVASCRIPT,
    ".cjs": LanguageType.JAVASCRIPT,
    ".jsx": LanguageType.JAVASCRIPT,
    ".ts": LanguageType.TYPESCRIPT,
    ".tsx": LanguageType.TYPESCRIPT,
    ".mts": LanguageType.TYPESCRIPT,
    ".java": LanguageType.JAVA,
    ".go": LanguageType.GO,
    ".rs": LanguageType.RUST,
    ".cpp": LanguageType.CPP,
    ".cc": LanguageType.CPP,
    ".cxx": LanguageType.CPP,
    ".c": LanguageType.C,
    ".h": LanguageType.C,
    ".hpp": LanguageType.CPP,
    ".cs": LanguageType.CSHARP,
    ".php": LanguageType.PHP,
    ".rb": LanguageType.RUBY,
    ".kt": LanguageType.KOTLIN,
    ".kts": LanguageType.KOTLIN,
    ".swift": LanguageType.SWIFT,
    ".scala": LanguageType.SCALA,
    ".lua": LanguageType.LUA,
    ".sql": LanguageType.SQL,
    ".html": LanguageType.HTML,
    ".htm": LanguageType.HTML,
    ".css": LanguageType.CSS,
    ".scss": LanguageType.CSS,
    ".sass": LanguageType.CSS,
    ".less": LanguageType.CSS,
    ".json": LanguageType.JSON,
    ".yaml": LanguageType.YAML,
    ".yml": LanguageType.YAML,
    ".md": LanguageType.MARKDOWN,
    ".markdown": LanguageType.MARKDOWN,
    ".sh": LanguageType.SHELL,
    ".bash": LanguageType.SHELL,
    ".zsh": LanguageType.SHELL,
    ".ps1": LanguageType.SHELL,
    ".bat": LanguageType.SHELL,
}

# 测试文件模式
TEST_FILE_PATTERNS = [
    r"test_.*\.py$",
    r".*_test\.py$",
    r".*\.test\.py$",
    r".*\.spec\.js$",
    r".*\.spec\.ts$",
    r".*\.test\.js$",
    r".*\.test\.ts$",
    r"Test.*\.java$",
    r".*Test\.java$",
    r".*_test\.go$",
]

# 配置文件模式
CONFIG_FILE_PATTERNS = [
    r"^package\.json$",
    r"^pyproject\.toml$",
    r"^setup\.py$",
    r"^setup\.cfg$",
    r"^requirements.*\.txt$",
    r"^Cargo\.toml$",
    r"^go\.mod$",
    r"^pom\.xml$",
    r"^build\.gradle$",
    r"^composer\.json$",
    r"^Gemfile$",
    r"^\.env",
    r"^config\.",
    r"^.*\.config\.(js|ts|json|yaml|yml)$",
]

# 文档文件模式
DOC_FILE_PATTERNS = [
    r"^README",
    r"^CHANGELOG",
    r"^CONTRIBUTING",
    r"^LICENSE",
    r"^AUTHORS",
    r"^.*\.md$",
    r"^docs?/",
    r"^documentation/",
]

# CI 配置文件模式
CI_FILE_PATTERNS = [
    r"^\.github/workflows/",
    r"^\.gitlab-ci\.yml$",
    r"^\.travis\.yml$",
    r"^Jenkinsfile$",
    r"^azure-pipelines\.yml$",
    r"^\.circleci/",
]


class ProjectAnalyzer:
    """
    项目结构分析器

    提供项目技术栈识别、结构可视化、依赖关系解析和代码质量评分功能。

    Attributes:
        config: 分析器配置
    """

    def __init__(self, config: ProjectAnalyzerConfig | None = None):
        """
        初始化分析器

        Args:
            config: 分析器配置，如果为 None 则使用默认配置
        """
        self.config = config or ProjectAnalyzerConfig()
        self._compiled_patterns: dict[str, list[re.Pattern]] = {}
        self._compile_patterns()
        logger.info("项目分析器初始化完成")

    def _compile_patterns(self) -> None:
        """编译正则表达式模式以提高性能"""
        pattern_groups = {
            "test": TEST_FILE_PATTERNS,
            "config": CONFIG_FILE_PATTERNS,
            "doc": DOC_FILE_PATTERNS,
            "ci": CI_FILE_PATTERNS,
        }

        for group_name, patterns in pattern_groups.items():
            self._compiled_patterns[group_name] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

    async def analyze(self, project_path: Path) -> ProjectReport:
        """
        分析项目

        执行完整的项目分析，包括技术栈识别、结构分析、
        依赖解析和质量评分。

        Args:
            project_path: 项目根目录路径

        Returns:
            ProjectReport: 项目分析报告

        Raises:
            ValueError: 当项目路径无效时抛出
            FileNotFoundError: 当项目路径不存在时抛出
        """
        if not project_path.exists():
            raise FileNotFoundError(f"项目路径不存在: {project_path}")

        if not project_path.is_dir():
            raise ValueError(f"项目路径不是目录: {project_path}")

        logger.info(f"开始分析项目: {project_path}")

        report = ProjectReport(
            project_path=project_path,
            project_name=project_path.name,
        )

        try:
            report.tech_stack = self.detect_tech_stack(project_path)
            logger.debug(f"技术栈检测完成: {report.tech_stack.project_type.value}")

            report.structure = self.analyze_structure(project_path)
            logger.debug(
                f"结构分析完成: {report.structure.total_files} 文件, "
                f"{report.structure.total_directories} 目录"
            )

            if self.config.enable_dependency_analysis:
                report.dependencies = self.analyze_dependencies(project_path)
                logger.debug(f"依赖分析完成: {len(report.dependencies)} 个依赖")

            if self.config.enable_quality_analysis:
                report.quality_score = self.calculate_quality_score(project_path)
                logger.debug(f"质量评分完成: {report.quality_score.overall:.2f}")

            report.recommendations = self._generate_recommendations(report)

            logger.info(f"项目分析完成: {project_path}")

        except Exception as e:
            error_msg = f"分析过程中发生错误: {str(e)}"
            logger.error(error_msg, exc_info=True)
            report.errors.append(error_msg)

        return report

    def detect_tech_stack(self, project_path: Path) -> TechStack:
        """
        检测技术栈

        通过分析项目文件和配置来识别项目使用的技术栈。

        Args:
            project_path: 项目根目录路径

        Returns:
            TechStack: 技术栈信息
        """
        tech_stack = TechStack()
        language_counts: dict[LanguageType, int] = defaultdict(int)

        try:
            self._detect_project_type(project_path, tech_stack)

            for file_path in self._iter_project_files(project_path):
                if file_path.is_file():
                    ext = file_path.suffix.lower()
                    if ext in LANGUAGE_EXTENSIONS:
                        language = LANGUAGE_EXTENSIONS[ext]
                        try:
                            line_count = self._count_file_lines(file_path)
                            language_counts[language] += line_count
                        except Exception as e:
                            logger.debug(f"无法读取文件 {file_path}: {e}")
                            language_counts[language] += 1

            tech_stack.languages = dict(language_counts)

            if language_counts:
                tech_stack.primary_language = max(
                    language_counts.keys(),
                    key=lambda k: language_counts[k],
                )

            self._detect_frameworks(project_path, tech_stack)
            self._detect_databases(project_path, tech_stack)
            self._detect_tools(project_path, tech_stack)

        except Exception as e:
            logger.error(f"技术栈检测失败: {e}", exc_info=True)

        return tech_stack

    def analyze_structure(self, project_path: Path) -> StructureInfo:
        """
        分析项目结构

        分析项目的目录结构、文件分布等信息。

        Args:
            project_path: 项目根目录路径

        Returns:
            StructureInfo: 项目结构信息
        """
        structure = StructureInfo()

        try:
            root_info = self._analyze_directory(project_path, depth=0)
            structure.root = root_info
            root_info.calculate_totals()

            structure.total_files = root_info.total_files
            structure.total_size = root_info.total_size

            self._calculate_structure_stats(structure, root_info)

            structure.has_tests = self._check_pattern_exists(
                project_path, self._compiled_patterns["test"]
            )
            structure.has_docs = self._check_pattern_exists(
                project_path, self._compiled_patterns["doc"]
            )
            structure.has_ci = self._check_pattern_exists(
                project_path, self._compiled_patterns["ci"]
            )

        except Exception as e:
            logger.error(f"结构分析失败: {e}", exc_info=True)

        return structure

    def analyze_dependencies(self, project_path: Path) -> list[DependencyInfo]:
        """
        分析项目依赖

        解析项目的依赖配置文件，提取依赖信息。

        Args:
            project_path: 项目根目录路径

        Returns:
            list[DependencyInfo]: 依赖列表
        """
        dependencies: list[DependencyInfo] = []

        try:
            pyproject_path = project_path / "pyproject.toml"
            if pyproject_path.exists():
                dependencies.extend(self._parse_pyproject_toml(pyproject_path))

            requirements_files = list(project_path.glob("requirements*.txt"))
            for req_file in requirements_files:
                dependencies.extend(self._parse_requirements_txt(req_file))

            package_json_path = project_path / "package.json"
            if package_json_path.exists():
                dependencies.extend(self._parse_package_json(package_json_path))

            cargo_path = project_path / "Cargo.toml"
            if cargo_path.exists():
                dependencies.extend(self._parse_cargo_toml(cargo_path))

            go_mod_path = project_path / "go.mod"
            if go_mod_path.exists():
                dependencies.extend(self._parse_go_mod(go_mod_path))

        except Exception as e:
            logger.error(f"依赖分析失败: {e}", exc_info=True)

        seen = set()
        unique_deps = []
        for dep in dependencies:
            key = (dep.name, dep.is_dev)
            if key not in seen:
                seen.add(key)
                unique_deps.append(dep)

        return unique_deps

    def calculate_quality_score(self, project_path: Path) -> QualityScore:
        """
        计算代码质量评分

        通过分析代码文件计算代码质量评分。

        Args:
            project_path: 项目根目录路径

        Returns:
            QualityScore: 质量评分
        """
        score = QualityScore()

        try:
            code_files = list(self._iter_code_files(project_path))

            if not code_files:
                logger.warning("未找到代码文件，无法计算质量评分")
                return score

            style_scores = []
            doc_scores = []
            complexity_scores = []
            maintainability_scores = []
            security_scores = []

            for file_path in code_files:
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")

                    style_scores.append(self._score_code_style(file_path, content))
                    doc_scores.append(self._score_documentation(file_path, content))
                    complexity_scores.append(self._score_complexity(file_path, content))
                    maintainability_scores.append(
                        self._score_maintainability(file_path, content)
                    )
                    security_scores.append(self._score_security(file_path, content))

                except Exception as e:
                    logger.debug(f"无法分析文件 {file_path}: {e}")

            if style_scores:
                score.code_style = sum(style_scores) / len(style_scores) * 100
            if doc_scores:
                score.documentation = sum(doc_scores) / len(doc_scores) * 100
            if complexity_scores:
                score.complexity = sum(complexity_scores) / len(complexity_scores) * 100
            if maintainability_scores:
                score.maintainability = (
                    sum(maintainability_scores) / len(maintainability_scores) * 100
                )
            if security_scores:
                score.security = sum(security_scores) / len(security_scores) * 100

            test_files = [
                f for f in code_files
                if self._matches_patterns(f.name, self._compiled_patterns["test"])
            ]
            if code_files:
                score.test_coverage = len(test_files) / len(code_files) * 100

            score.details = {
                "files_analyzed": len(code_files),
                "test_files": len(test_files),
                "avg_file_size": (
                    sum(f.stat().st_size for f in code_files) / len(code_files)
                    if code_files else 0
                ),
            }

            score.calculate_overall()

        except Exception as e:
            logger.error(f"质量评分计算失败: {e}", exc_info=True)

        return score

    def generate_report(self, analysis: ProjectReport) -> str:
        """
        生成分析报告

        将项目分析结果转换为可读的报告格式。

        Args:
            analysis: 项目分析报告

        Returns:
            str: 格式化的报告字符串
        """
        lines = [
            "# 项目分析报告",
            "",
            f"**项目名称**: {analysis.project_name}",
            f"**项目路径**: {analysis.project_path}",
            f"**分析时间**: {analysis.analyzed_at}",
            "",
            "---",
            "",
            "## 📊 技术栈分析",
            "",
            f"- **项目类型**: {analysis.tech_stack.project_type.value}",
            f"- **主要语言**: {analysis.tech_stack.primary_language.value}",
        ]

        if analysis.tech_stack.languages:
            lines.append("")
            lines.append("### 语言分布")
            lines.append("")
            sorted_langs = sorted(
                analysis.tech_stack.languages.items(),
                key=lambda x: x[1],
                reverse=True,
            )
            for lang, count in sorted_langs[:10]:
                lines.append(f"- {lang.value}: {count} 行")

        if analysis.tech_stack.frameworks:
            lines.append("")
            lines.append("### 框架")
            lines.append("")
            for fw in analysis.tech_stack.frameworks:
                lines.append(f"- {fw}")

        if analysis.tech_stack.databases:
            lines.append("")
            lines.append("### 数据库")
            lines.append("")
            for db in analysis.tech_stack.databases:
                lines.append(f"- {db}")

        if analysis.tech_stack.tools:
            lines.append("")
            lines.append("### 工具")
            lines.append("")
            for tool in analysis.tech_stack.tools:
                lines.append(f"- {tool}")

        lines.extend([
            "",
            "---",
            "",
            "## 📁 项目结构",
            "",
            f"- **总文件数**: {analysis.structure.total_files}",
            f"- **总目录数**: {analysis.structure.total_directories}",
            f"- **总大小**: {self._format_size(analysis.structure.total_size)}",
            f"- **总代码行数**: {analysis.structure.total_lines:,}",
            f"- **最大目录深度**: {analysis.structure.directory_depth}",
            f"- **包含测试**: {'✅' if analysis.structure.has_tests else '❌'}",
            f"- **包含文档**: {'✅' if analysis.structure.has_docs else '❌'}",
            f"- **CI 配置**: {'✅' if analysis.structure.has_ci else '❌'}",
        ])

        if analysis.structure.file_types:
            lines.append("")
            lines.append("### 文件类型分布")
            lines.append("")
            sorted_types = sorted(
                analysis.structure.file_types.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:10]
            for ext, count in sorted_types:
                ext_display = ext if ext else "(无扩展名)"
                lines.append(f"- {ext_display}: {count} 个文件")

        if analysis.dependencies:
            lines.extend([
                "",
                "---",
                "",
                "## 📦 依赖分析",
                "",
                f"**总依赖数**: {len(analysis.dependencies)}",
                "",
            ])

            prod_deps = [d for d in analysis.dependencies if not d.is_dev]
            dev_deps = [d for d in analysis.dependencies if d.is_dev]

            if prod_deps:
                lines.append("### 生产依赖")
                lines.append("")
                for dep in prod_deps[:20]:
                    version = f" ({dep.version})" if dep.version else ""
                    lines.append(f"- {dep.name}{version}")

            if dev_deps:
                lines.append("")
                lines.append("### 开发依赖")
                lines.append("")
                for dep in dev_deps[:20]:
                    version = f" ({dep.version})" if dep.version else ""
                    lines.append(f"- {dep.name}{version}")

        lines.extend([
            "",
            "---",
            "",
            "## ⭐ 质量评分",
            "",
            f"### 总体评分: {analysis.quality_score.overall:.1f}/100",
            "",
            "| 评分项 | 分数 |",
            "|--------|------|",
            f"| 代码风格 | {analysis.quality_score.code_style:.1f} |",
            f"| 文档完整性 | {analysis.quality_score.documentation:.1f} |",
            f"| 测试覆盖 | {analysis.quality_score.test_coverage:.1f} |",
            f"| 代码复杂度 | {analysis.quality_score.complexity:.1f} |",
            f"| 可维护性 | {analysis.quality_score.maintainability:.1f} |",
            f"| 安全性 | {analysis.quality_score.security:.1f} |",
        ])

        if analysis.recommendations:
            lines.extend([
                "",
                "---",
                "",
                "## 💡 改进建议",
                "",
            ])
            for i, rec in enumerate(analysis.recommendations, 1):
                lines.append(f"{i}. {rec}")

        if analysis.errors:
            lines.extend([
                "",
                "---",
                "",
                "## ⚠️ 错误信息",
                "",
            ])
            for error in analysis.errors:
                lines.append(f"- {error}")

        lines.extend([
            "",
            "---",
            "",
            "*报告由 FoxCode 项目分析器生成*",
        ])

        return "\n".join(lines)

    def _iter_project_files(self, project_path: Path) -> list[Path]:
        """
        迭代项目文件

        Args:
            project_path: 项目路径

        Returns:
            文件路径列表
        """
        files = []

        try:
            for root, dirs, filenames in os.walk(project_path):
                root_path = Path(root)

                dirs[:] = [
                    d for d in dirs
                    if not self._should_exclude_dir(d) and
                    (self.config.include_hidden or not d.startswith('.'))
                ]

                for filename in filenames:
                    if not self.config.include_hidden and filename.startswith('.'):
                        continue

                    if self._should_exclude_file(filename):
                        continue

                    file_path = root_path / filename

                    try:
                        if file_path.stat().st_size <= self.config.max_file_size:
                            files.append(file_path)
                    except OSError:
                        continue

        except Exception as e:
            logger.error(f"遍历项目文件失败: {e}", exc_info=True)

        return files

    def _iter_code_files(self, project_path: Path) -> list[Path]:
        """
        迭代代码文件

        Args:
            project_path: 项目路径

        Returns:
            代码文件路径列表
        """
        code_extensions = {
            ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go",
            ".rs", ".c", ".cpp", ".h", ".hpp", ".cs", ".php", ".rb",
            ".kt", ".swift", ".scala", ".lua",
        }

        return [
            f for f in self._iter_project_files(project_path)
            if f.suffix.lower() in code_extensions
        ]

    def _should_exclude_dir(self, dir_name: str) -> bool:
        """检查是否应排除目录"""
        for pattern in self.config.exclude_dirs:
            if '*' in pattern:
                if re.match(pattern.replace('*', '.*'), dir_name, re.IGNORECASE):
                    return True
            elif dir_name == pattern:
                return True
        return False

    def _should_exclude_file(self, filename: str) -> bool:
        """检查是否应排除文件"""
        for pattern in self.config.exclude_files:
            if '*' in pattern:
                regex_pattern = pattern.replace('.', r'\.').replace('*', '.*')
                if re.match(regex_pattern, filename, re.IGNORECASE):
                    return True
        return False

    def _analyze_directory(
        self,
        dir_path: Path,
        depth: int = 0,
    ) -> DirectoryInfo:
        """
        分析单个目录

        Args:
            dir_path: 目录路径
            depth: 当前深度

        Returns:
            DirectoryInfo: 目录信息
        """
        dir_info = DirectoryInfo(
            path=dir_path,
            name=dir_path.name,
        )

        if depth > self.config.analyze_depth:
            return dir_info

        try:
            for item in sorted(dir_path.iterdir()):
                if item.name.startswith('.') and not self.config.include_hidden:
                    continue

                if item.is_dir():
                    if not self._should_exclude_dir(item.name):
                        subdir_info = self._analyze_directory(item, depth + 1)
                        dir_info.subdirectories.append(subdir_info)
                elif item.is_file() and not self._should_exclude_file(item.name):
                    file_info = self._create_file_info(item)
                    dir_info.files.append(file_info)

        except PermissionError as e:
            logger.warning(f"无法访问目录 {dir_path}: {e}")
        except Exception as e:
            logger.error(f"分析目录失败 {dir_path}: {e}", exc_info=True)

        return dir_info

    def _create_file_info(self, file_path: Path) -> FileInfo:
        """
        创建文件信息

        Args:
            file_path: 文件路径

        Returns:
            FileInfo: 文件信息
        """
        ext = file_path.suffix.lower()
        language = LANGUAGE_EXTENSIONS.get(ext, LanguageType.OTHER)

        try:
            stat = file_path.stat()
            size = stat.st_size
        except OSError:
            size = 0

        try:
            lines = self._count_file_lines(file_path)
        except Exception:
            lines = 0

        name = file_path.name
        is_test = self._matches_patterns(name, self._compiled_patterns["test"])
        is_config = self._matches_patterns(name, self._compiled_patterns["config"])
        is_doc = self._matches_patterns(
            str(file_path.relative_to(file_path.parent.parent)),
            self._compiled_patterns["doc"],
        )

        return FileInfo(
            path=file_path,
            name=name,
            extension=ext,
            size=size,
            lines=lines,
            language=language,
            is_test=is_test,
            is_config=is_config,
            is_documentation=is_doc,
        )

    def _count_file_lines(self, file_path: Path) -> int:
        """统计文件行数"""
        try:
            with open(file_path, encoding='utf-8', errors='ignore') as f:
                return sum(1 for _ in f)
        except Exception:
            return 0

    def _matches_patterns(self, text: str, patterns: list[re.Pattern]) -> bool:
        """检查文本是否匹配任一模式"""
        return any(pattern.search(text) for pattern in patterns)

    def _check_pattern_exists(
        self,
        project_path: Path,
        patterns: list[re.Pattern],
    ) -> bool:
        """检查项目中是否存在匹配模式的文件"""
        for file_path in self._iter_project_files(project_path):
            rel_path = file_path.relative_to(project_path)
            if self._matches_patterns(str(rel_path), patterns):
                return True
        return False

    def _calculate_structure_stats(
        self,
        structure: StructureInfo,
        root_info: DirectoryInfo,
    ) -> None:
        """计算结构统计信息"""
        def count_directories(dir_info: DirectoryInfo, depth: int = 0) -> tuple[int, int, int]:
            total_dirs = 1
            max_depth = depth
            total_lines = sum(f.lines for f in dir_info.files)

            for subdir in dir_info.subdirectories:
                sub_dirs, sub_depth, sub_lines = count_directories(subdir, depth + 1)
                total_dirs += sub_dirs
                max_depth = max(max_depth, sub_depth)
                total_lines += sub_lines

            return total_dirs, max_depth, total_lines

        total_dirs, max_depth, total_lines = count_directories(root_info)
        structure.total_directories = total_dirs
        structure.directory_depth = max_depth
        structure.total_lines = total_lines

        file_types: dict[str, int] = defaultdict(int)

        def count_file_types(dir_info: DirectoryInfo) -> None:
            for f in dir_info.files:
                ext = f.extension if f.extension else "(无扩展名)"
                file_types[ext] += 1
            for subdir in dir_info.subdirectories:
                count_file_types(subdir)

        count_file_types(root_info)
        structure.file_types = dict(file_types)

    def _detect_project_type(self, project_path: Path, tech_stack: TechStack) -> None:
        """检测项目类型"""
        has_pyproject = (project_path / "pyproject.toml").exists()
        has_setup_py = (project_path / "setup.py").exists()
        has_requirements = list(project_path.glob("requirements*.txt"))
        has_package_json = (project_path / "package.json").exists()
        has_cargo = (project_path / "Cargo.toml").exists()
        has_go_mod = (project_path / "go.mod").exists()
        has_pom = (project_path / "pom.xml").exists()
        has_gradle = (project_path / "build.gradle").exists() or \
                     (project_path / "build.gradle.kts").exists()

        type_count = sum([
            has_pyproject or has_setup_py or bool(has_requirements),
            has_package_json,
            has_cargo,
            has_go_mod,
            has_pom or has_gradle,
        ])

        if type_count > 1:
            tech_stack.project_type = ProjectType.MIXED
        elif has_pyproject or has_setup_py or has_requirements:
            tech_stack.project_type = ProjectType.PYTHON
        elif has_package_json:
            ts_files = list(project_path.glob("**/*.ts")) + \
                      list(project_path.glob("**/*.tsx"))
            tech_stack.project_type = (
                ProjectType.TYPESCRIPT if ts_files else ProjectType.JAVASCRIPT
            )
        elif has_cargo:
            tech_stack.project_type = ProjectType.RUST
        elif has_go_mod:
            tech_stack.project_type = ProjectType.GO
        elif has_pom or has_gradle:
            tech_stack.project_type = ProjectType.JAVA

    def _detect_frameworks(self, project_path: Path, tech_stack: TechStack) -> None:
        """检测框架"""
        frameworks: set[str] = set()

        pyproject_path = project_path / "pyproject.toml"
        if pyproject_path.exists():
            try:
                with open(pyproject_path, "rb") as f:
                    data = tomllib.load(f)

                deps = []
                if "project" in data and "dependencies" in data["project"]:
                    deps.extend(data["project"]["dependencies"])
                if "project" in data and "optional-dependencies" in data["project"]:
                    for opt_deps in data["project"]["optional-dependencies"].values():
                        deps.extend(opt_deps)

                python_frameworks = {
                    "django": "Django",
                    "flask": "Flask",
                    "fastapi": "FastAPI",
                    "tornado": "Tornado",
                    "aiohttp": "aiohttp",
                    "sanic": "Sanic",
                    "bottle": "Bottle",
                    "pyramid": "Pyramid",
                    "celery": "Celery",
                    "sqlalchemy": "SQLAlchemy",
                    "pydantic": "Pydantic",
                    "pytest": "pytest",
                    "numpy": "NumPy",
                    "pandas": "Pandas",
                    "tensorflow": "TensorFlow",
                    "torch": "PyTorch",
                    "scikit-learn": "scikit-learn",
                    "requests": "Requests",
                }

                for dep in deps:
                    dep_lower = dep.lower().split('>=')[0].split('==')[0].split('<')[0].strip()
                    for key, name in python_frameworks.items():
                        if key in dep_lower:
                            frameworks.add(name)

            except Exception as e:
                logger.debug(f"解析 pyproject.toml 失败: {e}")

        package_json_path = project_path / "package.json"
        if package_json_path.exists():
            try:
                with open(package_json_path, encoding="utf-8") as f:
                    data = json.load(f)

                all_deps = {}
                all_deps.update(data.get("dependencies", {}))
                all_deps.update(data.get("devDependencies", {}))

                js_frameworks = {
                    "react": "React",
                    "vue": "Vue.js",
                    "angular": "Angular",
                    "svelte": "Svelte",
                    "next": "Next.js",
                    "nuxt": "Nuxt.js",
                    "express": "Express.js",
                    "koa": "Koa",
                    "fastify": "Fastify",
                    "nestjs": "NestJS",
                    "electron": "Electron",
                    "typescript": "TypeScript",
                    "webpack": "Webpack",
                    "vite": "Vite",
                    "rollup": "Rollup",
                    "jest": "Jest",
                    "mocha": "Mocha",
                    "tailwindcss": "Tailwind CSS",
                }

                for dep_name in all_deps:
                    dep_lower = dep_name.lower()
                    for key, name in js_frameworks.items():
                        if key in dep_lower:
                            frameworks.add(name)

            except Exception as e:
                logger.debug(f"解析 package.json 失败: {e}")

        tech_stack.frameworks = sorted(frameworks)

    def _detect_databases(self, project_path: Path, tech_stack: TechStack) -> None:
        """检测数据库"""
        databases: set[str] = set()

        db_patterns = [
            (r"postgresql|psycopg", "PostgreSQL"),
            (r"mysql|pymysql|mysqlclient", "MySQL"),
            (r"sqlite", "SQLite"),
            (r"mongodb|pymongo", "MongoDB"),
            (r"redis", "Redis"),
            (r"elasticsearch", "Elasticsearch"),
            (r"cassandra", "Cassandra"),
            (r"oracle", "Oracle"),
            (r"sqlserver|pyodbc", "SQL Server"),
        ]

        for file_path in self._iter_project_files(project_path):
            if file_path.suffix.lower() in {".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml"}:
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore").lower()
                    for pattern, db_name in db_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            databases.add(db_name)
                except Exception:
                    continue

        tech_stack.databases = sorted(databases)

    def _detect_tools(self, project_path: Path, tech_stack: TechStack) -> None:
        """检测工具"""
        tools: set[str] = set()

        tool_files = {
            ".github/workflows": "GitHub Actions",
            ".gitlab-ci.yml": "GitLab CI",
            ".travis.yml": "Travis CI",
            "Jenkinsfile": "Jenkins",
            "docker-compose.yml": "Docker Compose",
            "Dockerfile": "Docker",
            ".pre-commit-config.yaml": "pre-commit",
            ".eslintrc": "ESLint",
            ".prettierrc": "Prettier",
            "ruff.toml": "Ruff",
            ".mypy.ini": "mypy",
            "pytest.ini": "pytest",
            "tox.ini": "tox",
            "Makefile": "Make",
        }

        for file_pattern, tool_name in tool_files.items():
            if (project_path / file_pattern).exists():
                tools.add(tool_name)

        tech_stack.tools = sorted(tools)

    def _parse_pyproject_toml(self, file_path: Path) -> list[DependencyInfo]:
        """解析 pyproject.toml"""
        dependencies = []

        try:
            with open(file_path, "rb") as f:
                data = tomllib.load(f)

            if "project" in data:
                for dep in data["project"].get("dependencies", []):
                    name, version = self._parse_dependency_string(dep)
                    dependencies.append(DependencyInfo(
                        name=name,
                        version=version,
                        is_dev=False,
                        source="pyproject.toml",
                    ))

                for group_name, group_deps in data["project"].get("optional-dependencies", {}).items():
                    for dep in group_deps:
                        name, version = self._parse_dependency_string(dep)
                        dependencies.append(DependencyInfo(
                            name=name,
                            version=version,
                            is_dev=True,
                            source=f"pyproject.toml [{group_name}]",
                        ))

            if "tool" in data and "poetry" in data["tool"]:
                poetry_deps = data["tool"]["poetry"].get("dependencies", {})
                for name, version in poetry_deps.items():
                    if name.lower() != "python":
                        dependencies.append(DependencyInfo(
                            name=name,
                            version=str(version) if version else None,
                            is_dev=False,
                            source="pyproject.toml (poetry)",
                        ))

                poetry_dev_deps = data["tool"]["poetry"].get("dev-dependencies", {})
                for name, version in poetry_dev_deps.items():
                    dependencies.append(DependencyInfo(
                        name=name,
                        version=str(version) if version else None,
                        is_dev=True,
                        source="pyproject.toml (poetry dev)",
                    ))

        except Exception as e:
            logger.error(f"解析 pyproject.toml 失败: {e}", exc_info=True)

        return dependencies

    def _parse_requirements_txt(self, file_path: Path) -> list[DependencyInfo]:
        """解析 requirements.txt"""
        dependencies = []

        try:
            with open(file_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('-'):
                        name, version = self._parse_dependency_string(line)
                        is_dev = "dev" in file_path.name.lower()
                        dependencies.append(DependencyInfo(
                            name=name,
                            version=version,
                            is_dev=is_dev,
                            source=file_path.name,
                        ))
        except Exception as e:
            logger.error(f"解析 {file_path} 失败: {e}", exc_info=True)

        return dependencies

    def _parse_package_json(self, file_path: Path) -> list[DependencyInfo]:
        """解析 package.json"""
        dependencies = []

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            for name, version in data.get("dependencies", {}).items():
                dependencies.append(DependencyInfo(
                    name=name,
                    version=version,
                    is_dev=False,
                    source="package.json",
                ))

            for name, version in data.get("devDependencies", {}).items():
                dependencies.append(DependencyInfo(
                    name=name,
                    version=version,
                    is_dev=True,
                    source="package.json (dev)",
                ))

        except Exception as e:
            logger.error(f"解析 package.json 失败: {e}", exc_info=True)

        return dependencies

    def _parse_cargo_toml(self, file_path: Path) -> list[DependencyInfo]:
        """解析 Cargo.toml"""
        dependencies = []

        try:
            with open(file_path, "rb") as f:
                data = tomllib.load(f)

            deps = data.get("dependencies", {})
            for name, version in deps.items():
                if isinstance(version, str):
                    dependencies.append(DependencyInfo(
                        name=name,
                        version=version,
                        is_dev=False,
                        source="Cargo.toml",
                    ))
                elif isinstance(version, dict):
                    dependencies.append(DependencyInfo(
                        name=name,
                        version=version.get("version"),
                        is_dev=False,
                        source="Cargo.toml",
                    ))

            dev_deps = data.get("dev-dependencies", {})
            for name, version in dev_deps.items():
                if isinstance(version, str):
                    dependencies.append(DependencyInfo(
                        name=name,
                        version=version,
                        is_dev=True,
                        source="Cargo.toml (dev)",
                    ))

        except Exception as e:
            logger.error(f"解析 Cargo.toml 失败: {e}", exc_info=True)

        return dependencies

    def _parse_go_mod(self, file_path: Path) -> list[DependencyInfo]:
        """解析 go.mod"""
        dependencies = []

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            require_pattern = r"require\s*\(([^)]+)\)"
            matches = re.findall(require_pattern, content, re.DOTALL)

            for match in matches:
                lines = match.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('//'):
                        parts = line.split()
                        if len(parts) >= 2:
                            dependencies.append(DependencyInfo(
                                name=parts[0],
                                version=parts[1],
                                is_dev=False,
                                source="go.mod",
                            ))

        except Exception as e:
            logger.error(f"解析 go.mod 失败: {e}", exc_info=True)

        return dependencies

    def _parse_dependency_string(self, dep_str: str) -> tuple[str, str | None]:
        """
        解析依赖字符串

        Args:
            dep_str: 依赖字符串（如 "requests>=2.28.0"）

        Returns:
            tuple[str, str | None]: (依赖名, 版本)
        """
        operators = ['>=', '<=', '==', '!=', '~=', '>', '<', '===']

        for op in operators:
            if op in dep_str:
                parts = dep_str.split(op, 1)
                return parts[0].strip(), parts[1].strip()

        if ';' in dep_str:
            return dep_str.split(';')[0].strip(), None

        return dep_str.strip(), None

    def _score_code_style(self, file_path: Path, content: str) -> float:  # noqa: ARG002
        """评分代码风格"""
        score = 1.0

        lines = content.split('\n')

        long_lines = sum(1 for line in lines if len(line) > 100)
        if lines and long_lines / len(lines) > 0.1:
            score -= 0.2

        trailing_whitespace = sum(1 for line in lines if line.rstrip() != line)
        if lines and trailing_whitespace / len(lines) > 0.1:
            score -= 0.1

        mixed_indent = False
        for line in lines:
            if line.startswith(' ') and '\t' in line[:len(line) - len(line.lstrip())]:
                mixed_indent = True
                break
        if mixed_indent:
            score -= 0.2

        return max(0.0, score)

    def _score_documentation(self, file_path: Path, content: str) -> float:
        """评分文档"""
        score = 0.5

        if file_path.suffix.lower() == ".py":
            try:
                tree = ast.parse(content)

                total_items = 0
                with_docstrings = 0

                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef | ast.ClassDef | ast.AsyncFunctionDef):
                        total_items += 1
                        if ast.get_docstring(node):
                            with_docstrings += 1

                if total_items > 0:
                    coverage = with_docstrings / total_items
                    score = 0.3 + coverage * 0.7

            except SyntaxError:
                pass

        comment_lines = sum(1 for line in content.split('\n') if line.strip().startswith('#'))
        total_lines = len(content.split('\n'))
        if total_lines > 0 and comment_lines / total_lines > 0.1:
            score += 0.2

        return min(1.0, score)

    def _score_complexity(self, file_path: Path, content: str) -> float:
        """评分复杂度"""
        score = 1.0

        if file_path.suffix.lower() == ".py":
            try:
                tree = ast.parse(content)

                max_complexity = 0
                total_complexity = 0
                function_count = 0

                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                        complexity = self._calculate_cyclomatic_complexity(node)
                        max_complexity = max(max_complexity, complexity)
                        total_complexity += complexity
                        function_count += 1

                if max_complexity > 15:
                    score -= 0.3
                elif max_complexity > 10:
                    score -= 0.1

                if function_count > 0:
                    avg_complexity = total_complexity / function_count
                    if avg_complexity > 8:
                        score -= 0.2

            except SyntaxError:
                pass

        lines = content.split('\n')
        if lines and len(lines) > 500:
            score -= 0.2

        return max(0.0, score)

    def _calculate_cyclomatic_complexity(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
        """计算圈复杂度"""
        complexity = 1

        for child in ast.walk(node):
            if isinstance(child, ast.If | ast.While | ast.For | ast.AsyncFor):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
            elif isinstance(child, ast.And | ast.Or | ast.ExceptHandler | ast.With | ast.AsyncWith):
                complexity += 1

        return complexity

    def _score_maintainability(self, file_path: Path, content: str) -> float:
        """评分可维护性"""
        score = 1.0

        lines = content.split('\n')
        if lines:
            blank_ratio = sum(1 for line in lines if not line.strip()) / len(lines)
            if blank_ratio < 0.05 or blank_ratio > 0.4:
                score -= 0.1

        if file_path.suffix.lower() == ".py":
            try:
                tree = ast.parse(content)

                class_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
                function_count = sum(
                    1 for node in ast.walk(tree)
                    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
                )

                if class_count > 0 and function_count / class_count > 20:
                    score -= 0.2

            except SyntaxError:
                pass

        return max(0.0, score)

    def _score_security(self, file_path: Path, content: str) -> float:
        """评分安全性"""
        score = 1.0

        security_patterns = [
            (r"eval\s*\(", "使用 eval() 函数"),
            (r"exec\s*\(", "使用 exec() 函数"),
            (r"__import__\s*\(", "使用 __import__() 函数"),
            (r"subprocess\..*shell\s*=\s*True", "subprocess 使用 shell=True"),
            (r"pickle\.loads?\s*\(", "使用 pickle 可能不安全"),
            (r"yaml\.load\s*\([^)]*\)", "yaml.load 不安全"),
            (r"password\s*=\s*['\"]", "硬编码密码"),
            (r"api_key\s*=\s*['\"]", "硬编码 API Key"),
            (r"secret\s*=\s*['\"]", "硬编码密钥"),
        ]

        for pattern, desc in security_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                score -= 0.15
                logger.debug(f"发现安全问题: {desc} in {file_path}")

        return max(0.0, score)

    def _generate_recommendations(self, report: ProjectReport) -> list[str]:
        """生成改进建议"""
        recommendations = []

        if report.quality_score.overall < 60:
            recommendations.append("整体代码质量较低，建议进行全面重构")
        elif report.quality_score.overall < 80:
            recommendations.append("代码质量有提升空间，建议关注低分项")

        if report.quality_score.documentation < 50:
            recommendations.append("添加更多文档字符串和注释以提高代码可读性")

        if report.quality_score.test_coverage < 30:
            recommendations.append("添加单元测试以提高测试覆盖率")

        if report.quality_score.complexity < 50:
            recommendations.append("简化复杂函数，考虑拆分长函数")

        if report.quality_score.security < 70:
            recommendations.append("检查并修复潜在的安全问题")

        if not report.structure.has_tests:
            recommendations.append("项目缺少测试文件，建议添加测试")

        if not report.structure.has_docs:
            recommendations.append("项目缺少文档，建议添加 README.md")

        if not report.structure.has_ci:
            recommendations.append("建议添加 CI/CD 配置以自动化测试和部署")

        if report.structure.directory_depth > 8:
            recommendations.append("目录层级过深，考虑简化项目结构")

        if not recommendations:
            recommendations.append("项目状态良好，继续保持！")

        return recommendations

    def _format_size(self, size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


# 创建默认分析器实例
project_analyzer = ProjectAnalyzer()
