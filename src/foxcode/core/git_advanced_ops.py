"""
FoxCode Git 高级操作模块

提供智能提交、冲突解决和分支管理功能。

主要功能：
- 智能提交信息生成
- 合并冲突分析和解决建议
- 分支可视化管理
- 分支策略建议
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CommitType(str, Enum):
    """提交类型"""
    FEAT = "feat"       # 新功能
    FIX = "fix"         # 修复 bug
    DOCS = "docs"       # 文档变更
    STYLE = "style"     # 代码格式
    REFACTOR = "refactor"  # 重构
    TEST = "test"       # 测试
    CHORE = "chore"     # 构建/工具
    PERF = "perf"       # 性能优化
    CI = "ci"           # CI 配置
    BUILD = "build"     # 构建系统


class BranchType(str, Enum):
    """分支类型"""
    MAIN = "main"
    DEVELOP = "develop"
    FEATURE = "feature"
    RELEASE = "release"
    HOTFIX = "hotfix"
    BUGFIX = "bugfix"


@dataclass
class FileChange:
    """
    文件变更
    
    Attributes:
        path: 文件路径
        status: 状态 (A/M/D/R)
        additions: 新增行数
        deletions: 删除行数
    """
    path: str
    status: str = "M"
    additions: int = 0
    deletions: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "status": self.status,
            "additions": self.additions,
            "deletions": self.deletions,
        }


@dataclass
class CommitInfo:
    """
    提交信息
    
    Attributes:
        type: 提交类型
        scope: 影响范围
        subject: 主题
        body: 正文
        footer: 页脚
        breaking: 是否破坏性变更
    """
    type: CommitType = CommitType.FEAT
    scope: str = ""
    subject: str = ""
    body: str = ""
    footer: str = ""
    breaking: bool = False
    
    def to_message(self) -> str:
        """生成提交消息"""
        # 类型和范围
        header = f"{self.type.value}"
        if self.scope:
            header += f"({self.scope})"
        header += ": "
        
        # 破坏性变更标记
        if self.breaking:
            header += "BREAKING CHANGE: "
        
        header += self.subject
        
        lines = [header]
        
        if self.body:
            lines.append("")
            lines.append(self.body)
        
        if self.footer:
            lines.append("")
            lines.append(self.footer)
        
        return "\n".join(lines)


@dataclass
class ConflictInfo:
    """
    冲突信息
    
    Attributes:
        file_path: 文件路径
        ours: 我们的变更
        theirs: 他们的变更
        conflict_markers: 冲突标记位置
        suggestion: 解决建议
    """
    file_path: str
    ours: str = ""
    theirs: str = ""
    conflict_markers: list[tuple[int, int]] = field(default_factory=list)
    suggestion: str = ""


@dataclass
class BranchInfo:
    """
    分支信息
    
    Attributes:
        name: 分支名
        type: 分支类型
        is_current: 是否当前分支
        is_remote: 是否远程分支
        last_commit: 最后提交
        ahead: 领先提交数
        behind: 落后提交数
    """
    name: str
    type: BranchType = BranchType.FEATURE
    is_current: bool = False
    is_remote: bool = False
    last_commit: str = ""
    ahead: int = 0
    behind: int = 0


@dataclass
class GitStatus:
    """
    Git 状态
    
    Attributes:
        branch: 当前分支
        is_clean: 是否干净
        staged: 已暂存文件
        unstaged: 未暂存文件
        untracked: 未跟踪文件
        ahead: 领先提交数
        behind: 落后提交数
    """
    branch: str = ""
    is_clean: bool = True
    staged: list[FileChange] = field(default_factory=list)
    unstaged: list[FileChange] = field(default_factory=list)
    untracked: list[str] = field(default_factory=list)
    ahead: int = 0
    behind: int = 0


class GitConfig(BaseModel):
    """
    Git 配置
    
    Attributes:
        commit_template: 提交模板
        auto_stage: 是否自动暂存
        conventional_commits: 是否使用约定式提交
        branch_prefixes: 分支前缀
    """
    commit_template: str = ""
    auto_stage: bool = False
    conventional_commits: bool = True
    branch_prefixes: dict[str, str] = Field(
        default_factory=lambda: {
            "feature": "feature/",
            "bugfix": "bugfix/",
            "hotfix": "hotfix/",
            "release": "release/",
        }
    )


class GitAdvancedOps:
    """
    Git 高级操作
    
    提供智能提交、冲突解决和分支管理功能。
    
    Example:
        >>> git = GitAdvancedOps()
        >>> status = git.get_status()
        >>> message = git.generate_commit_message(status)
    """
    
    # 文件扩展名到提交类型的映射
    FILE_TYPE_MAP = {
        ".py": CommitType.FEAT,
        ".js": CommitType.FEAT,
        ".ts": CommitType.FEAT,
        ".md": CommitType.DOCS,
        ".rst": CommitType.DOCS,
        ".txt": CommitType.DOCS,
        ".json": CommitType.CHORE,
        ".yaml": CommitType.CHORE,
        ".yml": CommitType.CHORE,
        ".toml": CommitType.CHORE,
        ".cfg": CommitType.CHORE,
        ".ini": CommitType.CHORE,
        ".css": CommitType.STYLE,
        ".scss": CommitType.STYLE,
        ".less": CommitType.STYLE,
        ".html": CommitType.FEAT,
        ".sql": CommitType.FEAT,
        ".sh": CommitType.CHORE,
    }
    
    # 关键词到提交类型的映射
    KEYWORD_TYPE_MAP = {
        "fix": CommitType.FIX,
        "bug": CommitType.FIX,
        "修复": CommitType.FIX,
        "add": CommitType.FEAT,
        "新增": CommitType.FEAT,
        "实现": CommitType.FEAT,
        "update": CommitType.FEAT,
        "更新": CommitType.FEAT,
        "remove": CommitType.REFACTOR,
        "删除": CommitType.REFACTOR,
        "refactor": CommitType.REFACTOR,
        "重构": CommitType.REFACTOR,
        "test": CommitType.TEST,
        "测试": CommitType.TEST,
        "doc": CommitType.DOCS,
        "文档": CommitType.DOCS,
        "style": CommitType.STYLE,
        "格式": CommitType.STYLE,
        "perf": CommitType.PERF,
        "性能": CommitType.PERF,
        "ci": CommitType.CI,
        "build": CommitType.BUILD,
        "构建": CommitType.BUILD,
    }
    
    def __init__(self, config: GitConfig | None = None):
        """
        初始化 Git 操作
        
        Args:
            config: Git 配置
        """
        self.config = config or GitConfig()
        logger.info("Git 高级操作模块初始化完成")
    
    def _run_git_command(self, args: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
        """运行 Git 命令"""
        try:
            result = subprocess.run(
                ["git"] + args,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=30,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except FileNotFoundError:
            return -1, "", "Git not found"
    
    def get_status(self, repo_path: Path | None = None) -> GitStatus:
        """
        获取 Git 状态
        
        Args:
            repo_path: 仓库路径
            
        Returns:
            Git 状态
        """
        status = GitStatus()
        
        # 获取当前分支
        _, branch, _ = self._run_git_command(["branch", "--show-current"], repo_path)
        status.branch = branch.strip()
        
        # 获取状态
        returncode, output, _ = self._run_git_command(
            ["status", "--porcelain=v1"],
            repo_path
        )
        
        if returncode == 0:
            for line in output.strip().split("\n"):
                if not line:
                    continue
                
                file_status = line[:2]
                file_path = line[3:]
                
                if file_status.startswith("??"):
                    status.untracked.append(file_path)
                elif file_status.strip():
                    change = FileChange(
                        path=file_path,
                        status=file_status.strip()[0],
                    )
                    if file_status[0] in "MADRC":
                        status.staged.append(change)
                    else:
                        status.unstaged.append(change)
        
        status.is_clean = (
            not status.staged and 
            not status.unstaged and 
            not status.untracked
        )
        
        # 获取 ahead/behind
        _, ahead_behind, _ = self._run_git_command(
            ["rev-list", "--left-right", "--count", "@{upstream}...HEAD"],
            repo_path
        )
        
        if ahead_behind.strip():
            parts = ahead_behind.strip().split()
            if len(parts) == 2:
                status.behind = int(parts[0])
                status.ahead = int(parts[1])
        
        return status
    
    def generate_commit_message(
        self,
        status: GitStatus,
        diff: str = "",
    ) -> str:
        """
        生成智能提交信息
        
        Args:
            status: Git 状态
            diff: 差异内容
            
        Returns:
            提交信息
        """
        commit_info = CommitInfo()
        
        # 分析变更文件
        all_changes = status.staged + status.unstaged
        
        if not all_changes:
            return "chore: no changes"
        
        # 确定提交类型
        commit_type = self._determine_commit_type(all_changes, diff)
        commit_info.type = commit_type
        
        # 确定范围
        scope = self._determine_scope(all_changes)
        commit_info.scope = scope
        
        # 生成主题
        subject = self._generate_subject(all_changes, commit_type)
        commit_info.subject = subject
        
        # 检查破坏性变更
        if self._has_breaking_changes(diff):
            commit_info.breaking = True
        
        return commit_info.to_message()
    
    def _determine_commit_type(
        self,
        changes: list[FileChange],
        diff: str,
    ) -> CommitType:
        """确定提交类型"""
        # 基于文件扩展名
        type_counts: dict[CommitType, int] = {}
        
        for change in changes:
            ext = Path(change.path).suffix.lower()
            file_type = self.FILE_TYPE_MAP.get(ext, CommitType.FEAT)
            type_counts[file_type] = type_counts.get(file_type, 0) + 1
        
        # 基于差异内容关键词
        diff_lower = diff.lower()
        for keyword, commit_type in self.KEYWORD_TYPE_MAP.items():
            if keyword in diff_lower:
                type_counts[commit_type] = type_counts.get(commit_type, 0) + 5
        
        # 返回最多的类型
        if type_counts:
            return max(type_counts.items(), key=lambda x: x[1])[0]
        
        return CommitType.FEAT
    
    def _determine_scope(self, changes: list[FileChange]) -> str:
        """确定提交范围"""
        if not changes:
            return ""
        
        # 获取公共目录
        dirs = [Path(c.path).parent for c in changes]
        
        if len(dirs) == 1:
            return str(dirs[0]).replace("/", "-").replace("\\", "-")
        
        # 找公共前缀
        common = ""
        first_parts = str(dirs[0]).split("/")
        
        for i, part in enumerate(first_parts):
            if all(str(d).split("/")[i] == part if i < len(str(d).split("/")) else False for d in dirs):
                common = part
            else:
                break
        
        return common
    
    def _generate_subject(
        self,
        changes: list[FileChange],
        commit_type: CommitType,
    ) -> str:
        """生成提交主题"""
        if not changes:
            return "update"
        
        # 基于变更类型生成描述
        if len(changes) == 1:
            file_path = changes[0].path
            file_name = Path(file_path).stem
            
            status_desc = {
                "A": "add",
                "M": "update",
                "D": "remove",
                "R": "rename",
            }
            
            action = status_desc.get(changes[0].status, "update")
            return f"{action} {file_name}"
        
        # 多文件变更
        additions = sum(c.additions for c in changes if c.status == "A")
        modifications = sum(1 for c in changes if c.status == "M")
        deletions = sum(1 for c in changes if c.status == "D")
        
        parts = []
        if additions:
            parts.append(f"add {additions} files")
        if modifications:
            parts.append(f"update {modifications} files")
        if deletions:
            parts.append(f"remove {deletions} files")
        
        return ", ".join(parts) if parts else "update files"
    
    def _has_breaking_changes(self, diff: str) -> bool:
        """检查是否有破坏性变更"""
        breaking_patterns = [
            r"BREAKING CHANGE",
            r"breaking change",
            r"破坏性变更",
            r"不兼容",
        ]
        
        for pattern in breaking_patterns:
            if re.search(pattern, diff, re.IGNORECASE):
                return True
        
        return False
    
    def analyze_conflicts(self, repo_path: Path | None = None) -> list[ConflictInfo]:
        """
        分析合并冲突
        
        Args:
            repo_path: 仓库路径
            
        Returns:
            冲突信息列表
        """
        conflicts = []
        
        # 获取冲突文件
        _, output, _ = self._run_git_command(
            ["diff", "--name-only", "--diff-filter=U"],
            repo_path
        )
        
        conflict_files = output.strip().split("\n")
        
        for file_path in conflict_files:
            if not file_path:
                continue
            
            conflict = ConflictInfo(file_path=file_path)
            
            # 读取冲突内容
            full_path = (repo_path or Path.cwd()) / file_path
            if full_path.exists():
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    # 解析冲突标记
                    conflict.conflict_markers = self._find_conflict_markers(content)
                    
                    # 提取 ours 和 theirs
                    conflict.ours, conflict.theirs = self._extract_conflict_parts(content)
                    
                    # 生成建议
                    conflict.suggestion = self._suggest_resolution(conflict)
                    
                except Exception as e:
                    logger.debug(f"读取冲突文件失败: {e}")
            
            conflicts.append(conflict)
        
        return conflicts
    
    def _find_conflict_markers(self, content: str) -> list[tuple[int, int]]:
        """查找冲突标记位置"""
        markers = []
        lines = content.split("\n")
        
        start = None
        for i, line in enumerate(lines):
            if line.startswith("<<<<<<<"):
                start = i
            elif line.startswith(">>>>>>>") and start is not None:
                markers.append((start, i))
                start = None
        
        return markers
    
    def _extract_conflict_parts(self, content: str) -> tuple[str, str]:
        """提取冲突部分"""
        ours = []
        theirs = []
        
        lines = content.split("\n")
        current = None
        
        for line in lines:
            if line.startswith("<<<<<<<"):
                current = "ours"
            elif line.startswith("======="):
                current = "theirs"
            elif line.startswith(">>>>>>>"):
                current = None
            elif current == "ours":
                ours.append(line)
            elif current == "theirs":
                theirs.append(line)
        
        return "\n".join(ours), "\n".join(theirs)
    
    def _suggest_resolution(self, conflict: ConflictInfo) -> str:
        """生成冲突解决建议"""
        # 简单的建议逻辑
        if not conflict.ours and conflict.theirs:
            return "建议接受他们的变更（我们的变更为空）"
        elif conflict.ours and not conflict.theirs:
            return "建议保留我们的变更（他们的变更为空）"
        elif conflict.ours == conflict.theirs:
            return "两边的变更相同，可以直接接受任一方"
        else:
            return "需要手动合并两边的变更"
    
    def get_branches(self, repo_path: Path | None = None) -> list[BranchInfo]:
        """
        获取分支列表
        
        Args:
            repo_path: 仓库路径
            
        Returns:
            分支信息列表
        """
        branches = []
        
        # 获取本地分支
        _, output, _ = self._run_git_command(
            ["branch", "-vv"],
            repo_path
        )
        
        current_branch = ""
        for line in output.strip().split("\n"):
            if not line:
                continue
            
            is_current = line.startswith("*")
            if is_current:
                current_branch = line[2:].split()[0]
            
            parts = line.lstrip("* ").split()
            if not parts:
                continue
            
            name = parts[0]
            
            # 确定分支类型
            branch_type = self._determine_branch_type(name)
            
            branches.append(BranchInfo(
                name=name,
                type=branch_type,
                is_current=is_current,
                is_remote=False,
            ))
        
        # 获取远程分支
        _, output, _ = self._run_git_command(
            ["branch", "-r"],
            repo_path
        )
        
        for line in output.strip().split("\n"):
            if not line:
                continue
            
            name = line.strip()
            branch_type = self._determine_branch_type(name)
            
            branches.append(BranchInfo(
                name=name,
                type=branch_type,
                is_current=name.endswith(current_branch),
                is_remote=True,
            ))
        
        return branches
    
    def _determine_branch_type(self, name: str) -> BranchType:
        """确定分支类型"""
        name_lower = name.lower()
        
        if name_lower in ("main", "master"):
            return BranchType.MAIN
        elif name_lower == "develop":
            return BranchType.DEVELOP
        elif "feature" in name_lower:
            return BranchType.FEATURE
        elif "release" in name_lower:
            return BranchType.RELEASE
        elif "hotfix" in name_lower:
            return BranchType.HOTFIX
        elif "bugfix" in name_lower:
            return BranchType.BUGFIX
        else:
            return BranchType.FEATURE
    
    def suggest_branch_strategy(self, branches: list[BranchInfo]) -> str:
        """
        建议分支策略
        
        Args:
            branches: 分支列表
            
        Returns:
            策略建议
        """
        has_main = any(b.type == BranchType.MAIN for b in branches)
        has_develop = any(b.type == BranchType.DEVELOP for b in branches)
        has_feature = any(b.type == BranchType.FEATURE for b in branches)
        
        suggestions = []
        
        if not has_main:
            suggestions.append("建议创建 main 分支作为主分支")
        
        if not has_develop:
            suggestions.append("建议创建 develop 分支作为开发分支")
        
        if has_feature:
            feature_count = sum(1 for b in branches if b.type == BranchType.FEATURE)
            if feature_count > 5:
                suggestions.append("功能分支较多，建议及时合并或清理已完成的分支")
        
        if not suggestions:
            suggestions.append("分支结构良好，建议继续使用 Git Flow 或类似工作流")
        
        return "\n".join(suggestions)
    
    def create_branch(
        self,
        name: str,
        base: str = "HEAD",
        repo_path: Path | None = None,
    ) -> bool:
        """
        创建分支
        
        Args:
            name: 分支名
            base: 基础分支
            repo_path: 仓库路径
            
        Returns:
            是否成功
        """
        returncode, _, _ = self._run_git_command(
            ["checkout", "-b", name, base],
            repo_path
        )
        return returncode == 0
    
    def commit(
        self,
        message: str,
        amend: bool = False,
        repo_path: Path | None = None,
    ) -> bool:
        """
        提交变更
        
        Args:
            message: 提交信息
            amend: 是否修改上次提交
            repo_path: 仓库路径
            
        Returns:
            是否成功
        """
        args = ["commit", "-m", message]
        if amend:
            args.append("--amend")
        
        returncode, _, _ = self._run_git_command(args, repo_path)
        return returncode == 0


# 创建默认 Git 操作实例
git_advanced_ops = GitAdvancedOps()
