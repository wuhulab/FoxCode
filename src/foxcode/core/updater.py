"""
FoxCode 版本更新模块

处理版本检查、GitHub releases 获取和自动更新功能。
支持从 GitHub releases 拉取最新版本并对比本地版本。

功能：
- 从 GitHub API 获取最新 releases
- 版本号比较（语义化版本）
- 自动下载更新包
- 支持增量更新和完整更新
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import re
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

logger = logging.getLogger(__name__)

# GitHub 仓库信息
GITHUB_REPO_OWNER = "wuhulab"
GITHUB_REPO_NAME = "FoxCode"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}"
GITHUB_RELEASES_URL = f"{GITHUB_API_URL}/releases"


class UpdateStatus(str, Enum):
    """更新状态枚举"""
    UP_TO_DATE = "up_to_date"           # 已是最新版本
    UPDATE_AVAILABLE = "update_available"  # 有可用更新
    UPDATE_DOWNLOADING = "downloading"   # 正在下载
    UPDATE_INSTALLING = "installing"     # 正在安装
    UPDATE_SUCCESS = "success"           # 更新成功
    UPDATE_FAILED = "failed"             # 更新失败
    NETWORK_ERROR = "network_error"      # 网络错误
    CHECK_FAILED = "check_failed"        # 检查失败


@dataclass
class ReleaseInfo:
    """
    发布版本信息
    
    存储从 GitHub releases API 获取的版本信息
    """
    version: str                        # 版本号（如 "0.2.0"）
    tag_name: str                       # Git 标签名（如 "v0.2.0"）
    title: str                          # 发布标题
    body: str                           # 发布说明
    published_at: str                   # 发布时间
    html_url: str                       # GitHub 页面链接
    assets: list[dict[str, Any]] = field(default_factory=list)  # 资产列表
    prerelease: bool = False            # 是否为预发布版本
    draft: bool = False                 # 是否为草稿
    
    def get_download_url(self, platform_name: str | None = None) -> str | None:
        """
        获取指定平台的下载链接
        
        Args:
            platform_name: 平台名称（windows/linux/darwin），为 None 则返回第一个资产
            
        Returns:
            下载链接，如果没有匹配则返回 None
        """
        if not self.assets:
            return None
        
        if platform_name is None:
            return self.assets[0].get("browser_download_url")
        
        # 平台名称映射
        platform_patterns = {
            "windows": ["windows", "win", "win32", "win64"],
            "linux": ["linux", "ubuntu", "debian"],
            "darwin": ["darwin", "macos", "mac", "osx"],
        }
        
        patterns = platform_patterns.get(platform_name.lower(), [platform_name.lower()])
        
        for asset in self.assets:
            name = asset.get("name", "").lower()
            for pattern in patterns:
                if pattern in name:
                    return asset.get("browser_download_url")
        
        return None
    
    def get_file_size(self, platform_name: str | None = None) -> int:
        """
        获取下载文件大小（字节）
        
        Args:
            platform_name: 平台名称
            
        Returns:
            文件大小（字节），如果未找到则返回 0
        """
        if not self.assets:
            return 0
        
        if platform_name is None:
            return self.assets[0].get("size", 0)
        
        platform_patterns = {
            "windows": ["windows", "win", "win32", "win64"],
            "linux": ["linux", "ubuntu", "debian"],
            "darwin": ["darwin", "macos", "mac", "osx"],
        }
        
        patterns = platform_patterns.get(platform_name.lower(), [platform_name.lower()])
        
        for asset in self.assets:
            name = asset.get("name", "").lower()
            for pattern in patterns:
                if pattern in name:
                    return asset.get("size", 0)
        
        return 0


@dataclass
class UpdateResult:
    """
    更新结果
    
    存储更新操作的结果信息
    """
    status: UpdateStatus                # 更新状态
    current_version: str                # 当前版本
    latest_version: str | None = None   # 最新版本
    release_info: ReleaseInfo | None = None  # 发布信息
    message: str = ""                   # 结果消息
    error: str | None = None            # 错误信息
    download_path: Path | None = None   # 下载文件路径
    installed: bool = False             # 是否已安装


class VersionComparator:
    """
    版本比较器
    
    支持语义化版本比较（Semantic Versioning）
    """
    
    # 版本号正则表达式
    VERSION_PATTERN = re.compile(
        r'^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[-._]?(alpha|beta|rc|pre|post|dev|a|b|c)(?:[-._]?(\d+))?)?$',
        re.IGNORECASE
    )
    
    @classmethod
    def parse_version(cls, version: str) -> tuple[int, int, int, str, int]:
        """
        解析版本号
        
        Args:
            version: 版本字符串（如 "0.1.0", "v0.2.0-beta.1"）
            
        Returns:
            (major, minor, patch, prerelease_type, prerelease_num)
        """
        # 清理版本字符串
        version = version.strip().lstrip('v')
        
        match = cls.VERSION_PATTERN.match(version)
        if not match:
            # 尝试简单解析
            parts = version.split('.')
            major = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
            minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            patch = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
            return (major, minor, patch, "", 0)
        
        major = int(match.group(1))
        minor = int(match.group(2)) if match.group(2) else 0
        patch = int(match.group(3)) if match.group(3) else 0
        
        prerelease_type = match.group(4).lower() if match.group(4) else ""
        prerelease_num = int(match.group(5)) if match.group(5) else 0
        
        return (major, minor, patch, prerelease_type, prerelease_num)
    
    @classmethod
    def compare(cls, version1: str, version2: str) -> int:
        """
        比较两个版本号
        
        Args:
            version1: 版本1
            version2: 版本2
            
        Returns:
            -1: version1 < version2
             0: version1 == version2
             1: version1 > version2
        """
        v1 = cls.parse_version(version1)
        v2 = cls.parse_version(version2)
        
        # 比较主版本号
        for i in range(3):
            if v1[i] < v2[i]:
                return -1
            if v1[i] > v2[i]:
                return 1
        
        # 比较预发布版本
        # 正式版 > 预发布版
        prerelease_order = {
            "": 100,        # 正式版
            "rc": 50,       # Release Candidate
            "beta": 40,     # Beta
            "b": 40,
            "alpha": 30,    # Alpha
            "a": 30,
            "pre": 20,      # Pre-release
            "c": 20,
            "post": 60,     # Post-release
            "dev": 10,      # Development
        }
        
        v1_pre_type = prerelease_order.get(v1[3], 0)
        v2_pre_type = prerelease_order.get(v2[3], 0)
        
        if v1_pre_type < v2_pre_type:
            return -1
        if v1_pre_type > v2_pre_type:
            return 1
        
        # 比较预发布版本号
        if v1[4] < v2[4]:
            return -1
        if v1[4] > v2[4]:
            return 1
        
        return 0
    
    @classmethod
    def is_newer(cls, version1: str, version2: str) -> bool:
        """
        判断 version1 是否比 version2 新
        
        Args:
            version1: 版本1
            version2: 版本2
            
        Returns:
            version1 是否比 version2 新
        """
        return cls.compare(version1, version2) > 0


class GitHubReleasesClient:
    """
    GitHub Releases API 客户端
    
    处理与 GitHub API 的交互
    """
    
    def __init__(
        self,
        repo_owner: str = GITHUB_REPO_OWNER,
        repo_name: str = GITHUB_REPO_NAME,
        timeout: int = 30,
    ):
        """
        初始化客户端
        
        Args:
            repo_owner: 仓库所有者
            repo_name: 仓库名称
            timeout: 请求超时时间（秒）
        """
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.timeout = timeout
        self.base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
    
    def _make_request(self, url: str) -> dict[str, Any] | list[Any] | None:
        """
        发送 HTTP 请求
        
        Args:
            url: 请求 URL
            
        Returns:
            JSON 响应数据，失败返回 None
        """
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"FoxCode-Updater/{self._get_current_version()}",
        }
        
        # 如果有 GitHub Token，添加到请求头
        github_token = os.environ.get("GITHUB_TOKEN")
        if github_token:
            headers["Authorization"] = f"token {github_token}"
        
        try:
            request = Request(url, headers=headers)
            with urlopen(request, timeout=self.timeout) as response:
                data = response.read().decode('utf-8')
                return json.loads(data)
        except HTTPError as e:
            logger.error(f"HTTP 错误: {e.code} - {e.reason}")
            if e.code == 403:
                logger.warning("API 请求频率限制，请稍后重试")
            return None
        except URLError as e:
            logger.error(f"网络错误: {e.reason}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析错误: {e}")
            return None
        except Exception as e:
            logger.error(f"请求失败: {e}")
            return None
    
    def _get_current_version(self) -> str:
        """获取当前版本"""
        try:
            from foxcode import __version__
            return __version__
        except ImportError:
            return "0.0.0"
    
    def get_latest_release(self, include_prerelease: bool = False) -> ReleaseInfo | None:
        """
        获取最新发布版本
        
        Args:
            include_prerelease: 是否包含预发布版本
            
        Returns:
            ReleaseInfo 对象，失败返回 None
        """
        if include_prerelease:
            # 获取所有 releases，然后找到最新的
            releases = self.get_releases(limit=10)
            if not releases:
                return None
            
            # 过滤掉草稿，找到最新的
            for release in releases:
                if not release.draft:
                    return release
            return None
        else:
            # 获取最新正式版本
            url = f"{self.base_url}/releases/latest"
            data = self._make_request(url)
            
            if data and isinstance(data, dict):
                return self._parse_release(data)
            
            return None
    
    def get_releases(self, limit: int = 10) -> list[ReleaseInfo]:
        """
        获取发布版本列表
        
        Args:
            limit: 最大返回数量
            
        Returns:
            ReleaseInfo 列表
        """
        url = f"{self.base_url}/releases?per_page={limit}"
        data = self._make_request(url)
        
        if not data or not isinstance(data, list):
            return []
        
        releases = []
        for item in data:
            release = self._parse_release(item)
            if release:
                releases.append(release)
        
        return releases
    
    def get_release_by_tag(self, tag: str) -> ReleaseInfo | None:
        """
        根据标签获取发布版本
        
        Args:
            tag: Git 标签名
            
        Returns:
            ReleaseInfo 对象，失败返回 None
        """
        url = f"{self.base_url}/releases/tags/{tag}"
        data = self._make_request(url)
        
        if data and isinstance(data, dict):
            return self._parse_release(data)
        
        return None
    
    def _parse_release(self, data: dict[str, Any]) -> ReleaseInfo | None:
        """
        解析 release 数据
        
        Args:
            data: API 返回的数据
            
        Returns:
            ReleaseInfo 对象
        """
        try:
            return ReleaseInfo(
                version=data.get("tag_name", "").lstrip('v'),
                tag_name=data.get("tag_name", ""),
                title=data.get("name", ""),
                body=data.get("body", ""),
                published_at=data.get("published_at", ""),
                html_url=data.get("html_url", ""),
                assets=data.get("assets", []),
                prerelease=data.get("prerelease", False),
                draft=data.get("draft", False),
            )
        except Exception as e:
            logger.error(f"解析 release 数据失败: {e}")
            return None


class UpdateDownloader:
    """
    更新下载器
    
    处理更新包的下载和验证
    """
    
    def __init__(
        self,
        download_dir: Path | None = None,
        chunk_size: int = 8192,
        timeout: int = 300,
    ):
        """
        初始化下载器
        
        Args:
            download_dir: 下载目录，为 None 则使用临时目录
            chunk_size: 下载块大小（字节）
            timeout: 下载超时时间（秒）
        """
        self.download_dir = download_dir or Path(tempfile.gettempdir()) / "foxcode_updates"
        self.chunk_size = chunk_size
        self.timeout = timeout
        
        # 确保下载目录存在
        self.download_dir.mkdir(parents=True, exist_ok=True)
    
    def download(
        self,
        url: str,
        filename: str | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Path | None:
        """
        下载文件
        
        Args:
            url: 下载链接
            filename: 文件名，为 None 则从 URL 提取
            progress_callback: 进度回调函数 (downloaded_bytes, total_bytes)
            
        Returns:
            下载文件路径，失败返回 None
        """
        if filename is None:
            filename = url.split('/')[-1] or "update.zip"
        
        filepath = self.download_dir / filename
        
        try:
            request = Request(
                url,
                headers={"User-Agent": "FoxCode-Updater"},
            )
            
            with urlopen(request, timeout=self.timeout) as response:
                total_size = int(response.headers.get('Content-Length', 0))
                downloaded = 0
                
                with open(filepath, 'wb') as f:
                    while True:
                        chunk = response.read(self.chunk_size)
                        if not chunk:
                            break
                        
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if progress_callback:
                            progress_callback(downloaded, total_size)
            
            logger.info(f"下载完成: {filepath}")
            return filepath
            
        except HTTPError as e:
            logger.error(f"下载失败 (HTTP {e.code}): {e.reason}")
            return None
        except URLError as e:
            logger.error(f"下载失败 (网络错误): {e.reason}")
            return None
        except Exception as e:
            logger.error(f"下载失败: {e}")
            # 清理不完整的文件
            if filepath.exists():
                filepath.unlink()
            return None
    
    def verify_checksum(self, filepath: Path, expected_hash: str | None = None) -> bool:
        """
        验证文件校验和
        
        Args:
            filepath: 文件路径
            expected_hash: 预期的哈希值（SHA256），为 None 则跳过验证
            
        Returns:
            是否验证通过
        """
        if not expected_hash:
            logger.warning("未提供校验和，跳过验证")
            return True
        
        try:
            import hashlib
            
            sha256_hash = hashlib.sha256()
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(self.chunk_size), b''):
                    sha256_hash.update(chunk)
            
            actual_hash = sha256_hash.hexdigest()
            
            if actual_hash.lower() == expected_hash.lower():
                logger.info("文件校验和验证通过")
                return True
            else:
                logger.error(f"文件校验和不匹配: 期望 {expected_hash}, 实际 {actual_hash}")
                return False
                
        except Exception as e:
            logger.error(f"校验和验证失败: {e}")
            return False


class UpdateInstaller:
    """
    更新安装器
    
    处理更新包的解压和安装
    """
    
    def __init__(self, backup_dir: Path | None = None):
        """
        初始化安装器
        
        Args:
            backup_dir: 备份目录
        """
        self.backup_dir = backup_dir or Path(tempfile.gettempdir()) / "foxcode_backup"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def install(
        self,
        archive_path: Path,
        target_dir: Path,
        create_backup: bool = True,
    ) -> bool:
        """
        安装更新
        
        Args:
            archive_path: 更新包路径
            target_dir: 目标安装目录
            create_backup: 是否创建备份
            
        Returns:
            是否安装成功
        """
        try:
            # 创建备份
            if create_backup:
                backup_path = self._create_backup(target_dir)
                if not backup_path:
                    logger.warning("创建备份失败，继续安装")
            
            # 解压更新包
            if archive_path.suffix.lower() == '.zip':
                success = self._extract_zip(archive_path, target_dir)
            elif archive_path.suffix.lower() in ['.tar', '.gz', '.tgz']:
                success = self._extract_tar(archive_path, target_dir)
            else:
                logger.error(f"不支持的压缩格式: {archive_path.suffix}")
                return False
            
            if success:
                logger.info(f"更新安装成功: {target_dir}")
            
            return success
            
        except Exception as e:
            logger.error(f"安装更新失败: {e}")
            return False
    
    def _create_backup(self, target_dir: Path) -> Path | None:
        """
        创建备份
        
        Args:
            target_dir: 要备份的目录
            
        Returns:
            备份路径，失败返回 None
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.backup_dir / f"foxcode_backup_{timestamp}"
            
            shutil.copytree(target_dir, backup_path)
            logger.info(f"备份创建成功: {backup_path}")
            
            return backup_path
            
        except Exception as e:
            logger.error(f"创建备份失败: {e}")
            return None
    
    def _extract_zip(self, archive_path: Path, target_dir: Path) -> bool:
        """
        解压 ZIP 文件
        
        Args:
            archive_path: ZIP 文件路径
            target_dir: 目标目录
            
        Returns:
            是否成功
        """
        try:
            with zipfile.ZipFile(archive_path, 'r') as zf:
                # 安全检查：防止路径穿越攻击
                for member in zf.namelist():
                    member_path = Path(member)
                    if member_path.is_absolute() or '..' in member:
                        logger.error(f"检测到不安全的路径: {member}")
                        return False
                
                # 解压文件
                zf.extractall(target_dir)
            
            return True
            
        except zipfile.BadZipFile as e:
            logger.error(f"无效的 ZIP 文件: {e}")
            return False
        except Exception as e:
            logger.error(f"解压失败: {e}")
            return False
    
    def _extract_tar(self, archive_path: Path, target_dir: Path) -> bool:
        """
        解压 TAR 文件
        
        Args:
            archive_path: TAR 文件路径
            target_dir: 目标目录
            
        Returns:
            是否成功
        """
        try:
            import tarfile
            
            with tarfile.open(archive_path, 'r:*') as tf:
                # 安全检查
                for member in tf.getmembers():
                    if member.name.startswith('/') or '..' in member.name:
                        logger.error(f"检测到不安全的路径: {member.name}")
                        return False
                
                tf.extractall(target_dir)
            
            return True
            
        except Exception as e:
            logger.error(f"解压 TAR 文件失败: {e}")
            return False
    
    def restore_backup(self, backup_path: Path, target_dir: Path) -> bool:
        """
        从备份恢复
        
        Args:
            backup_path: 备份路径
            target_dir: 目标目录
            
        Returns:
            是否恢复成功
        """
        try:
            if target_dir.exists():
                shutil.rmtree(target_dir)
            
            shutil.copytree(backup_path, target_dir)
            logger.info(f"从备份恢复成功: {backup_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"恢复备份失败: {e}")
            return False


class SourceCodeInstaller:
    """
    源码安装器
    
    从 GitHub 下载源码并在本地安装
    """
    
    def __init__(self, working_dir: Path | None = None):
        """
        初始化源码安装器
        
        Args:
            working_dir: 工作目录，用于存放临时文件
        """
        self.working_dir = working_dir or Path(tempfile.gettempdir()) / "foxcode_source"
        self.working_dir.mkdir(parents=True, exist_ok=True)
    
    def download_source(
        self,
        tag: str = "main",
        repo_owner: str = GITHUB_REPO_OWNER,
        repo_name: str = GITHUB_REPO_NAME,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Path | None:
        """
        下载源码
        
        Args:
            tag: Git 标签或分支名（如 "v0.2.0" 或 "main"）
            repo_owner: 仓库所有者
            repo_name: 仓库名称
            progress_callback: 进度回调函数 (downloaded_bytes, total_bytes)
            
        Returns:
            下载的源码压缩包路径，失败返回 None
        """
        # GitHub 源码下载链接
        archive_url = f"https://github.com/{repo_owner}/{repo_name}/archive/refs/heads/{tag}.zip"
        if tag.startswith("v"):
            # 如果是版本标签，使用 tags 路径
            archive_url = f"https://github.com/{repo_owner}/{repo_name}/archive/refs/tags/{tag}.zip"
        
        filename = f"{repo_name}-{tag}.zip"
        filepath = self.working_dir / filename
        
        logger.info(f"正在下载源码: {archive_url}")
        
        try:
            request = Request(
                archive_url,
                headers={"User-Agent": "FoxCode-Updater"},
            )
            
            with urlopen(request, timeout=300) as response:
                total_size = int(response.headers.get('Content-Length', 0))
                downloaded = 0
                
                with open(filepath, 'wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if progress_callback:
                            progress_callback(downloaded, total_size)
            
            logger.info(f"源码下载完成: {filepath}")
            return filepath
            
        except HTTPError as e:
            logger.error(f"下载源码失败 (HTTP {e.code}): {e.reason}")
            return None
        except URLError as e:
            logger.error(f"下载源码失败 (网络错误): {e.reason}")
            return None
        except Exception as e:
            logger.error(f"下载源码失败: {e}")
            if filepath.exists():
                filepath.unlink()
            return None
    
    def extract_source(self, archive_path: Path) -> Path | None:
        """
        解压源码
        
        Args:
            archive_path: 源码压缩包路径
            
        Returns:
            解压后的源码目录路径，失败返回 None
        """
        try:
            # 解压到同一目录
            extract_dir = archive_path.parent / f"extracted_{archive_path.stem}"
            
            # 如果目录已存在，先删除
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            
            with zipfile.ZipFile(archive_path, 'r') as zf:
                # 安全检查：防止路径穿越攻击
                for member in zf.namelist():
                    member_path = Path(member)
                    if member_path.is_absolute() or '..' in member:
                        logger.error(f"检测到不安全的路径: {member}")
                        return None
                
                # 解压文件
                zf.extractall(extract_dir)
            
            # 找到解压后的实际源码目录（通常是一个子目录）
            subdirs = list(extract_dir.iterdir())
            if len(subdirs) == 1 and subdirs[0].is_dir():
                source_dir = subdirs[0]
            else:
                source_dir = extract_dir
            
            logger.info(f"源码解压完成: {source_dir}")
            return source_dir
            
        except zipfile.BadZipFile as e:
            logger.error(f"无效的 ZIP 文件: {e}")
            return None
        except Exception as e:
            logger.error(f"解压源码失败: {e}")
            return None
    
    def install_from_source(
        self,
        source_dir: Path,
        upgrade: bool = True,
        editable: bool = False,
    ) -> tuple[bool, str]:
        """
        从源码安装
        
        Args:
            source_dir: 源码目录路径
            upgrade: 是否升级安装
            editable: 是否以可编辑模式安装
            
        Returns:
            (是否成功, 输出信息)
        """
        import subprocess
        
        # 检查源码目录是否存在
        if not source_dir.exists():
            return False, f"源码目录不存在: {source_dir}"
        
        # 检查是否有 setup.py 或 pyproject.toml
        has_setup = (source_dir / "setup.py").exists()
        has_pyproject = (source_dir / "pyproject.toml").exists()
        
        if not has_setup and not has_pyproject:
            return False, "源码目录中没有找到 setup.py 或 pyproject.toml"
        
        # 构建 pip install 命令
        cmd = [sys.executable, "-m", "pip", "install"]
        
        if upgrade:
            cmd.append("--upgrade")
        
        if editable:
            cmd.extend(["-e", str(source_dir)])
        else:
            cmd.append(str(source_dir))
        
        logger.info(f"正在执行安装命令: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5分钟超时
            )
            
            if result.returncode == 0:
                logger.info("源码安装成功")
                return True, result.stdout
            else:
                logger.error(f"源码安装失败: {result.stderr}")
                return False, result.stderr
                
        except subprocess.TimeoutExpired:
            logger.error("安装超时")
            return False, "安装超时，请检查网络连接或手动安装"
        except Exception as e:
            logger.error(f"安装失败: {e}")
            return False, str(e)
    
    def cleanup(self) -> None:
        """清理临时文件"""
        try:
            if self.working_dir.exists():
                shutil.rmtree(self.working_dir)
                logger.info("临时文件已清理")
        except Exception as e:
            logger.warning(f"清理临时文件失败: {e}")


class FoxCodeUpdater:
    """
    FoxCode 更新管理器
    
    整合版本检查、下载、安装等功能。
    支持从本地配置文件读取和保存版本配置。
    支持源码下载和本地安装。
    """
    
    def __init__(
        self,
        current_version: str | None = None,
        include_prerelease: bool = False,
        auto_backup: bool = True,
        config_path: Path | None = None,
        working_dir: Path | None = None,
        use_source_install: bool = True,
    ):
        """
        初始化更新管理器
        
        Args:
            current_version: 当前版本，为 None 则自动获取
            include_prerelease: 是否包含预发布版本
            auto_backup: 是否自动备份
            config_path: 配置文件路径，为 None 则自动查找
            working_dir: 工作目录，用于查找配置文件
            use_source_install: 是否使用源码安装方式
        """
        self.current_version = current_version or self._get_current_version()
        self.include_prerelease = include_prerelease
        self.auto_backup = auto_backup
        self.working_dir = working_dir or Path.cwd()
        self.use_source_install = use_source_install
        
        # 配置文件路径
        self.config_path = config_path or self._find_config_file()
        
        # 加载本地配置
        self._update_config = self._load_update_config()
        
        # 如果配置中指定了预发布版本，使用配置中的设置
        if self._update_config.get("include_prerelease", False):
            self.include_prerelease = True
        
        # 从配置获取 GitHub 仓库
        github_repo = self._update_config.get("github_repo", "wuhulab/FoxCode")
        if "/" in github_repo:
            repo_owner, repo_name = github_repo.split("/", 1)
        else:
            repo_owner, repo_name = "wuhulab", "FoxCode"
        
        self.client = GitHubReleasesClient(repo_owner=repo_owner, repo_name=repo_name)
        self.downloader = UpdateDownloader()
        self.installer = UpdateInstaller()
        self.source_installer = SourceCodeInstaller()
        
        # 状态
        self._latest_release: ReleaseInfo | None = None
        self._download_progress: float = 0.0
    
    def _get_current_version(self) -> str:
        """获取当前版本"""
        try:
            from foxcode import __version__
            return __version__
        except ImportError:
            return "0.0.0"
    
    def _get_platform_name(self) -> str:
        """获取当前平台名称"""
        system = platform.system().lower()
        if system == "windows":
            return "windows"
        elif system == "darwin":
            return "darwin"
        else:
            return "linux"
    
    def _find_config_file(self) -> Path:
        """
        查找配置文件
        
        按优先级查找：
        1. 工作目录下的 .foxcode.toml
        2. 工作目录下的 foxcode.toml
        3. 用户目录下的 ~/.foxcode/config.toml
        
        Returns:
            配置文件路径
        """
        search_paths = [
            self.working_dir / ".foxcode.toml",
            self.working_dir / "foxcode.toml",
            Path.home() / ".foxcode" / "config.toml",
        ]
        
        for path in search_paths:
            if path.exists():
                return path
        
        # 默认使用工作目录下的 .foxcode.toml
        return self.working_dir / ".foxcode.toml"
    
    def _load_update_config(self) -> dict[str, Any]:
        """
        从配置文件加载更新配置
        
        Returns:
            更新配置字典
        """
        if not self.config_path.exists():
            return {}
        
        try:
            if sys.version_info >= (3, 11):
                import tomllib
            else:
                import tomli as tomllib
            
            with open(self.config_path, "rb") as f:
                config = tomllib.load(f)
            
            return config.get("update", {})
        except Exception as e:
            logger.warning(f"加载更新配置失败: {e}")
            return {}
    
    def _save_update_config(self, updates: dict[str, Any]) -> bool:
        """
        保存更新配置到配置文件
        
        Args:
            updates: 要更新的配置项
            
        Returns:
            是否保存成功
        """
        try:
            # 读取现有配置
            existing_config = {}
            if self.config_path.exists():
                try:
                    if sys.version_info >= (3, 11):
                        import tomllib
                    else:
                        import tomli as tomllib
                    
                    with open(self.config_path, "rb") as f:
                        existing_config = tomllib.load(f)
                except Exception:
                    existing_config = {}
            
            # 更新 update 配置
            if "update" not in existing_config:
                existing_config["update"] = {}
            
            existing_config["update"].update(updates)
            
            # 写入配置文件
            try:
                import tomli_w
                with open(self.config_path, "wb") as f:
                    tomli_w.dump(existing_config, f)
                return True
            except ImportError:
                # 如果没有 tomli_w，使用简单格式写入
                return self._write_simple_config(existing_config)
            
        except Exception as e:
            logger.error(f"保存更新配置失败: {e}")
            return False
    
    def _write_simple_config(self, config: dict) -> bool:
        """
        简单的 TOML 配置写入（不依赖 tomli_w）
        
        Args:
            config: 配置字典
            
        Returns:
            是否写入成功
        """
        try:
            # 确保目录存在
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, "w", encoding="utf-8") as f:
                f.write('# FoxCode 配置文件\n')
                f.write(f'# 自动更新于 {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n')
                
                # 先写入顶级字段
                for key, value in config.items():
                    if not isinstance(value, dict):
                        self._write_toml_value(f, key, value)
                
                # 再写入节
                for key, value in config.items():
                    if isinstance(value, dict):
                        f.write(f'\n[{key}]\n')
                        for k, v in value.items():
                            self._write_toml_value(f, k, v, indent="    ")
            
            return True
        except Exception as e:
            logger.error(f"写入配置失败: {e}")
            return False
    
    def _write_toml_value(self, f, key: str, value, indent: str = "") -> None:
        """
        写入单个 TOML 值
        
        Args:
            f: 文件对象
            key: 键名
            value: 值
            indent: 缩进
        """
        if isinstance(value, str):
            f.write(f'{indent}{key} = "{value}"\n')
        elif isinstance(value, bool):
            f.write(f'{indent}{key} = {"true" if value else "false"}\n')
        elif isinstance(value, (int, float)):
            f.write(f'{indent}{key} = {value}\n')
        elif isinstance(value, list):
            if not value:
                f.write(f'{indent}{key} = []\n')
            elif all(isinstance(v, str) for v in value):
                formatted = ', '.join(f'"{v}"' for v in value)
                f.write(f'{indent}{key} = [{formatted}]\n')
            else:
                f.write(f'{indent}{key} = {value}\n')
        elif value is None:
            pass
        else:
            f.write(f'{indent}{key} = "{str(value)}"\n')
    
    def should_check_update(self) -> bool:
        """
        检查是否应该执行更新检查
        
        根据配置的检查间隔判断是否需要检查更新
        
        Returns:
            是否应该检查更新
        """
        # 检查是否启用自动检查
        if not self._update_config.get("auto_check", True):
            return False
        
        # 检查是否锁定版本
        locked_version = self._update_config.get("locked_version", "")
        if locked_version:
            return False
        
        # 检查上次检查时间
        last_check = self._update_config.get("last_check_time", "")
        if last_check:
            try:
                last_check_time = datetime.fromisoformat(last_check)
                interval_hours = self._update_config.get("check_interval_hours", 24)
                elapsed = datetime.now() - last_check_time
                if elapsed.total_seconds() < interval_hours * 3600:
                    return False
            except Exception:
                pass
        
        return True
    
    def is_version_skipped(self, version: str) -> bool:
        """
        检查版本是否被跳过
        
        Args:
            version: 版本号
            
        Returns:
            是否被跳过
        """
        skip_version = self._update_config.get("skip_version", "")
        return skip_version == version
    
    def is_version_locked(self) -> bool:
        """
        检查是否锁定版本
        
        Returns:
            是否锁定版本
        """
        return bool(self._update_config.get("locked_version", ""))
    
    def get_locked_version(self) -> str | None:
        """
        获取锁定的版本
        
        Returns:
            锁定的版本号，未锁定返回 None
        """
        locked = self._update_config.get("locked_version", "")
        return locked if locked else None
    
    def skip_version(self, version: str) -> bool:
        """
        跳过指定版本
        
        Args:
            version: 要跳过的版本号
            
        Returns:
            是否成功
        """
        return self._save_update_config({"skip_version": version})
    
    def lock_version(self, version: str) -> bool:
        """
        锁定到指定版本
        
        Args:
            version: 要锁定的版本号
            
        Returns:
            是否成功
        """
        return self._save_update_config({"locked_version": version})
    
    def unlock_version(self) -> bool:
        """
        解除版本锁定
        
        Returns:
            是否成功
        """
        return self._save_update_config({"locked_version": ""})
    
    def check_for_updates(self) -> UpdateResult:
        """
        检查更新
        
        Returns:
            UpdateResult 对象
        """
        try:
            logger.info("正在检查更新...")
            
            # 检查是否锁定版本
            locked_version = self.get_locked_version()
            if locked_version:
                logger.info(f"版本已锁定: {locked_version}")
                return UpdateResult(
                    status=UpdateStatus.UP_TO_DATE,
                    current_version=self.current_version,
                    latest_version=locked_version,
                    message=f"版本已锁定: {locked_version}",
                )
            
            # 获取最新版本
            latest_release = self.client.get_latest_release(
                include_prerelease=self.include_prerelease
            )
            
            if not latest_release:
                return UpdateResult(
                    status=UpdateStatus.CHECK_FAILED,
                    current_version=self.current_version,
                    message="无法获取最新版本信息",
                    error="GitHub API 请求失败",
                )
            
            self._latest_release = latest_release
            
            # 保存检查结果到配置文件
            self._save_update_config({
                "last_check_time": datetime.now().isoformat(),
                "last_known_version": latest_release.version,
            })
            
            # 检查是否跳过该版本
            if self.is_version_skipped(latest_release.version):
                return UpdateResult(
                    status=UpdateStatus.UP_TO_DATE,
                    current_version=self.current_version,
                    latest_version=latest_release.version,
                    release_info=latest_release,
                    message=f"已跳过版本: {latest_release.version}",
                )
            
            # 比较版本
            if VersionComparator.is_newer(latest_release.version, self.current_version):
                return UpdateResult(
                    status=UpdateStatus.UPDATE_AVAILABLE,
                    current_version=self.current_version,
                    latest_version=latest_release.version,
                    release_info=latest_release,
                    message=f"发现新版本: {latest_release.version}",
                )
            else:
                return UpdateResult(
                    status=UpdateStatus.UP_TO_DATE,
                    current_version=self.current_version,
                    latest_version=latest_release.version,
                    release_info=latest_release,
                    message="当前已是最新版本",
                )
                
        except Exception as e:
            logger.error(f"检查更新失败: {e}")
            return UpdateResult(
                status=UpdateStatus.CHECK_FAILED,
                current_version=self.current_version,
                message="检查更新失败",
                error=str(e),
            )
    
    def download_update(
        self,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> UpdateResult:
        """
        下载更新
        
        Args:
            progress_callback: 进度回调函数
            
        Returns:
            UpdateResult 对象
        """
        if not self._latest_release:
            check_result = self.check_for_updates()
            if check_result.status != UpdateStatus.UPDATE_AVAILABLE:
                return check_result
        
        release = self._latest_release
        platform_name = self._get_platform_name()
        
        # 获取下载链接
        download_url = release.get_download_url(platform_name)
        if not download_url:
            # 尝试获取通用包
            download_url = release.get_download_url()
        
        if not download_url:
            return UpdateResult(
                status=UpdateStatus.UPDATE_FAILED,
                current_version=self.current_version,
                latest_version=release.version,
                message="未找到适合当前平台的更新包",
                error=f"平台 {platform_name} 没有对应的更新包",
            )
        
        # 下载文件
        file_size = release.get_file_size(platform_name)
        filename = download_url.split('/')[-1]
        
        logger.info(f"正在下载更新: {filename} ({file_size / 1024 / 1024:.1f} MB)")
        
        download_path = self.downloader.download(
            download_url,
            filename,
            progress_callback,
        )
        
        if not download_path:
            return UpdateResult(
                status=UpdateStatus.NETWORK_ERROR,
                current_version=self.current_version,
                latest_version=release.version,
                message="下载更新失败",
                error="网络错误或下载中断",
            )
        
        return UpdateResult(
            status=UpdateStatus.UPDATE_DOWNLOADING,
            current_version=self.current_version,
            latest_version=release.version,
            release_info=release,
            message="下载完成",
            download_path=download_path,
        )
    
    def install_update(
        self,
        download_path: Path | None = None,
        target_dir: Path | None = None,
    ) -> UpdateResult:
        """
        安装更新
        
        Args:
            download_path: 下载文件路径，为 None 则使用最近下载的文件
            target_dir: 目标安装目录，为 None 则自动检测
            
        Returns:
            UpdateResult 对象
        """
        # 确定下载路径
        if not download_path:
            # 查找最近的下载文件
            downloads = list(self.downloader.download_dir.glob("*.zip"))
            if not downloads:
                return UpdateResult(
                    status=UpdateStatus.UPDATE_FAILED,
                    current_version=self.current_version,
                    message="未找到下载的更新包",
                    error="请先下载更新",
                )
            download_path = max(downloads, key=lambda p: p.stat().st_mtime)
        
        # 确定目标目录
        if not target_dir:
            # 自动检测安装目录
            target_dir = self._detect_install_dir()
        
        if not target_dir:
            return UpdateResult(
                status=UpdateStatus.UPDATE_FAILED,
                current_version=self.current_version,
                message="无法确定安装目录",
                error="请手动指定目标目录",
            )
        
        # 安装更新
        logger.info(f"正在安装更新到: {target_dir}")
        
        success = self.installer.install(
            download_path,
            target_dir,
            create_backup=self.auto_backup,
        )
        
        if success:
            return UpdateResult(
                status=UpdateStatus.UPDATE_SUCCESS,
                current_version=self.current_version,
                latest_version=self._latest_release.version if self._latest_release else None,
                message="更新安装成功，请重启 FoxCode",
                installed=True,
            )
        else:
            return UpdateResult(
                status=UpdateStatus.UPDATE_FAILED,
                current_version=self.current_version,
                message="安装更新失败",
                error="解压或安装过程中出错",
            )
    
    def _detect_install_dir(self) -> Path | None:
        """
        检测 FoxCode 安装目录
        
        Returns:
            安装目录路径
        """
        # 尝试从当前模块位置检测
        try:
            import foxcode
            module_path = Path(foxcode.__file__)
            # 向上查找 src 目录
            current = module_path.parent
            while current != current.parent:
                if current.name == "src":
                    return current.parent
                if (current / "src" / "foxcode").exists():
                    return current
                current = current.parent
        except Exception:
            pass
        
        # 尝试从 sys.path 检测
        for path_str in sys.path:
            path = Path(path_str)
            if (path / "foxcode").is_dir():
                return path
        
        return None
    
    def update(
        self,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> UpdateResult:
        """
        执行完整更新流程
        
        Args:
            progress_callback: 进度回调函数 (stage, progress)
            
        Returns:
            UpdateResult 对象
        """
        # 1. 检查更新
        if progress_callback:
            progress_callback("检查更新...", 0.0)
        
        check_result = self.check_for_updates()
        
        if check_result.status == UpdateStatus.UP_TO_DATE:
            return check_result
        
        if check_result.status != UpdateStatus.UPDATE_AVAILABLE:
            return check_result
        
        # 2. 下载更新
        if progress_callback:
            progress_callback("下载更新...", 0.3)
        
        def download_progress(downloaded: int, total: int):
            if progress_callback and total > 0:
                progress = 0.3 + (downloaded / total) * 0.5
                progress_callback("下载更新...", progress)
        
        download_result = self.download_update(download_progress)
        
        if download_result.status != UpdateStatus.UPDATE_DOWNLOADING:
            return download_result
        
        # 3. 安装更新
        if progress_callback:
            progress_callback("安装更新...", 0.9)
        
        install_result = self.install_update(download_result.download_path)
        
        if progress_callback:
            progress_callback("完成", 1.0)
        
        return install_result
    
    def update_from_source(
        self,
        progress_callback: Callable[[str, float], None] | None = None,
        branch: str = "main",
    ) -> UpdateResult:
        """
        从源码执行更新
        
        下载源码并在本地安装
        
        Args:
            progress_callback: 进度回调函数 (stage, progress)
            branch: 要下载的分支或标签名，默认为 main
            
        Returns:
            UpdateResult 对象
        """
        # 1. 检查更新
        if progress_callback:
            progress_callback("检查更新...", 0.0)
        
        check_result = self.check_for_updates()
        
        if check_result.status == UpdateStatus.UP_TO_DATE:
            return check_result
        
        if check_result.status != UpdateStatus.UPDATE_AVAILABLE:
            return check_result
        
        # 获取版本标签
        if self._latest_release:
            tag = self._latest_release.tag_name
        else:
            tag = branch
        
        # 2. 下载源码
        if progress_callback:
            progress_callback("下载源码...", 0.2)
        
        def download_progress(downloaded: int, total: int):
            if progress_callback and total > 0:
                progress = 0.2 + (downloaded / total) * 0.4
                progress_callback("下载源码...", progress)
        
        archive_path = self.source_installer.download_source(
            tag=tag,
            progress_callback=download_progress,
        )
        
        if not archive_path:
            return UpdateResult(
                status=UpdateStatus.NETWORK_ERROR,
                current_version=self.current_version,
                latest_version=self._latest_release.version if self._latest_release else None,
                message="下载源码失败",
                error="网络错误或下载中断",
            )
        
        # 3. 解压源码
        if progress_callback:
            progress_callback("解压源码...", 0.65)
        
        source_dir = self.source_installer.extract_source(archive_path)
        
        if not source_dir:
            return UpdateResult(
                status=UpdateStatus.UPDATE_FAILED,
                current_version=self.current_version,
                latest_version=self._latest_release.version if self._latest_release else None,
                message="解压源码失败",
                error="无法解压下载的源码包",
            )
        
        # 4. 安装源码
        if progress_callback:
            progress_callback("安装源码...", 0.75)
        
        success, output = self.source_installer.install_from_source(
            source_dir,
            upgrade=True,
            editable=False,
        )
        
        if not success:
            return UpdateResult(
                status=UpdateStatus.UPDATE_FAILED,
                current_version=self.current_version,
                latest_version=self._latest_release.version if self._latest_release else None,
                message="安装源码失败",
                error=output,
            )
        
        # 5. 清理临时文件
        if progress_callback:
            progress_callback("清理临时文件...", 0.95)
        
        self.source_installer.cleanup()
        
        if progress_callback:
            progress_callback("完成", 1.0)
        
        return UpdateResult(
            status=UpdateStatus.UPDATE_SUCCESS,
            current_version=self.current_version,
            latest_version=self._latest_release.version if self._latest_release else None,
            release_info=self._latest_release,
            message="源码安装成功，请重启 FoxCode",
            installed=True,
        )
    
    def get_update_info(self) -> dict[str, Any]:
        """
        获取更新信息摘要
        
        Returns:
            更新信息字典
        """
        info = {
            "current_version": self.current_version,
            "latest_version": None,
            "update_available": False,
            "release_notes": None,
            "download_size": None,
            "download_url": None,
        }
        
        if self._latest_release:
            release = self._latest_release
            info["latest_version"] = release.version
            info["update_available"] = VersionComparator.is_newer(
                release.version, self.current_version
            )
            info["release_notes"] = release.body[:500] if release.body else None
            info["download_size"] = release.get_file_size(self._get_platform_name())
            info["download_url"] = release.get_download_url(self._get_platform_name())
        
        return info


def check_for_updates() -> UpdateResult:
    """
    便捷函数：检查更新
    
    Returns:
        UpdateResult 对象
    """
    updater = FoxCodeUpdater()
    return updater.check_for_updates()


def get_latest_version() -> str | None:
    """
    便捷函数：获取最新版本号
    
    Returns:
        最新版本号，失败返回 None
    """
    updater = FoxCodeUpdater()
    result = updater.check_for_updates()
    return result.latest_version


def is_update_available() -> bool:
    """
    便捷函数：检查是否有可用更新
    
    Returns:
        是否有可用更新
    """
    updater = FoxCodeUpdater()
    result = updater.check_for_updates()
    return result.status == UpdateStatus.UPDATE_AVAILABLE
