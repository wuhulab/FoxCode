"""
FoxCode 注释保护器 - 使用 diff 算法保护项目原有注释

这个模块实现了"注释保护"功能：当 AI 编辑文件后，自动恢复文件中
原有的注释，避免 AI 意外删除或修改项目作者留下的注释。

核心思想：
1. 在文件被修改前，提取出所有注释及其在代码中的"锚点"位置
2. AI 写入新内容后，扫描新内容，定位每个原始注释的锚点
3. 把原始注释重新插入到新内容中

为什么需要保护注释：
- 项目原作者的注释通常包含业务逻辑说明、注意事项、TODO 等
- AI 在重构或重写代码时容易丢失这些注释
- 保留注释能提高代码的可维护性

支持的语言：
- 通过 CommentParser 自动识别，支持 30+ 种语言的注释语法

设计目标：
- 即使 AI 大量重写代码，注释也能尽量保留在合理位置
- 对未受影响的代码行不引入任何修改
- 处理行注释、块注释、文档字符串、HTML 注释
"""

from __future__ import annotations

import difflib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from foxcode.core.comment_parser import CommentParser, CommentRegion, CommentType

logger = logging.getLogger(__name__)


@dataclass
class AnchorInfo:
    """注释锚点信息 - 用于在新内容中重新定位"""

    line: int  # 原始文件中的行号（0-indexed）
    text: str  # 锚点代码（不含注释）
    normalized: str = ""  # 规范化后的锚点（用于模糊匹配）

    def __post_init__(self):
        self.normalized = self._normalize(self.text)

    @staticmethod
    def _normalize(text: str) -> str:
        """规范化代码：去除多余空白，便于模糊匹配"""
        return re.sub(r"\s+", " ", text.strip())


@dataclass
class ProtectedComment:
    """一个被保护的注释（带上下文信息）"""

    region: CommentRegion
    anchor: AnchorInfo | None

    @property
    def text(self) -> str:
        return self.region.text

    @property
    def body(self) -> str:
        return self.region.body

    @property
    def comment_type(self) -> CommentType:
        return self.region.comment_type

    @property
    def standalone(self) -> bool:
        return self.region.standalone


@dataclass
class ProtectionResult:
    """注释保护结果"""

    protected_content: str  # 保护后的最终内容
    restored_count: int = 0  # 恢复的注释数量
    lost_count: int = 0  # 丢失的注释数量（找不到合适位置）
    kept_count: int = 0  # 保留的注释数量（未受影响）
    new_comments_count: int = 0  # AI 新增的注释数量
    lost_comments: list[ProtectedComment] = field(default_factory=list)
    anchors_used: dict[str, int] = field(default_factory=dict)  # 锚点 -> 使用次数

    @property
    def total_protected(self) -> int:
        return self.restored_count + self.kept_count

    @property
    def total_comments(self) -> int:
        """原始注释总数（恢复 + 保留 + 丢失）"""
        return self.restored_count + self.kept_count + self.lost_count

    def summary(self) -> str:
        return (
            f"恢复 {self.restored_count} 个原始注释, "
            f"保留 {self.kept_count} 个, "
            f"丢失 {self.lost_count} 个, "
            f"新增 {self.new_comments_count} 个"
        )


class CommentProtector:
    """
    注释保护器

    用法：
        protector = CommentProtector()
        # 提取原始内容中的注释
        protected = protector.extract_protected_comments(original_content, file_path)
        # AI 修改文件后，恢复注释
        new_content = "..."  # AI 写入的内容
        result = protector.restore_comments(
            original_content, new_content, file_path, protected
        )
        # result.protected_content 是最终内容
    """

    # 模糊匹配的相似度阈值（0-1）
    FUZZY_THRESHOLD: ClassVar[float] = 0.6

    # 锚点查找的最大搜索范围（行）
    SEARCH_RADIUS: ClassVar[int] = 20

    def __init__(self, fuzzy_threshold: float = 0.6, search_radius: int = 20):
        """
        初始化注释保护器

        Args:
            fuzzy_threshold: 锚点相似度阈值，低于此值认为不匹配
            search_radius: 锚点附近搜索的最大行数
        """
        self.fuzzy_threshold = fuzzy_threshold
        self.search_radius = search_radius

    def extract_protected_comments(
        self,
        original_content: str | None,
        file_path: str | Path,
    ) -> list[ProtectedComment]:
        """
        从原始内容中提取所有受保护的注释

        Args:
            original_content: 文件原始内容（可为 None）
            file_path: 文件路径（用于识别注释语法）

        Returns:
            ProtectedComment 列表
        """
        if not original_content:
            return []
        parser = CommentParser(file_path)
        if not parser.is_supported(file_path):
            return []

        regions = parser.parse(original_content)
        protected = []
        for region in regions:
            anchor = None
            if region.anchor_line is not None:
                anchor = AnchorInfo(line=region.anchor_line, text=region.anchor_text)
            protected.append(ProtectedComment(region=region, anchor=anchor))
        return protected

    def restore_comments(
        self,
        original_content: str,
        new_content: str,
        file_path: str | Path,
        protected: list[ProtectedComment] | None = None,
    ) -> ProtectionResult:
        """
        恢复原始注释到新内容

        Args:
            original_content: 文件原始内容
            new_content: AI 写入的新内容
            file_path: 文件路径
            protected: 已提取的受保护注释（如不提供则从 original_content 重新提取）

        Returns:
            ProtectionResult 包含最终内容和统计信息
        """
        result = ProtectionResult(protected_content=new_content)

        if protected is None:
            protected = self.extract_protected_comments(original_content, file_path)

        if not protected:
            return result

        # 规范化行尾为 \n：避免 Windows 的 \r\n 干扰行号计算
        original_newline = "\n"
        if "\r\n" in new_content:
            original_newline = "\r\n"
            new_content = new_content.replace("\r\n", "\n")
        new_lines = new_content.splitlines(keepends=True)

        # 解析新内容，识别 AI 新增的注释
        new_parser = CommentParser(file_path)
        new_regions = new_parser.parse(new_content)
        result.new_comments_count = len(new_regions)

        # 检查哪些原始注释已经存在于新内容中
        existing_bodies = {self._normalize_body(r.body): r for r in new_regions}

        # 先剥离新内容中的所有注释，得到纯代码
        new_lines = new_content.splitlines(keepends=True)
        new_code_lines = self._strip_lines(new_lines, new_regions)

        # 对每个受保护的注释，决定如何处理
        comments_to_insert: list[tuple[int, int, ProtectedComment]] = []  # (行号, 原始顺序, 注释)
        for seq, pc in enumerate(protected):
            body_norm = self._normalize_body(pc.body)
            # 如果新内容中已经有这个注释，跳过
            if body_norm in existing_bodies:
                result.kept_count += 1
                continue
            # 尝试定位锚点
            target_line = self._locate_anchor(pc, new_code_lines, new_content, file_path)
            if target_line is not None:
                comments_to_insert.append((target_line, seq, pc))
                anchor_key = pc.anchor.normalized if pc.anchor else ""
                result.anchors_used[anchor_key] = result.anchors_used.get(anchor_key, 0) + 1
            else:
                result.lost_count += 1
                result.lost_comments.append(pc)

        # 排序：行号大的先插入（避免行号错乱）
        # 同行号下，原顺序大的先插入（这样原顺序小的会出现在文件上方）
        comments_to_insert.sort(key=lambda x: (x[0], x[1]), reverse=True)
        final_lines = list(new_lines)
        for target_line, _seq, pc in comments_to_insert:
            inserted = self._insert_comment(final_lines, target_line, pc, new_content)
            if inserted:
                result.restored_count += 1
            else:
                result.lost_count += 1
                result.lost_comments.append(pc)

        result.protected_content = "".join(final_lines)
        # 恢复原始行尾
        if original_newline != "\n":
            result.protected_content = result.protected_content.replace("\n", original_newline)
        logger.info(f"注释保护: {result.summary()}")
        return result

    def _strip_lines(self, lines: list[str], regions: list[CommentRegion]) -> list[str]:
        """从行列表中剥离所有注释区域，返回纯代码行

        - 整行注释：替换为空白行（保留缩进）
        - 行内注释：只移除注释部分，保留前面的代码
        """
        new_lines = []
        for i, line in enumerate(lines):
            covered = [r for r in regions if r.contains_line(i)]
            if not covered:
                new_lines.append(line)
                continue
            # 行内注释：保留代码部分
            inline = [r for r in covered if not r.standalone]
            if inline and not all(r.standalone for r in covered):
                first_col = min(r.start_col for r in inline)
                code_part = line[:first_col].rstrip()
                if line.endswith("\n"):
                    code_part += "\n"
                if code_part.strip():
                    new_lines.append(code_part)
                else:
                    indent = len(line) - len(line.lstrip())
                    leading = line[:indent]
                    new_lines.append(leading + "\n" if leading else "\n")
            else:
                # 整行注释：替换为空白行
                indent = len(line) - len(line.lstrip())
                leading = line[:indent]
                if line.strip():
                    if leading:
                        new_lines.append(leading + "\n")
                    else:
                        new_lines.append("\n")
                else:
                    new_lines.append(line)
        return new_lines

    def _normalize_body(self, body: str) -> str:
        """规范化注释正文用于匹配"""
        return re.sub(r"\s+", " ", body.strip())

    def _locate_anchor(
        self,
        pc: ProtectedComment,
        new_code_lines: list[str],
        _new_content: str,
        _file_path: str | Path,
    ) -> int | None:
        """
        在新代码中定位注释应该插入的位置

        Returns:
            插入位置的行号（注释将插入到该行**之前**），None 表示找不到
        """
        if pc.anchor is None or not pc.anchor.normalized:
            return None

        # 1. 尝试精确匹配
        for i, line in enumerate(new_code_lines):
            if AnchorInfo._normalize(line) == pc.anchor.normalized:
                return self._choose_insert_position(i, pc, new_code_lines)

        # 2. 尝试模糊匹配
        best_score = 0.0
        best_idx = -1
        anchor_norm = pc.anchor.normalized
        for i, line in enumerate(new_code_lines):
            norm = AnchorInfo._normalize(line)
            if not norm:
                continue
            score = difflib.SequenceMatcher(None, anchor_norm, norm).ratio()
            if score > best_score and score >= self.fuzzy_threshold:
                best_score = score
                best_idx = i

        if best_idx >= 0:
            return self._choose_insert_position(best_idx, pc, new_code_lines)

        return None

    def _choose_insert_position(
        self,
        anchor_idx: int,
        pc: ProtectedComment,
        _new_code_lines: list[str],
    ) -> int:
        """
        在锚点行附近选择最佳插入位置

        - 独立成行的注释：插入到锚点行**之前**（前一行）
        - 行内注释（行尾）：附加到锚点行**末尾**
        """
        if pc.standalone:
            # 独立行：插入到锚点行的前一行
            return max(0, anchor_idx)
        # 行内注释：附加到锚点行末尾
        return anchor_idx

    def _insert_comment(
        self,
        lines: list[str],
        target_line: int,
        pc: ProtectedComment,
        _new_content: str,
    ) -> bool:
        """
        将注释插入到指定行

        Args:
            lines: 当前行列表（会被修改）
            target_line: 目标行（0-indexed）
            pc: 要插入的注释
            new_content: 完整的新内容（用于判断缩进）

        Returns:
            是否成功插入
        """
        if target_line < 0 or target_line > len(lines):
            return False

        # 获取锚点行的缩进（target_line 可能就是锚点行）
        anchor_idx = min(target_line, len(lines) - 1) if lines else 0
        if anchor_idx < len(lines):
            anchor_line = lines[anchor_idx]
            indent = self._get_indent(anchor_line)
        else:
            indent = ""

        if pc.standalone:
            # 独立行：插入独立的一行注释
            comment_line = self._format_standalone_comment(pc, indent)
            lines.insert(target_line, comment_line)
            return True

        # 行内注释：附加到行尾
        if target_line >= len(lines):
            return False
        target_line_content = lines[target_line]
        # 去掉所有尾部换行符（包括 \r\n）
        stripped = target_line_content.rstrip("\n\r")
        # 在行尾添加注释
        new_line = stripped + "  " + pc.text + "\n"
        lines[target_line] = new_line
        return True

        # 行内注释：附加到行尾
        if target_line >= len(lines):
            return False
        target_line_content = lines[target_line]
        stripped = target_line_content.rstrip("\n\r")
        # 保留 trailing newline
        if stripped.endswith("\r"):
            newline = "\r"
        else:
            newline = "\n" if target_line_content.endswith("\n") else ""
        # 在行尾添加注释
        new_line = stripped + "  " + pc.text + newline
        lines[target_line] = new_line
        return True

    def _get_indent(self, line: str) -> str:
        """获取行的缩进（前置空白）"""
        return line[: len(line) - len(line.lstrip())]

    def _format_standalone_comment(self, pc: ProtectedComment, indent: str) -> str:
        """格式化独立注释行（包括换行符）"""
        if not pc.text.endswith("\n"):
            return indent + pc.text + "\n"
        return indent + pc.text

    def is_supported(self, file_path: str | Path) -> bool:
        """判断文件是否支持注释保护"""
        return CommentParser.is_supported(file_path)


# 全局单例
default_protector = CommentProtector()
