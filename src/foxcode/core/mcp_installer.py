"""
FoxCode MCP 安装器模块

实现从 GitHub URL 安装 MCP 服务器和 Skills 的功能
支持自动克隆、检测和安装

安全说明：
- 只允许从 GitHub.com 克隆仓库
- 对 URL 进行严格验证
- 限制克隆目标目录
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class InstallStatus(str, Enum):
    """安装状态"""
    PENDING = "pending"
    CLONING = "cloning"
    DETECTING = "detecting"
    INSTALLING = "installing"
    COMPLETED = "completed"
    FAILED = "failed"
    ALREADY_EXISTS = "already_exists"


class InstallType(str, Enum):
    """安装类型"""
    SKILL = "skill"
    MCP_SERVER = "mcp_server"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"


@dataclass
class SkillInfo:
    """Skill 信息"""
    name: str
    path: Path
    description: str = ""
    version: str = "1.0.0"
    enabled: bool = True


@dataclass
class MCPServerInfo:
    """MCP 服务器信息"""
    name: str
    path: Path
    config: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


@dataclass
class InstallResult:
    """安装结果"""
    status: InstallStatus
    install_type: InstallType
    source_url: str
    target_path: Path | None = None
    skills: list[SkillInfo] = field(default_factory=list)
    mcp_servers: list[MCPServerInfo] = field(default_factory=list)
    error: str | None = None
    message: str = ""


class GitHubURLValidator(BaseModel):
    """GitHub URL 验证器"""
    url: str = Field(description="GitHub 仓库 URL")
    
    @field_validator("url", mode="after")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        """验证是否为有效的 GitHub URL"""
        if not v:
            raise ValueError("URL 不能为空")
        
        v = v.strip()
        
        # 支持 https://github.com/user/repo 格式
        if v.endswith(".git"):
            v = v[:-4]
        
        # 解析 URL
        parsed = urlparse(v)
        
        # 检查是否为 GitHub
        if parsed.netloc.lower() not in ("github.com", "www.github.com"):
            raise ValueError(f"只支持 GitHub 仓库，当前域名: {parsed.netloc}")
        
        # 检查路径格式
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) < 2:
            raise ValueError(f"无效的 GitHub 仓库路径: {parsed.path}")
        
        return v
    
    def get_repo_info(self) -> tuple[str, str]:
        """获取仓库信息 (owner, repo)"""
        parsed = urlparse(self.url.rstrip("/"))
        path_parts = parsed.path.strip("/").split("/")
        return path_parts[0], path_parts[1]
    
    def get_clone_url(self) -> str:
        """获取克隆 URL"""
        return f"{self.url}.git"


class MCPInstaller:
    """
    MCP 安装器
    
    从 GitHub URL 安装 MCP 服务器和 Skills
    """
    
    def __init__(self, foxcode_dir: Path):
        """
        初始化安装器
        
        Args:
            foxcode_dir: .foxcode 目录路径
        """
        self.foxcode_dir = foxcode_dir
        self.skills_dir = foxcode_dir / "skills"
        self.mcp_dir = foxcode_dir / "mcp"
        self._logger = logging.getLogger("foxcode.mcp.installer")
        
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        """确保目录存在"""
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.mcp_dir.mkdir(parents=True, exist_ok=True)
    
    def validate_url(self, url: str) -> tuple[bool, str]:
        """
        验证 URL 是否有效
        
        Args:
            url: GitHub URL
            
        Returns:
            (是否有效, 原因消息)
        """
        try:
            validator = GitHubURLValidator(url=url)
            return True, f"有效的 GitHub 仓库: {validator.get_repo_info()[0]}/{validator.get_repo_info()[1]}"
        except Exception as e:
            return False, str(e)
    
    async def install_from_url(self, url: str, force: bool = False) -> InstallResult:
        """
        从 URL 安装
        
        Args:
            url: GitHub URL
            force: 是否强制重新安装
            
        Returns:
            安装结果
        """
        # 验证 URL
        is_valid, message = self.validate_url(url)
        if not is_valid:
            return InstallResult(
                status=InstallStatus.FAILED,
                install_type=InstallType.UNKNOWN,
                source_url=url,
                error=message,
            )
        
        try:
            validator = GitHubURLValidator(url=url)
            owner, repo = validator.get_repo_info()
            clone_url = validator.get_clone_url()
            
            # 目标目录
            target_path = self.mcp_dir / f"{owner}_{repo}"
            
            # 检查是否已存在
            if target_path.exists() and not force:
                return InstallResult(
                    status=InstallStatus.ALREADY_EXISTS,
                    install_type=InstallType.UNKNOWN,
                    source_url=url,
                    target_path=target_path,
                    message=f"仓库已存在: {target_path}，使用 --force 强制重新安装",
                )
            
            # 如果强制安装且目录存在，先删除
            if target_path.exists() and force:
                self._logger.info(f"删除已存在的目录: {target_path}")
                shutil.rmtree(target_path, ignore_errors=True)
            
            # 克隆仓库
            self._logger.info(f"开始克隆仓库: {clone_url}")
            clone_result = await self._clone_repository(clone_url, target_path)
            
            if not clone_result:
                return InstallResult(
                    status=InstallStatus.FAILED,
                    install_type=InstallType.UNKNOWN,
                    source_url=url,
                    target_path=target_path,
                    error="克隆仓库失败",
                )
            
            # 检测内容类型
            self._logger.info(f"检测仓库内容: {target_path}")
            install_type, skills, mcp_servers = await self._detect_content(target_path)
            
            # 安装 skills
            installed_skills = []
            if skills:
                self._logger.info(f"安装 {len(skills)} 个 skills")
                for skill_info in skills:
                    installed = await self._install_skill(skill_info)
                    if installed:
                        installed_skills.append(skill_info)
            
            # 安装 MCP 服务器
            installed_servers = []
            if mcp_servers:
                self._logger.info(f"安装 {len(mcp_servers)} 个 MCP 服务器")
                for server_info in mcp_servers:
                    installed = await self._install_mcp_server(server_info)
                    if installed:
                        installed_servers.append(server_info)
            
            return InstallResult(
                status=InstallStatus.COMPLETED,
                install_type=install_type,
                source_url=url,
                target_path=target_path,
                skills=installed_skills,
                mcp_servers=installed_servers,
                message=f"安装完成: {len(installed_skills)} 个 skills, {len(installed_servers)} 个 MCP 服务器",
            )
            
        except Exception as e:
            self._logger.error(f"安装失败: {e}")
            return InstallResult(
                status=InstallStatus.FAILED,
                install_type=InstallType.UNKNOWN,
                source_url=url,
                error=str(e),
            )
    
    async def _clone_repository(self, clone_url: str, target_path: Path) -> bool:
        """
        克隆仓库
        
        Args:
            clone_url: 克隆 URL
            target_path: 目标路径
            
        Returns:
            是否成功
        """
        try:
            # 使用 git clone 命令
            cmd = ["git", "clone", "--depth", "1", clone_url, str(target_path)]
            
            self._logger.debug(f"执行命令: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                self._logger.error(f"克隆失败: {stderr.decode('utf-8', errors='ignore')}")
                return False
            
            self._logger.info(f"克隆成功: {target_path}")
            return True
            
        except FileNotFoundError:
            self._logger.error("git 命令未找到，请确保已安装 git")
            return False
        except Exception as e:
            self._logger.error(f"克隆异常: {e}")
            return False
    
    async def _detect_content(self, repo_path: Path) -> tuple[InstallType, list[SkillInfo], list[MCPServerInfo]]:
        """
        检测仓库内容
        
        Args:
            repo_path: 仓库路径
            
        Returns:
            (安装类型, skills 列表, MCP 服务器列表)
        """
        skills: list[SkillInfo] = []
        mcp_servers: list[MCPServerInfo] = []
        
        # 检测 skills 目录
        skills_path = repo_path / ".claude" / "skills"
        if skills_path.exists() and skills_path.is_dir():
            for skill_file in skills_path.glob("**/*.md"):
                skill_info = self._parse_skill_file(skill_file)
                if skill_info:
                    skills.append(skill_info)
        
        # 检测 skill.py 文件
        for skill_file in repo_path.glob("**/skill.py"):
            skill_info = self._parse_skill_py_file(skill_file)
            if skill_info:
                skills.append(skill_info)
        
        # 检测 MCP 服务器配置
        mcp_config_path = repo_path / "mcp.json"
        if mcp_config_path.exists():
            mcp_info = await self._parse_mcp_config(mcp_config_path)
            if mcp_info:
                mcp_servers.extend(mcp_info)
        
        # 检测 package.json (可能是 MCP 服务器)
        package_json = repo_path / "package.json"
        if package_json.exists():
            mcp_info = await self._parse_package_json(package_json)
            if mcp_info:
                mcp_servers.extend(mcp_info)
        
        # 确定安装类型
        if skills and mcp_servers:
            install_type = InstallType.HYBRID
        elif skills:
            install_type = InstallType.SKILL
        elif mcp_servers:
            install_type = InstallType.MCP_SERVER
        else:
            install_type = InstallType.UNKNOWN
        
        return install_type, skills, mcp_servers
    
    def _parse_skill_file(self, skill_file: Path) -> SkillInfo | None:
        """
        解析 skill 文件 (.md 格式)
        
        Args:
            skill_file: skill 文件路径
            
        Returns:
            Skill 信息
        """
        try:
            content = skill_file.read_text(encoding="utf-8")
            
            # 提取名称（从文件名或标题）
            name = skill_file.stem
            
            # 尝试从内容中提取描述
            description = ""
            lines = content.split("\n")
            for line in lines[:10]:
                if line.startswith("# "):
                    name = line[2:].strip()
                elif line.strip() and not description:
                    description = line.strip()
            
            return SkillInfo(
                name=name,
                path=skill_file,
                description=description[:200] if description else f"Skill: {name}",
            )
            
        except Exception as e:
            self._logger.warning(f"解析 skill 文件失败: {skill_file}, {e}")
            return None
    
    def _parse_skill_py_file(self, skill_file: Path) -> SkillInfo | None:
        """
        解析 Python skill 文件
        
        Args:
            skill_file: skill.py 文件路径
            
        Returns:
            Skill 信息
        """
        try:
            content = skill_file.read_text(encoding="utf-8")
            
            # 提取类名和描述
            name = skill_file.parent.name  # 使用目录名作为 skill 名称
            description = ""
            
            # 尝试从 docstring 提取描述
            import ast
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        if ast.get_docstring(node):
                            description = ast.get_docstring(node) or ""
                            break
            except Exception:
                pass
            
            return SkillInfo(
                name=name,
                path=skill_file,
                description=description[:200] if description else f"Python Skill: {name}",
            )
            
        except Exception as e:
            self._logger.warning(f"解析 Python skill 文件失败: {skill_file}, {e}")
            return None
    
    async def _parse_mcp_config(self, config_path: Path) -> list[MCPServerInfo]:
        """
        解析 MCP 配置文件
        
        Args:
            config_path: 配置文件路径
            
        Returns:
            MCP 服务器信息列表
        """
        import json
        
        try:
            content = config_path.read_text(encoding="utf-8")
            config = json.loads(content)
            
            servers = []
            
            # 处理 mcpServers 格式
            if "mcpServers" in config:
                for name, server_config in config["mcpServers"].items():
                    servers.append(MCPServerInfo(
                        name=name,
                        path=config_path.parent,
                        config=server_config,
                    ))
            
            return servers
            
        except Exception as e:
            self._logger.warning(f"解析 MCP 配置失败: {config_path}, {e}")
            return []
    
    async def _parse_package_json(self, package_path: Path) -> list[MCPServerInfo]:
        """
        解析 package.json 文件
        
        Args:
            package_path: package.json 路径
            
        Returns:
            MCP 服务器信息列表
        """
        import json
        
        try:
            content = package_path.read_text(encoding="utf-8")
            package = json.loads(content)
            
            servers = []
            
            # 检查是否是 MCP 服务器
            name = package.get("name", package_path.parent.name)
            
            # 如果有 bin 字段，可能是 MCP 服务器
            if "bin" in package:
                servers.append(MCPServerInfo(
                    name=name,
                    path=package_path.parent,
                    config={
                        "command": "node",
                        "args": [str(package_path.parent / package["bin"])],
                    },
                ))
            
            return servers
            
        except Exception as e:
            self._logger.warning(f"解析 package.json 失败: {package_path}, {e}")
            return []
    
    async def _install_skill(self, skill_info: SkillInfo) -> bool:
        """
        安装 skill
        
        Args:
            skill_info: Skill 信息
            
        Returns:
            是否成功
        """
        try:
            # 创建目标目录
            target_dir = self.skills_dir / skill_info.name
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # 复制文件
            if skill_info.path.is_file():
                target_file = target_dir / skill_info.path.name
                shutil.copy2(skill_info.path, target_file)
            else:
                # 如果是目录，复制整个目录
                shutil.copytree(skill_info.path, target_dir, dirs_exist_ok=True)
            
            self._logger.info(f"Skill 安装成功: {skill_info.name}")
            return True
            
        except Exception as e:
            self._logger.error(f"Skill 安装失败: {skill_info.name}, {e}")
            return False
    
    async def _install_mcp_server(self, server_info: MCPServerInfo) -> bool:
        """
        安装 MCP 服务器
        
        Args:
            server_info: MCP 服务器信息
            
        Returns:
            是否成功
        """
        try:
            # 创建目标目录
            target_dir = self.mcp_dir / server_info.name
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # 如果需要，安装依赖
            package_json = server_info.path / "package.json"
            if package_json.exists():
                # 运行 npm install
                cmd = ["npm", "install"]
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=str(server_info.path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await process.communicate()
            
            self._logger.info(f"MCP 服务器安装成功: {server_info.name}")
            return True
            
        except Exception as e:
            self._logger.error(f"MCP 服务器安装失败: {server_info.name}, {e}")
            return False
    
    def list_installed_skills(self) -> list[SkillInfo]:
        """列出已安装的 skills"""
        skills = []
        
        if self.skills_dir.exists():
            for skill_dir in self.skills_dir.iterdir():
                if skill_dir.is_dir():
                    # 查找 skill 文件
                    for pattern in ["*.md", "skill.py"]:
                        for skill_file in skill_dir.glob(pattern):
                            if skill_file.suffix == ".md":
                                skill_info = self._parse_skill_file(skill_file)
                            else:
                                skill_info = self._parse_skill_py_file(skill_file)
                            
                            if skill_info:
                                skills.append(skill_info)
                                break
        
        return skills
    
    def list_installed_mcp_servers(self) -> list[MCPServerInfo]:
        """列出已安装的 MCP 服务器"""
        servers = []
        
        if self.mcp_dir.exists():
            for server_dir in self.mcp_dir.iterdir():
                if server_dir.is_dir():
                    servers.append(MCPServerInfo(
                        name=server_dir.name,
                        path=server_dir,
                    ))
        
        return servers
    
    def uninstall_skill(self, name: str) -> bool:
        """
        卸载 skill
        
        Args:
            name: Skill 名称
            
        Returns:
            是否成功
        """
        skill_path = self.skills_dir / name
        
        if not skill_path.exists():
            return False
        
        try:
            shutil.rmtree(skill_path, ignore_errors=True)
            self._logger.info(f"Skill 已卸载: {name}")
            return True
        except Exception as e:
            self._logger.error(f"卸载 Skill 失败: {name}, {e}")
            return False
    
    def uninstall_mcp_server(self, name: str) -> bool:
        """
        卸载 MCP 服务器
        
        Args:
            name: 服务器名称
            
        Returns:
            是否成功
        """
        server_path = self.mcp_dir / name
        
        if not server_path.exists():
            return False
        
        try:
            shutil.rmtree(server_path, ignore_errors=True)
            self._logger.info(f"MCP 服务器已卸载: {name}")
            return True
        except Exception as e:
            self._logger.error(f"卸载 MCP 服务器失败: {name}, {e}")
            return False


def get_installer(working_dir: Path | None = None) -> MCPInstaller:
    """
    获取 MCP 安装器实例
    
    Args:
        working_dir: 工作目录，默认为当前目录
        
    Returns:
        MCP 安装器实例
    """
    if working_dir is None:
        working_dir = Path.cwd()
    
    foxcode_dir = working_dir / ".foxcode"
    return MCPInstaller(foxcode_dir)
