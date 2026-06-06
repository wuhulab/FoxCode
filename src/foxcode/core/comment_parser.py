"""
FoxCode 注释解析器 - 跨语言注释提取

这个模块负责识别和提取源代码中的注释，支持多种编程语言：

- 行注释：`#` (Python/Shell/YAML/TOML/Ruby) 或 `//` (C系) 或 `--` (SQL/Lua/Haskell)
- 块注释：`/* ... */` (C系/CSS/SQL)
- 文档字符串：三引号（Python）
- HTML/XML 注释：`<!-- ... -->`

核心能力：
1. 识别一个文件可以使用哪些注释语法（基于扩展名）
2. 在解析注释的同时保留原始内容用于位置映射
3. 处理字符串字面量以避免误判（"hello // world" 中的 // 不是注释）
4. 计算每个注释的代码锚点 - 紧邻的非注释代码行（用于保护时定位）

主要类：
- CommentType: 注释类型枚举
- CommentRegion: 表示一个注释区域（含起止位置、内容、类型、锚点）
- CommentParser: 通用注释解析器
- get_parser_for_file: 根据文件扩展名返回合适的解析器
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import ClassVar


class CommentType(str, Enum):
    """注释类型"""

    LINE = "line"  # 行注释
    BLOCK = "block"  # 块注释
    DOCSTRING = "docstring"  # 文档字符串（Python 特有）
    HTML = "html"  # HTML/XML 注释


@dataclass
class CommentRegion:
    """注释区域 - 描述一个注释的精确位置和内容"""

    start_line: int  # 起始行（0-indexed）
    start_col: int  # 起始列（0-indexed）
    end_line: int  # 结束行（0-indexed）
    end_col: int  # 结束列（0-indexed，不含结束定界符后的换行）
    text: str  # 注释的完整文本（含定界符，可能跨多行）
    body: str  # 注释正文（不含定界符）
    comment_type: CommentType
    # 代码锚点：注释附近最相关的一行代码（用于在 AI 编辑后重新定位）
    anchor_line: int | None = None  # 锚点行号（0-indexed）
    anchor_text: str = ""  # 锚点代码内容（不含行尾换行）
    standalone: bool = False  # 注释是否独立成行

    def contains_line(self, line: int) -> bool:
        """判断某行是否在该注释区域内"""
        return self.start_line <= line <= self.end_line

    def get_indent(self) -> str:
        """获取注释首行的缩进"""
        first_line = self.text.split("\n", 1)[0]
        stripped = first_line.lstrip()
        return first_line[: len(first_line) - len(stripped)]


class CommentParser:
    """
    通用注释解析器

    通过字符级状态机扫描源码，识别注释区域。设计原则：
    - 零依赖（不依赖 tree-sitter 等 AST 库）
    - 正确处理字符串字面量（不会把字符串内的 // 当成注释）
    - 支持多种语言的注释语法
    """

    EXTENSION_MAP: ClassVar[dict[str, dict]] = {
        # Python 系列
        ".py": {"line": ["#"], "block": [('"""', '"""'), ("'''", "'''")], "docstring": True},
        ".pyi": {"line": ["#"], "block": [('"""', '"""'), ("'''", "'''")], "docstring": True},
        # C 系
        ".js": {"line": ["//"], "block": [("/*", "*/")]},
        ".mjs": {"line": ["//"], "block": [("/*", "*/")]},
        ".cjs": {"line": ["//"], "block": [("/*", "*/")]},
        ".jsx": {"line": ["//"], "block": [("/*", "*/")]},
        ".ts": {"line": ["//"], "block": [("/*", "*/")]},
        ".tsx": {"line": ["//"], "block": [("/*", "*/")]},
        ".java": {"line": ["//"], "block": [("/*", "*/")]},
        ".go": {"line": ["//"], "block": [("/*", "*/")]},
        ".rs": {"line": ["//"], "block": [("/*", "*/")]},
        ".c": {"line": ["//"], "block": [("/*", "*/")]},
        ".h": {"line": ["//"], "block": [("/*", "*/")]},
        ".cpp": {"line": ["//"], "block": [("/*", "*/")]},
        ".cc": {"line": ["//"], "block": [("/*", "*/")]},
        ".cxx": {"line": ["//"], "block": [("/*", "*/")]},
        ".hpp": {"line": ["//"], "block": [("/*", "*/")]},
        ".hxx": {"line": ["//"], "block": [("/*", "*/")]},
        ".cs": {"line": ["//"], "block": [("/*", "*/")]},
        ".swift": {"line": ["//"], "block": [("/*", "*/")]},
        ".kt": {"line": ["//"], "block": [("/*", "*/")]},
        ".kts": {"line": ["//"], "block": [("/*", "*/")]},
        ".scala": {"line": ["//"], "block": [("/*", "*/")]},
        ".m": {"line": ["//"], "block": [("/*", "*/")]},
        ".dart": {"line": ["//"], "block": [("/*", "*/")]},
        # 脚本语言
        ".rb": {"line": ["#"], "block": [("=begin", "=end")]},
        ".php": {"line": ["//", "#"], "block": [("/*", "*/")]},
        ".lua": {"line": ["--"], "block": [("--[[", "]]")]},
        # 其它
        ".sql": {"line": ["--"], "block": [("/*", "*/")]},
        ".sh": {"line": ["#"]},
        ".bash": {"line": ["#"]},
        ".zsh": {"line": ["#"]},
        ".r": {"line": ["#"]},
        # 标记语言
        ".html": {"html": True},
        ".htm": {"html": True},
        ".xml": {"html": True},
        ".svg": {"html": True},
        ".md": {"html": True},
        ".mdx": {"html": True},
        # 样式
        ".css": {"block": [("/*", "*/")]},
        ".scss": {"line": ["//"], "block": [("/*", "*/")]},
        ".sass": {"line": ["//"], "block": [("/*", "*/")]},
        ".less": {"line": ["//"], "block": [("/*", "*/")]},
        # 配置
        ".yaml": {"line": ["#"]},
        ".yml": {"line": ["#"]},
        ".toml": {"line": ["#"]},
        ".ini": {"line": [";", "#"]},
        ".cfg": {"line": [";", "#"]},
        ".conf": {"line": ["#", ";"]},
        ".env": {"line": ["#"]},
    }

    def __init__(self, file_path: str | Path | None = None):
        """
        初始化解析器

        Args:
            file_path: 文件路径（用于自动识别语言），可为 None
        """
        self.file_path = Path(file_path) if file_path else None
        self._syntax = self._detect_syntax()

    def _detect_syntax(self) -> dict:
        """根据扩展名检测注释语法"""
        if not self.file_path:
            return {"line": ["//"], "block": [("/*", "*/")]}
        ext = self.file_path.suffix.lower()
        return self.EXTENSION_MAP.get(ext, {"line": ["//"], "block": [("/*", "*/")]})

    @classmethod
    def get_supported_extensions(cls) -> list[str]:
        """获取所有支持的扩展名"""
        return list(cls.EXTENSION_MAP.keys())

    @classmethod
    def is_supported(cls, file_path: str | Path) -> bool:
        """判断文件是否支持注释保护"""
        if not file_path:
            return False
        ext = Path(file_path).suffix.lower()
        return ext in cls.EXTENSION_MAP

    def parse(self, content: str) -> list[CommentRegion]:
        """
        解析内容中的所有注释

        Args:
            content: 源代码内容

        Returns:
            按位置排序的注释区域列表
        """
        comments: list[CommentRegion] = []
        n = len(content)

        i = 0
        line = 0
        col = 0

        while i < n:
            ch = content[i]

            # 处理换行
            if ch == "\n":
                line += 1
                col = 0
                i += 1
                continue

            # 在字符串内：跳过字符串内容
            if ch in ('"', "'", "`"):
                # 检查是否是独立成行的三引号文档字符串
                if self._syntax.get("docstring") and ch == '"' and content[i : i + 3] == '"""':
                    ds = self._try_match_docstring(content, i, line, col)
                    if ds is not None:
                        start_line, start_col, end_line, end_col, text, body = ds
                        comments.append(
                            CommentRegion(
                                start_line=start_line,
                                start_col=start_col,
                                end_line=end_line,
                                end_col=end_col,
                                text=text,
                                body=body,
                                comment_type=CommentType.DOCSTRING,
                            )
                        )
                        i, line, col = self._pos_at_to_index(content, end_line, end_col)
                        continue
                if self._syntax.get("docstring") and ch == "'" and content[i : i + 3] == "'''":
                    ds = self._try_match_docstring(content, i, line, col)
                    if ds is not None:
                        start_line, start_col, end_line, end_col, text, body = ds
                        comments.append(
                            CommentRegion(
                                start_line=start_line,
                                start_col=start_col,
                                end_line=end_line,
                                end_col=end_col,
                                text=text,
                                body=body,
                                comment_type=CommentType.DOCSTRING,
                            )
                        )
                        i, line, col = self._pos_at_to_index(content, end_line, end_col)
                        continue
                i, line, col = self._skip_string(content, i, line, col, ch)
                continue

            # HTML 注释
            if self._syntax.get("html") and content[i : i + 4] == "<!--":
                start_line, start_col = line, col
                end_pos = content.find("-->", i + 4)
                if end_pos == -1:
                    i += 1
                    col += 1
                    continue
                end_idx = end_pos + 3
                text = content[i:end_idx]
                body = content[i + 4 : end_pos]
                end_line, end_col = self._pos_at(content, end_idx)
                comments.append(
                    CommentRegion(
                        start_line=start_line,
                        start_col=start_col,
                        end_line=end_line,
                        end_col=end_col,
                        text=text,
                        body=body,
                        comment_type=CommentType.HTML,
                    )
                )
                i, line, col = end_idx, end_line, end_col
                continue

            # 块注释
            block = self._try_match_block(content, i, line, col)
            if block is not None:
                start_line, start_col, end_line, end_col, text, body, ctype = block
                comments.append(
                    CommentRegion(
                        start_line=start_line,
                        start_col=start_col,
                        end_line=end_line,
                        end_col=end_col,
                        text=text,
                        body=body,
                        comment_type=ctype,
                    )
                )
                i, line, col = self._pos_at_to_index(content, end_line, end_col)
                continue

            # 行注释
            line_match = self._try_match_line(content, i, line, col)
            if line_match is not None:
                start_line, start_col, end_line, end_col, text, body = line_match
                comments.append(
                    CommentRegion(
                        start_line=start_line,
                        start_col=start_col,
                        end_line=end_line,
                        end_col=end_col,
                        text=text,
                        body=body,
                        comment_type=CommentType.LINE,
                    )
                )
                i, line, col = self._pos_at_to_index(content, end_line, end_col)
                continue

            # 跳过普通字符
            i += 1
            col += 1

        # 为每个注释计算锚点和独立成行标志
        self._compute_anchors(content, comments)
        return comments

    def _compute_anchors(self, content: str, comments: list[CommentRegion]) -> None:
        """为解析出的所有注释计算代码锚点"""
        lines = content.splitlines(keepends=True)
        for c in comments:
            c.standalone = self._check_standalone(lines, c)
            anchor_line, anchor_text = self._find_anchor(lines, c)
            c.anchor_line = anchor_line
            c.anchor_text = anchor_text or ""

    def _try_match_line(self, content: str, i: int, line: int, col: int):
        """尝试匹配行注释"""
        for marker in self._syntax.get("line", []):
            mlen = len(marker)
            if i + mlen > len(content):
                continue
            if content[i : i + mlen] != marker:
                continue
            # Lua 长注释 "--[[" 只通过 block 匹配，行注释只匹配 "--"
            if marker == "--[[":
                continue
            start_line, start_col = line, col
            j = i + mlen
            while j < len(content) and content[j] != "\n":
                j += 1
            # 去掉行尾的 \r（处理 CRLF）
            end_j = j
            if end_j > i and content[end_j - 1] == "\r":
                end_j -= 1
            text = content[i:end_j]
            body = content[i + mlen : end_j]
            end_line, end_col = start_line, start_col + (end_j - i)
            return start_line, start_col, end_line, end_col, text, body
        return None

    def _try_match_block(self, content: str, i: int, line: int, col: int):
        """尝试匹配块注释"""
        for start_marker, end_marker in self._syntax.get("block", []):
            mlen = len(start_marker)
            if i + mlen > len(content):
                continue
            if content[i : i + mlen] != start_marker:
                continue
            # Ruby =begin 必须行首
            if start_marker == "=begin" and col != 0:
                continue
            start_line, start_col = line, col
            j = i + mlen
            end_pos = content.find(end_marker, j)
            if end_pos == -1:
                continue
            end_idx = end_pos + len(end_marker)
            text = content[i:end_idx]
            body = content[j:end_pos]
            end_line, end_col = self._pos_at(content, end_idx)
            ctype = (
                CommentType.DOCSTRING
                if (self._syntax.get("docstring") and start_marker in ('"""', "'''"))
                else CommentType.BLOCK
            )
            return start_line, start_col, end_line, end_col, text, body, ctype
        return None

    def _try_match_docstring(self, content: str, i: int, line: int, col: int):
        """
        尝试匹配 Python 三引号文档字符串

        启发式：仅当三引号所在行是独立行（除前导空白外没有其他代码）时算作文档字符串。
        这避免了误把普通的多行字符串识别为文档字符串。
        """
        n = len(content)
        if i + 3 > n:
            return None
        quote = content[i : i + 3]
        if quote not in ('"""', "'''"):
            return None
        # 检查行首是否只有空白
        line_start = i
        while line_start > 0 and content[line_start - 1] not in "\n":
            line_start -= 1
        prefix = content[line_start:i]
        if prefix.strip() != "":
            return None

        # 查找结束三引号
        # 简化的多行字符串匹配
        j = i + 3
        end_quote_idx = -1
        while j < n:
            if content[j] == "\\" and j + 1 < n:
                j += 2
                continue
            if content[j : j + 3] == quote:
                # 检查同行后面是否还有非空白内容
                rest = content[j + 3 :]
                nl = rest.find("\n")
                same_line = rest if nl == -1 else rest[:nl]
                if same_line.strip() == "":
                    end_quote_idx = j
                    break
            j += 1
        if end_quote_idx == -1:
            return None

        end_idx = end_quote_idx + 3
        start_line, start_col = line, col
        end_line, end_col = self._pos_at(content, end_idx)
        text = content[i:end_idx]
        body = content[i + 3 : end_quote_idx]
        return start_line, start_col, end_line, end_col, text, body

    def _skip_string(
        self, content: str, i: int, line: int, col: int, quote: str
    ) -> tuple[int, int, int]:
        """
        跳过字符串字面量

        Args:
            i: 起始索引（指向开头的引号字符）
            line, col: 对应的行列
            quote: 引号字符

        Returns:
            跳过字符串后新的 (i, line, col)
        """
        n = len(content)
        i += 1  # 跳过起始引号
        col += 1
        while i < n:
            ch = content[i]
            if ch == "\\" and i + 1 < n:
                # 转义字符：跳过下一个字符
                if content[i + 1] == "\n":
                    line += 1
                    col = 0
                else:
                    col += 1
                i += 2
                continue
            if ch == "\n":
                # 单引号/双引号字符串不应该跨行（标准），但允许继续
                # 三引号会在外面单独处理
                if quote in ('"""', "'''"):
                    line += 1
                    col = 0
                    i += 1
                    continue
                # 普通字符串跨行——退出，让外层处理
                return i, line, col
            if ch == quote:
                # 字符串结束
                return i + 1, line, col + 1
            if ch == "\n":
                line += 1
                col = 0
            else:
                col += 1
            i += 1
        return i, line, col

    def _pos_at(self, content: str, idx: int) -> tuple[int, int]:
        """计算 content 中 idx 处的 (line, col)"""
        line, col = 0, 0
        for k in range(min(idx, len(content))):
            if content[k] == "\n":
                line += 1
                col = 0
            else:
                col += 1
        return line, col

    def _pos_at_to_index(self, content: str, line: int, col: int) -> tuple[int, int, int]:
        """计算 content 中 (line, col) 对应的 index"""
        cur_line, cur_col = 0, 0
        for k, ch in enumerate(content):
            if cur_line == line and cur_col == col:
                return k, cur_line, cur_col
            if ch == "\n":
                cur_line += 1
                cur_col = 0
            else:
                cur_col += 1
        return len(content), cur_line, cur_col

    def _check_standalone(self, lines: list[str], comment: CommentRegion) -> bool:
        """判断注释是否独立成行（注释标记之前没有代码）"""
        if comment.start_line >= len(lines):
            return False
        first_line = lines[comment.start_line]
        prefix = first_line[: comment.start_col]
        return prefix.strip() == ""

    def _find_anchor(self, lines: list[str], comment: CommentRegion) -> tuple[int | None, str]:
        """
        找到注释的代码锚点

        - 行内注释（非独立成行）：取同一行的代码部分作为锚点
        - 独立成行注释：取注释之后第一个非空非注释代码行
        - 兜底：取注释之前最近的非空非注释代码行
        - 锚点文本会剥离行内注释，只保留代码部分
        """
        # 行内注释：取同一行注释之前的代码部分
        if not comment.standalone and comment.start_line < len(lines):
            first_line = lines[comment.start_line]
            code_part = first_line[: comment.start_col].rstrip()
            if code_part:
                return comment.start_line, code_part

        # 独立行：取注释之后的第一个非空非注释行
        for i in range(comment.end_line + 1, len(lines)):
            line = lines[i]
            stripped = line.strip()
            if not stripped:
                continue
            if self._is_pure_comment_line(line):
                continue
            # 剥离行内注释，只保留代码部分
            code_part = self._strip_inline_comment(line).rstrip("\n\r")
            if code_part:
                return i, code_part
            # 如果剥离后为空（整行都是注释但 _is_pure_comment_line 没识别到）
            # 这种情况下返回 None 让上层兜底
            return None, ""
        # 兜底：取注释之前最近的非空非注释行
        for i in range(comment.start_line - 1, -1, -1):
            line = lines[i]
            stripped = line.strip()
            if not stripped:
                continue
            if self._is_pure_comment_line(line):
                continue
            code_part = self._strip_inline_comment(line).rstrip("\n\r")
            if code_part:
                return i, code_part
            return None, ""
        return None, ""

    def _strip_inline_comment(self, line: str) -> str:
        """剥离行内注释，返回纯代码部分（不考虑字符串字面量，简化处理）"""
        if not self._syntax.get("line"):
            return line
        for marker in self._syntax.get("line", []):
            if marker == "--[[":
                continue
            idx = self._find_marker_outside_string(line, marker)
            if idx is not None and idx > 0:
                # 找到行内注释，截断
                return line[:idx].rstrip() + "\n" if line.endswith("\n") else line[:idx].rstrip()
        return line

    def _find_marker_outside_string(self, line: str, marker: str) -> int | None:
        """在一行中找到第一个不在字符串内的注释标记"""
        mlen = len(marker)
        i = 0
        in_string = None
        n = len(line)
        while i < n:
            ch = line[i]
            if in_string:
                if ch == "\\" and i + 1 < n:
                    i += 2
                    continue
                if ch == in_string:
                    in_string = None
                i += 1
                continue
            if ch in ('"', "'", "`"):
                in_string = ch
                i += 1
                continue
            if line[i : i + mlen] == marker:
                return i
            i += 1
        return None

    def _is_pure_comment_line(self, line: str) -> bool:
        """判断一行去除前导空白后是否以注释标记开始"""
        stripped = line.strip()
        if not stripped:
            return False
        for marker in self._syntax.get("line", []):
            if marker == "--[[":
                continue
            if stripped.startswith(marker):
                return True
        for start_marker, _ in self._syntax.get("block", []):
            if stripped.startswith(start_marker):
                return True
        return self._syntax.get("html") is True and stripped.startswith("<!--")

    def strip_comments(self, content: str) -> str:
        """
        移除所有注释，保留行结构

        返回一个与原文件行数一致的字符串。独立成行的注释替换为空白行（保持行号对齐），
        行内注释只移除注释部分，保留前面的代码。
        """
        comments = self.parse(content)
        if not comments:
            return content

        lines = content.splitlines(keepends=True)
        new_lines: list[str] = []
        for i, line in enumerate(lines):
            covered_by = [c for c in comments if c.contains_line(i)]
            if not covered_by:
                new_lines.append(line)
                continue
            # 检查是否有非 standalone 的注释（即行内注释）
            inline = [c for c in covered_by if not c.standalone]
            if inline and not all(c.standalone for c in covered_by):
                # 行内注释：保留注释前的代码部分
                first_inline = min(c.start_col for c in inline)
                code_part = line[:first_inline].rstrip()
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
        return "".join(new_lines)


def get_parser_for_file(file_path: str | Path) -> CommentParser:
    """
    根据文件路径返回合适的解析器
    """
    return CommentParser(file_path)
