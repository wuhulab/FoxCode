"""
FoxCode 环境初始化脚本生成模块 - 自动检测项目依赖并生成初始化脚本

这个文件负责项目环境的自动初始化:
1. 项目类型检测：识别 Python/Node.js/Go/Rust/Java 等项目
2. 依赖分析：扫描项目依赖文件（requirements.txt, package.json 等）
3. 脚本生成：生成跨平台兼容的初始化脚本
4. 环境配置：配置虚拟环境、安装依赖

支持的项目类型:
- PYTHON: 检测 requirements.txt / pyproject.toml
- NODEJS: 检测 package.json
- GO: 检测 go.mod
- RUST: 检测 Cargo.toml
- JAVA: 检测 pom.xml / build.gradle
- MIXED: 多语言混合项目

使用方式:
    from foxcode.core.init_script import InitScriptGenerator

    generator = InitScriptGenerator(working_dir=Path("."))
    project_type = generator.detect_project_type()
    script = generator.generate_script()
"""

from __future__ import annotations

import asyncio
import logging
import platform
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class ProjectType(str, Enum):
    """项目类型枚举"""
    PYTHON = "python"
    NODEJS = "nodejs"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class DependencyType(str, Enum):
    """依赖类型枚举"""
    PIP = "pip"
    NPM = "npm"
    YARN = "yarn"
    PNPM = "pnpm"
    GO_MOD = "go_mod"
    CARGO = "cargo"
    MAVEN = "maven"
    GRADLE = "gradle"


@dataclass
class ProjectDependency:
    """
    项目依赖信息
    
    Attributes:
        name: 依赖名称
        version: 版本要求
        dep_type: 依赖类型
        is_dev: 是否为开发依赖
    """
    name: str
    version: str = ""
    dep_type: DependencyType = DependencyType.PIP
    is_dev: bool = False


@dataclass
class ProjectEnvironment:
    """
    项目环境信息
    
    Attributes:
        project_type: 项目类型
        project_name: 项目名称
        dependencies: 依赖列表
        python_version: Python 版本要求
        node_version: Node.js 版本要求
        env_vars: 环境变量
        required_tools: 必需工具列表
    """
    project_type: ProjectType = ProjectType.UNKNOWN
    project_name: str = ""
    dependencies: list[ProjectDependency] = field(default_factory=list)
    python_version: str = ""
    node_version: str = ""
    env_vars: dict[str, str] = field(default_factory=dict)
    required_tools: list[str] = field(default_factory=list)


class InitScriptGenerator:
    """
    初始化脚本生成器
    
    自动检测项目依赖和环境需求，生成跨平台兼容的初始化脚本
    """

    def __init__(self, working_dir: Path):
        """
        初始化脚本生成器
        
        Args:
            working_dir: 工作目录
        """
        self.working_dir = Path(working_dir)
        self._environment: ProjectEnvironment | None = None

    @property
    def environment(self) -> ProjectEnvironment:
        """获取项目环境信息（延迟检测）"""
        if self._environment is None:
            self._environment = self.detect_environment()
        return self._environment

    def detect_environment(self) -> ProjectEnvironment:
        """
        检测项目环境和依赖
        
        Returns:
            项目环境信息
        """
        env = ProjectEnvironment(
            project_name=self.working_dir.name,
        )

        # 检测 Python 项目
        if self._detect_python_project(env):
            env.project_type = ProjectType.PYTHON

        # 检测 Node.js 项目
        if self._detect_nodejs_project(env):
            if env.project_type == ProjectType.PYTHON:
                env.project_type = ProjectType.MIXED
            else:
                env.project_type = ProjectType.NODEJS

        # 检测 Go 项目
        if self._detect_go_project(env):
            if env.project_type in (ProjectType.PYTHON, ProjectType.NODEJS):
                env.project_type = ProjectType.MIXED
            else:
                env.project_type = ProjectType.GO

        # 检测 Rust 项目
        if self._detect_rust_project(env):
            if env.project_type in (ProjectType.PYTHON, ProjectType.NODEJS, ProjectType.GO):
                env.project_type = ProjectType.MIXED
            else:
                env.project_type = ProjectType.RUST

        # 检测 Java 项目
        if self._detect_java_project(env):
            if env.project_type != ProjectType.UNKNOWN:
                env.project_type = ProjectType.MIXED
            else:
                env.project_type = ProjectType.JAVA

        logger.info(f"检测到项目类型: {env.project_type.value}")
        return env

    def _detect_python_project(self, env: ProjectEnvironment) -> bool:
        """检测 Python 项目"""
        found = False

        # 检测 requirements.txt
        requirements_file = self.working_dir / "requirements.txt"
        if requirements_file.exists():
            found = True
            deps = self._parse_requirements_txt(requirements_file)
            env.dependencies.extend(deps)

        # 检测 pyproject.toml
        pyproject_file = self.working_dir / "pyproject.toml"
        if pyproject_file.exists():
            found = True
            deps = self._parse_pyproject_toml(pyproject_file)
            env.dependencies.extend(deps)

        # 检测 setup.py
        setup_file = self.working_dir / "setup.py"
        if setup_file.exists():
            found = True

        # 检测 Pipfile
        pipfile = self.working_dir / "Pipfile"
        if pipfile.exists():
            found = True
            env.required_tools.append("pipenv")

        # 检测 .python-version
        python_version_file = self.working_dir / ".python-version"
        if python_version_file.exists():
            try:
                env.python_version = python_version_file.read_text().strip()
            except Exception:
                pass

        return found

    def _detect_nodejs_project(self, env: ProjectEnvironment) -> bool:
        """检测 Node.js 项目"""
        found = False

        # 检测 package.json
        package_json = self.working_dir / "package.json"
        if package_json.exists():
            found = True
            deps = self._parse_package_json(package_json)
            env.dependencies.extend(deps)

        # 检测 yarn.lock
        yarn_lock = self.working_dir / "yarn.lock"
        if yarn_lock.exists():
            env.required_tools.append("yarn")

        # 检测 pnpm-lock.yaml
        pnpm_lock = self.working_dir / "pnpm-lock.yaml"
        if pnpm_lock.exists():
            env.required_tools.append("pnpm")

        # 检测 .nvmrc
        nvmrc = self.working_dir / ".nvmrc"
        if nvmrc.exists():
            try:
                env.node_version = nvmrc.read_text().strip()
            except Exception:
                pass

        return found

    def _detect_go_project(self, env: ProjectEnvironment) -> bool:
        """检测 Go 项目"""
        go_mod = self.working_dir / "go.mod"
        if go_mod.exists():
            env.required_tools.append("go")
            return True
        return False

    def _detect_rust_project(self, env: ProjectEnvironment) -> bool:
        """检测 Rust 项目"""
        cargo_toml = self.working_dir / "Cargo.toml"
        if cargo_toml.exists():
            env.required_tools.append("cargo")
            return True
        return False

    def _detect_java_project(self, env: ProjectEnvironment) -> bool:
        """检测 Java 项目"""
        pom_xml = self.working_dir / "pom.xml"
        if pom_xml.exists():
            env.required_tools.append("maven")
            return True

        build_gradle = self.working_dir / "build.gradle"
        if build_gradle.exists():
            env.required_tools.append("gradle")
            return True

        return False

    def _parse_requirements_txt(self, file_path: Path) -> list[ProjectDependency]:
        """解析 requirements.txt 文件"""
        deps = []
        try:
            content = file_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # 解析依赖名称和版本
                match = re.match(r"^([a-zA-Z0-9_-]+)\s*([<>=!]+.+)?", line)
                if match:
                    dep = ProjectDependency(
                        name=match.group(1),
                        version=match.group(2) or "",
                        dep_type=DependencyType.PIP,
                    )
                    deps.append(dep)
        except Exception as e:
            logger.warning(f"解析 requirements.txt 失败: {e}")

        return deps

    def _parse_pyproject_toml(self, file_path: Path) -> list[ProjectDependency]:
        """解析 pyproject.toml 文件"""
        deps = []
        try:
            if platform.python_version_tuple() >= ("3", "11"):
                import tomllib
            else:
                import tomli as tomllib

            with open(file_path, "rb") as f:
                data = tomllib.load(f)

            # 解析 project.dependencies
            project = data.get("project", {})
            for dep_str in project.get("dependencies", []):
                match = re.match(r"^([a-zA-Z0-9_-]+)\s*([<>=!]+.+)?", dep_str)
                if match:
                    dep = ProjectDependency(
                        name=match.group(1),
                        version=match.group(2) or "",
                        dep_type=DependencyType.PIP,
                    )
                    deps.append(dep)

            # 解析开发依赖
            optional_deps = project.get("optional-dependencies", {})
            for group_deps in optional_deps.values():
                for dep_str in group_deps:
                    match = re.match(r"^([a-zA-Z0-9_-]+)\s*([<>=!]+.+)?", dep_str)
                    if match:
                        dep = ProjectDependency(
                            name=match.group(1),
                            version=match.group(2) or "",
                            dep_type=DependencyType.PIP,
                            is_dev=True,
                        )
                        deps.append(dep)
        except Exception as e:
            logger.warning(f"解析 pyproject.toml 失败: {e}")

        return deps

    def _parse_package_json(self, file_path: Path) -> list[ProjectDependency]:
        """解析 package.json 文件"""
        deps = []
        try:
            import json

            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            # 解析 dependencies
            for name, version in data.get("dependencies", {}).items():
                dep = ProjectDependency(
                    name=name,
                    version=version,
                    dep_type=DependencyType.NPM,
                )
                deps.append(dep)

            # 解析 devDependencies
            for name, version in data.get("devDependencies", {}).items():
                dep = ProjectDependency(
                    name=name,
                    version=version,
                    dep_type=DependencyType.NPM,
                    is_dev=True,
                )
                deps.append(dep)
        except Exception as e:
            logger.warning(f"解析 package.json 失败: {e}")

        return deps

    def generate_init_script(self, output_dir: Path | None = None) -> dict[str, Path]:
        """
        生成初始化脚本
        
        Args:
            output_dir: 输出目录，默认为工作目录下的 .foxcode 目录
            
        Returns:
            生成的脚本文件路径字典 {"unix": Path, "windows": Path}
        """
        output_dir = output_dir or self.working_dir / ".foxcode"
        output_dir.mkdir(parents=True, exist_ok=True)

        scripts = {}

        # 生成 Unix 脚本 (init.sh)
        unix_script = self._generate_unix_script()
        unix_path = output_dir / "init.sh"
        unix_path.write_text(unix_script, encoding="utf-8")
        scripts["unix"] = unix_path
        logger.info(f"已生成 Unix 初始化脚本: {unix_path}")

        # 生成 Windows 脚本 (init.bat)
        windows_script = self._generate_windows_script()
        windows_path = output_dir / "init.bat"
        windows_path.write_text(windows_script, encoding="utf-8")
        scripts["windows"] = windows_path
        logger.info(f"已生成 Windows 初始化脚本: {windows_path}")

        return scripts

    def _generate_unix_script(self) -> str:
        """生成 Unix 初始化脚本内容"""
        env = self.environment

        lines = [
            "#!/bin/bash",
            "# FoxCode 项目初始化脚本",
            f"# 生成时间: {datetime.now().isoformat()}",
            f"# 项目类型: {env.project_type.value}",
            "",
            "set -e  # 遇到错误立即退出",
            "",
            "echo '🦊 FoxCode 项目初始化'",
            "echo '========================'",
            "",
        ]

        # 检测必需工具
        if env.required_tools:
            lines.append("# 检测必需工具")
            for tool in env.required_tools:
                lines.append(f"if ! command -v {tool} &> /dev/null; then")
                lines.append(f"    echo '❌ 错误: 未找到 {tool}'")
                lines.append(f"    echo '   请先安装 {tool}'")
                lines.append("    exit 1")
                lines.append("fi")
            lines.append("")

        # Python 项目初始化
        if env.project_type in (ProjectType.PYTHON, ProjectType.MIXED):
            lines.extend(self._generate_python_init_unix())

        # Node.js 项目初始化
        if env.project_type in (ProjectType.NODEJS, ProjectType.MIXED):
            lines.extend(self._generate_nodejs_init_unix())

        # Go 项目初始化
        if env.project_type == ProjectType.GO:
            lines.extend(self._generate_go_init_unix())

        # Rust 项目初始化
        if env.project_type == ProjectType.RUST:
            lines.extend(self._generate_rust_init_unix())

        # Java 项目初始化
        if env.project_type == ProjectType.JAVA:
            lines.extend(self._generate_java_init_unix())

        lines.extend([
            "",
            "echo ''",
            "echo '✅ 项目初始化完成！'",
            "echo ''",
        ])

        return "\n".join(lines)

    def _generate_windows_script(self) -> str:
        """生成 Windows 初始化脚本内容"""
        env = self.environment

        lines = [
            "@echo off",
            "REM FoxCode 项目初始化脚本",
            f"REM 生成时间: {datetime.now().isoformat()}",
            f"REM 项目类型: {env.project_type.value}",
            "",
            "echo 🦊 FoxCode 项目初始化",
            "echo ========================",
            "",
        ]

        # 检测必需工具
        if env.required_tools:
            lines.append("REM 检测必需工具")
            for tool in env.required_tools:
                lines.append(f"where {tool} >nul 2>nul")
                lines.append("if errorlevel 1 (")
                lines.append(f"    echo ❌ 错误: 未找到 {tool}")
                lines.append(f"    echo    请先安装 {tool}")
                lines.append("    exit /b 1")
                lines.append(")")
            lines.append("")

        # Python 项目初始化
        if env.project_type in (ProjectType.PYTHON, ProjectType.MIXED):
            lines.extend(self._generate_python_init_windows())

        # Node.js 项目初始化
        if env.project_type in (ProjectType.NODEJS, ProjectType.MIXED):
            lines.extend(self._generate_nodejs_init_windows())

        # Go 项目初始化
        if env.project_type == ProjectType.GO:
            lines.extend(self._generate_go_init_windows())

        # Rust 项目初始化
        if env.project_type == ProjectType.RUST:
            lines.extend(self._generate_rust_init_windows())

        # Java 项目初始化
        if env.project_type == ProjectType.JAVA:
            lines.extend(self._generate_java_init_windows())

        lines.extend([
            "",
            "echo.",
            "echo ✅ 项目初始化完成！",
            "echo.",
        ])

        return "\n".join(lines)

    def _generate_python_init_unix(self) -> list[str]:
        """生成 Python 项目初始化命令（Unix）"""
        lines = [
            "",
            "# Python 项目初始化",
            "echo ''",
            "echo '📦 初始化 Python 环境...'",
        ]

        env = self.environment

        # 创建虚拟环境
        lines.append("if [ ! -d 'venv' ]; then")
        if env.python_version:
            lines.append(f"    python{env.python_version} -m venv venv")
        else:
            lines.append("    python3 -m venv venv")
        lines.append("fi")
        lines.append("source venv/bin/activate")
        lines.append("")

        # 安装依赖
        if any(d.dep_type == DependencyType.PIP for d in env.dependencies):
            lines.append("echo '安装 Python 依赖...'")
            lines.append("pip install --upgrade pip")
            if (self.working_dir / "requirements.txt").exists():
                lines.append("pip install -r requirements.txt")
            elif (self.working_dir / "pyproject.toml").exists():
                lines.append("pip install -e .")

        return lines

    def _generate_python_init_windows(self) -> list[str]:
        """生成 Python 项目初始化命令（Windows）"""
        lines = [
            "",
            "REM Python 项目初始化",
            "echo.",
            "echo 📦 初始化 Python 环境...",
        ]

        # 创建虚拟环境
        lines.append("if not exist venv (")
        lines.append("    python -m venv venv")
        lines.append(")")
        lines.append("call venv\\Scripts\\activate.bat")
        lines.append("")

        # 安装依赖
        if any(d.dep_type == DependencyType.PIP for d in self.environment.dependencies):
            lines.append("echo 安装 Python 依赖...")
            lines.append("pip install --upgrade pip")
            if (self.working_dir / "requirements.txt").exists():
                lines.append("pip install -r requirements.txt")
            elif (self.working_dir / "pyproject.toml").exists():
                lines.append("pip install -e .")

        return lines

    def _generate_nodejs_init_unix(self) -> list[str]:
        """生成 Node.js 项目初始化命令（Unix）"""
        lines = [
            "",
            "# Node.js 项目初始化",
            "echo ''",
            "echo '📦 初始化 Node.js 环境...'",
        ]

        # 检测包管理器
        if "yarn" in self.environment.required_tools:
            lines.append("yarn install")
        elif "pnpm" in self.environment.required_tools:
            lines.append("pnpm install")
        else:
            lines.append("npm install")

        return lines

    def _generate_nodejs_init_windows(self) -> list[str]:
        """生成 Node.js 项目初始化命令（Windows）"""
        lines = [
            "",
            "REM Node.js 项目初始化",
            "echo.",
            "echo 📦 初始化 Node.js 环境...",
        ]

        # 检测包管理器
        if "yarn" in self.environment.required_tools:
            lines.append("yarn install")
        elif "pnpm" in self.environment.required_tools:
            lines.append("pnpm install")
        else:
            lines.append("npm install")

        return lines

    def _generate_go_init_unix(self) -> list[str]:
        """生成 Go 项目初始化命令（Unix）"""
        return [
            "",
            "# Go 项目初始化",
            "echo ''",
            "echo '📦 初始化 Go 环境...'",
            "go mod download",
        ]

    def _generate_go_init_windows(self) -> list[str]:
        """生成 Go 项目初始化命令（Windows）"""
        return [
            "",
            "REM Go 项目初始化",
            "echo.",
            "echo 📦 初始化 Go 环境...",
            "go mod download",
        ]

    def _generate_rust_init_unix(self) -> list[str]:
        """生成 Rust 项目初始化命令（Unix）"""
        return [
            "",
            "# Rust 项目初始化",
            "echo ''",
            "echo '📦 初始化 Rust 环境...'",
            "cargo build",
        ]

    def _generate_rust_init_windows(self) -> list[str]:
        """生成 Rust 项目初始化命令（Windows）"""
        return [
            "",
            "REM Rust 项目初始化",
            "echo.",
            "echo 📦 初始化 Rust 环境...",
            "cargo build",
        ]

    def _generate_java_init_unix(self) -> list[str]:
        """生成 Java 项目初始化命令（Unix）"""
        lines = [
            "",
            "# Java 项目初始化",
            "echo ''",
            "echo '📦 初始化 Java 环境...'",
        ]

        if "maven" in self.environment.required_tools:
            lines.append("mvn dependency:resolve")
        elif "gradle" in self.environment.required_tools:
            lines.append("gradle build")

        return lines

    def _generate_java_init_windows(self) -> list[str]:
        """生成 Java 项目初始化命令（Windows）"""
        lines = [
            "",
            "REM Java 项目初始化",
            "echo.",
            "echo 📦 初始化 Java 环境...",
        ]

        if "maven" in self.environment.required_tools:
            lines.append("mvn dependency:resolve")
        elif "gradle" in self.environment.required_tools:
            lines.append("gradle build")

        return lines

    def validate_script(self, script_path: Path) -> tuple[bool, str]:
        """
        验证脚本是否可执行
        
        Args:
            script_path: 脚本文件路径
            
        Returns:
            (是否有效, 验证报告)
        """
        if not script_path.exists():
            return False, f"脚本文件不存在: {script_path}"

        try:
            content = script_path.read_text(encoding="utf-8")

            # 检查脚本是否为空
            if not content.strip():
                return False, "脚本文件为空"

            # 检查 Unix 脚本的 shebang
            if script_path.suffix == ".sh":
                if not content.startswith("#!/bin/bash"):
                    return False, "Unix 脚本缺少正确的 shebang"

            # 检查 Windows 脚本的格式
            if script_path.suffix == ".bat":
                if not content.startswith("@echo off"):
                    return False, "Windows 脚本缺少 @echo off"

            return True, "脚本验证通过"

        except Exception as e:
            return False, f"验证脚本失败: {e}"

    async def async_generate_init_script(self, output_dir: Path | None = None) -> dict[str, Path]:
        """
        异步生成初始化脚本
        
        Args:
            output_dir: 输出目录
            
        Returns:
            生成的脚本文件路径字典
        """
        return await asyncio.to_thread(self.generate_init_script, output_dir)


# ==================== 便捷函数 ====================

def create_init_scripts(working_dir: Path | str) -> dict[str, Path]:
    """
    创建初始化脚本的便捷函数
    
    Args:
        working_dir: 工作目录
        
    Returns:
        生成的脚本文件路径字典
    """
    generator = InitScriptGenerator(working_dir=Path(working_dir))
    return generator.generate_init_script()


def detect_project_type(working_dir: Path | str) -> ProjectType:
    """
    检测项目类型的便捷函数
    
    Args:
        working_dir: 工作目录
        
    Returns:
        项目类型
    """
    generator = InitScriptGenerator(working_dir=Path(working_dir))
    return generator.detect_environment().project_type
