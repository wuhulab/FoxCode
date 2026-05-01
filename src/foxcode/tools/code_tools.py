"""
FoxCode 代码分析工具 - 代码搜索和分析功能

这个文件提供代码相关的工具：
1. GrepTool: 正则表达式搜索代码内容
2. GlobTool: 文件模式匹配查找文件
3. 其他代码分析工具

工具用途：
- 快速搜索代码中的关键字、函数名、类名
- 查找特定模式的代码（如TODO、FIXME）
- 分析代码结构和依赖关系

使用方式：
    # 这些工具通过agent自动调用
    # AI会根据需要选择合适的工具
    
    # 例如搜索代码：
    # <function=grep>
    # <parameter=pattern>def.*login</parameter>
    # <parameter=path>src/</parameter>
    # </function>

关键工具：
- GrepTool: 强大的正则搜索工具
  - 支持正则表达式
  - 支持大小写敏感/不敏感
  - 支持上下文显示
  - 支持多种输出模式

搜索技巧：
- 查找函数定义: pattern="def function_name"
- 查找类定义: pattern="class ClassName"
- 查找TODO: pattern="TODO|FIXME"
- 查找导入: pattern="import|from"
"""

from __future__ import annotations

import fnmatch
import logging
import re
from pathlib import Path
from typing import Any

import aiofiles

from foxcode.tools.base import (
    BaseTool,
    ToolCategory,
    ToolParameter,
    ToolResult,
    tool,
)

logger = logging.getLogger(__name__)


@tool
class GrepTool(BaseTool):
    """
    Grep工具 - 强大的代码搜索工具
    
    使用正则表达式在文件中搜索内容，类似于Unix的grep命令。
    
    功能特点：
    - 支持正则表达式搜索
    - 支持大小写敏感/不敏感
    - 支持文件模式过滤（glob）
    - 支持多种输出模式
    - 支持上下文显示
    
    输出模式：
    - content: 显示匹配的行内容
    - files_with_matches: 只显示文件名
    - count: 显示匹配次数
    
    使用示例：
        # 搜索函数定义
        <function=grep>
        <parameter=pattern>def.*login</parameter>
        <parameter=path>src/</parameter>
        <parameter=output_mode>content</parameter>
        </function>
        
        # 搜索TODO（忽略大小写）
        <function=grep>
        <parameter=pattern>todo|fixme</parameter>
        <parameter=ignore_case>true</parameter>
        </function>
    """

    name = "grep"
    description = "Search content in files using regex"
    category = ToolCategory.SEARCH
    parameters = [
        ToolParameter(
            name="pattern",
            type="string",
            description="Regex pattern to search",
            required=True,
        ),
        ToolParameter(
            name="path",
            type="string",
            description="Directory or file path to search",
            required=False,
            default=".",
        ),
        ToolParameter(
            name="glob",
            type="string",
            description="File matching pattern (e.g. *.py)",
            required=False,
            default="*",
        ),
        ToolParameter(
            name="output_mode",
            type="string",
            description="Output mode: content, files_with_matches, count",
            required=False,
            default="content",
            enum=["content", "files_with_matches", "count"],
        ),
        ToolParameter(
            name="ignore_case",
            type="boolean",
            description="Whether to ignore case",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="context_lines",
            type="integer",
            description="Number of context lines to show around matches",
            required=False,
            default=2,
        ),
    ]

    async def execute(
        self,
        pattern: str,
        path: str = ".",
        glob: str = "*",
        output_mode: str = "content",
        ignore_case: bool = False,
        context_lines: int = 2,
        **kwargs: Any,
    ) -> ToolResult:
        """执行 grep 搜索"""
        try:
            base_path = Path(path).resolve()

            if not base_path.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"路径不存在: {path}",
                )

            # 编译正则表达式
            flags = re.IGNORECASE if ignore_case else 0
            try:
                regex = re.compile(pattern, flags)
            except re.error as e:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"无效的正则表达式: {e}",
                )

            # 获取要搜索的文件
            if base_path.is_file():
                files = [base_path]
            else:
                files = [
                    f for f in base_path.rglob("*")
                    if f.is_file() and fnmatch.fnmatch(f.name, glob)
                ]

            # 搜索文件
            results = []
            file_matches = {}

            for file_path in files[:1000]:  # 限制搜索文件数量
                try:
                    async with aiofiles.open(file_path, encoding="utf-8") as f:
                        lines = await f.readlines()

                    matches_in_file = []
                    for i, line in enumerate(lines):
                        if regex.search(line):
                            matches_in_file.append((i, line.rstrip("\n\r")))

                    if matches_in_file:
                        file_matches[str(file_path)] = matches_in_file

                        if output_mode == "content":
                            for line_num, line_content in matches_in_file:
                                # 获取上下文
                                context = []
                                start = max(0, line_num - context_lines)
                                end = min(len(lines), line_num + context_lines + 1)

                                for j in range(start, end):
                                    prefix = ">>>" if j == line_num else "   "
                                    context.append(f"{prefix} {j + 1:4d}→{lines[j].rstrip()}")

                                results.append({
                                    "file": str(file_path),
                                    "line": line_num + 1,
                                    "content": line_content,
                                    "context": "\n".join(context),
                                })

                except (UnicodeDecodeError, PermissionError):
                    continue

            # 格式化输出
            if output_mode == "files_with_matches":
                output = f"模式: {pattern}\n"
                output += f"找到 {len(file_matches)} 个文件\n\n"
                output += "\n".join(sorted(file_matches.keys()))

            elif output_mode == "count":
                output = f"模式: {pattern}\n\n"
                for file_path, matches in sorted(file_matches.items()):
                    output += f"{file_path}: {len(matches)}\n"

            else:  # content
                output = f"模式: {pattern}\n"
                output += f"找到 {len(results)} 处匹配\n\n"

                for r in results[:100]:  # 限制输出
                    output += f"\n{r['file']}:{r['line']}\n"
                    output += f"{r['context']}\n"

                if len(results) > 100:
                    output += f"\n... 共 {len(results)} 处匹配，仅显示前 100 处"

            return ToolResult(
                success=True,
                output=output,
                data={
                    "pattern": pattern,
                    "path": str(base_path),
                    "glob": glob,
                    "match_count": len(results),
                    "file_count": len(file_matches),
                },
            )

        except Exception as e:
            logger.error(f"Grep 搜索失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=str(e),
            )


@tool
class SearchCodebaseTool(BaseTool):
    """Semantic codebase search"""

    name = "search_codebase"
    description = "Search codebase using natural language description"
    category = ToolCategory.SEARCH
    parameters = [
        ToolParameter(
            name="query",
            type="string",
            description="Search query (natural language description)",
            required=True,
        ),
        ToolParameter(
            name="target_directories",
            type="array",
            description="List of directories to search",
            required=False,
            default=None,
        ),
    ]

    async def execute(
        self,
        query: str,
        target_directories: list[str] | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """执行语义化搜索"""
        try:
            # 将自然语言查询转换为关键词
            keywords = self._extract_keywords(query)

            # 确定搜索目录
            if target_directories:
                dirs = [Path(d) for d in target_directories]
            else:
                dirs = [Path.cwd()]

            # 搜索文件
            results = []

            for base_dir in dirs:
                if not base_dir.exists():
                    continue

                for file_path in base_dir.rglob("*"):
                    if not file_path.is_file():
                        continue

                    # 跳过常见忽略目录
                    if any(part in file_path.parts for part in [
                        "node_modules", ".git", "__pycache__",
                        "venv", ".venv", "dist", "build",
                    ]):
                        continue

                    try:
                        async with aiofiles.open(file_path, encoding="utf-8") as f:
                            content = await f.read()

                        # 计算相关性分数
                        score = self._calculate_relevance(content, keywords)

                        if score > 0:
                            results.append({
                                "file": str(file_path.relative_to(base_dir)),
                                "score": score,
                                "size": len(content),
                            })

                    except (UnicodeDecodeError, PermissionError):
                        continue

            # 按相关性排序
            results.sort(key=lambda x: x["score"], reverse=True)

            # 格式化输出
            output = f"查询: {query}\n"
            output += f"关键词: {', '.join(keywords)}\n\n"

            for r in results[:20]:
                output += f"[{r['score']:.2f}] {r['file']}\n"

            if len(results) > 20:
                output += f"\n... 共 {len(results)} 个结果"

            return ToolResult(
                success=True,
                output=output,
                data={
                    "query": query,
                    "keywords": keywords,
                    "result_count": len(results),
                    "results": results[:50],
                },
            )

        except Exception as e:
            logger.error(f"代码库搜索失败: {e}")
            return ToolResult(
                success=False,
                output="",
                error=str(e),
            )

    def _extract_keywords(self, query: str) -> list[str]:
        """从查询中提取关键词"""
        # 移除常见停用词
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "need", "dare", "ought", "used", "to", "of", "in",
            "for", "on", "with", "at", "by", "from", "as", "into",
            "through", "during", "before", "after", "above", "below",
            "between", "under", "again", "further", "then", "once",
            "here", "there", "when", "where", "why", "how", "all",
            "each", "few", "more", "most", "other", "some", "such",
            "no", "nor", "not", "only", "own", "same", "so", "than",
            "too", "very", "just", "and", "but", "if", "or", "because",
            "until", "while", "about", "against", "find", "search", "look", "show", "get", "what",
        }

        # 提取单词
        words = re.findall(r"\b\w+\b", query.lower())

        # 过滤并返回
        return [w for w in words if w not in stop_words and len(w) > 2]

    def _calculate_relevance(self, content: str, keywords: list[str]) -> float:
        """计算内容与关键词的相关性"""
        content_lower = content.lower()
        score = 0.0

        for keyword in keywords:
            count = content_lower.count(keyword)
            if count > 0:
                # 对数缩放避免大文件优势
                import math
                score += math.log1p(count)

        return score
