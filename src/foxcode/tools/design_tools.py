"""
design_tools.py — 设计规范检查工具。

提供 design_check 工具供 AI 主动调用，检查 .foxcode 目录下的 DESIGN.md 规范。
当 /design on 启用时，AI 可在前端代码生成时主动触发此工具。

工具列表：
    DesignCheckTool — 检查设计规范并返回令牌和规则

调用方式：
    # AI 通过 XML 调用
    <function=design_check>
    <parameter=action>tokens</parameter>
    </function>
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from foxcode.tools.base import BaseTool, ToolCategory, ToolParameter, ToolResult, tool

logger = logging.getLogger(__name__)


@tool
class DesignCheckTool(BaseTool):
    """
    设计规范检查工具 — AI 主动调用以查看和遵守项目设计规范。

    当 /design on 启用时，AI 在生成前端代码前应主动调用此工具，
    获取项目的设计令牌（颜色、排版、间距等）并严格遵守。
    """

    name = "design_check"
    description = "检查项目设计规范（DESIGN.md），获取颜色、排版、间距等设计令牌。在前端代码生成时必须遵守这些规范。"
    category = ToolCategory.CODE
    dangerous = False
    parameters = [
        ToolParameter(
            name="action",
            type="string",
            description="操作类型: tokens=获取设计令牌, rules=获取设计规则, check=检查代码是否符合规范",
            required=False,
            default="tokens",
            enum=["tokens", "rules", "check"],
        ),
        ToolParameter(
            name="code_snippet",
            type="string",
            description="要检查的代码片段（action=check 时必填）",
            required=False,
            default="",
        ),
    ]

    async def execute(
        self,
        action: str = "tokens",
        code_snippet: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        """执行设计规范检查。"""
        try:
            # 查找项目中的 DESIGN.md 文件
            design_file = self._find_design_file()

            if not design_file:
                return ToolResult(
                    success=False,
                    output="未找到设计规范文件。请在 .foxcode/ 目录下放置 DESIGN.md 文件。",
                    error="NO_DESIGN_FILE",
                )

            content = design_file.read_text(encoding="utf-8")

            if action == "tokens":
                return self._get_tokens(content)
            elif action == "rules":
                return self._get_rules(content)
            elif action == "check":
                if not code_snippet:
                    return ToolResult(
                        success=False,
                        output="请提供要检查的代码片段。",
                        error="MISSING_CODE_SNIPPET",
                    )
                return self._check_code(content, code_snippet)
            else:
                return ToolResult(
                    success=False,
                    output=f"未知操作: {action}。可用: tokens, rules, check",
                    error="INVALID_ACTION",
                )

        except Exception as e:
            logger.error("设计规范检查失败: %s", e)
            return ToolResult(success=False, output="", error=str(e))

    def _find_design_file(self) -> Path | None:
        """在 .foxcode 目录下查找 DESIGN.md 文件。"""
        # 按优先级查找
        search_paths = [
            Path.cwd() / ".foxcode" / "DESIGN.md",
            Path.cwd() / "DESIGN.md",
            Path.cwd() / "design.md",
            Path.cwd() / ".foxcode" / "design.md",
        ]

        for path in search_paths:
            if path.exists() and path.is_file():
                return path

        return None

    def _get_tokens(self, content: str) -> ToolResult:
        """获取设计令牌摘要。"""
        from foxcode.design_md.lint import lint

        report = lint(content)
        ds = report.designSystem

        # 构建令牌摘要
        tokens = {}

        # 颜色令牌
        if ds.colors:
            tokens["colors"] = {name: color.hex for name, color in ds.colors.items()}

        # 排版令牌
        if ds.typography:
            typography = {}
            for name, typo in ds.typography.items():
                props = {}
                if typo.fontFamily:
                    props["fontFamily"] = typo.fontFamily
                if typo.fontSize:
                    props["fontSize"] = f"{typo.fontSize.value}{typo.fontSize.unit}"
                if typo.fontWeight is not None:
                    props["fontWeight"] = typo.fontWeight
                if typo.lineHeight:
                    props["lineHeight"] = f"{typo.lineHeight.value}{typo.lineHeight.unit}"
                typography[name] = props
            tokens["typography"] = typography

        # 圆角令牌
        if ds.rounded:
            tokens["borderRadius"] = {name: f"{dim.value}{dim.unit}" for name, dim in ds.rounded.items()}

        # 间距令牌
        if ds.spacing:
            tokens["spacing"] = {name: f"{dim.value}{dim.unit}" for name, dim in ds.spacing.items()}

        # 组件令牌
        if ds.components:
            components = {}
            for name, comp in ds.components.items():
                comp_props = {}
                for prop_name, prop_val in comp.properties.items():
                    if hasattr(prop_val, "hex"):
                        comp_props[prop_name] = prop_val.hex
                    elif hasattr(prop_val, "value"):
                        comp_props[prop_name] = f"{prop_val.value}{prop_val.unit}"
                    else:
                        comp_props[prop_name] = str(prop_val)
                components[name] = comp_props
            tokens["components"] = components

        output = json.dumps(tokens, indent=2, ensure_ascii=False)

        return ToolResult(
            success=True,
            output=output,
            data=tokens,
        )

    def _get_rules(self, content: str) -> ToolResult:
        """获取设计规则和 findings。"""
        from foxcode.design_md.lint import lint

        report = lint(content)

        rules_text = "## 设计规范检查结果\n\n"
        rules_text += f"错误: {report.summary['errors']}, 警告: {report.summary['warnings']}, 信息: {report.summary['infos']}\n\n"

        if report.findings:
            rules_text += "### 发现的问题\n\n"
            for f in report.findings:
                rules_text += f"- [{f.severity.upper()}] {f.path}: {f.message}\n"

        # 附加设计令牌的简要说明
        ds = report.designSystem
        rules_text += f"\n### 令牌统计\n"
        rules_text += f"- 颜色: {len(ds.colors)} 个\n"
        rules_text += f"- 排版: {len(ds.typography)} 个\n"
        rules_text += f"- 圆角: {len(ds.rounded)} 个\n"
        rules_text += f"- 间距: {len(ds.spacing)} 个\n"
        rules_text += f"- 组件: {len(ds.components)} 个\n"

        return ToolResult(
            success=True,
            output=rules_text,
            data={"findings": report.findings, "summary": report.summary},
        )

    def _check_code(self, content: str, code_snippet: str) -> ToolResult:
        """检查代码片段是否符合设计规范。"""
        from foxcode.design_md.lint import lint
        import re

        report = lint(content)
        ds = report.designSystem

        violations = []

        # 检查硬编码颜色
        hex_pattern = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
        for match in hex_pattern.finditer(code_snippet):
            found_color = match.group(0).lower()
            # 规范化为 6 位
            if len(found_color) == 4:
                found_color = f"#{found_color[1]}{found_color[1]}{found_color[2]}{found_color[2]}{found_color[3]}{found_color[3]}"

            # 检查是否在规范令牌中
            known_colors = {c.hex for c in ds.colors.values()}
            if found_color not in known_colors:
                violations.append(f"硬编码颜色 '{match.group(0)}' 不在设计规范令牌中")

        # 检查硬编码间距值
        dim_pattern = re.compile(r"(\d+)\s*px")
        for match in dim_pattern.finditer(code_snippet):
            found_value = match.group(0)
            known_spacing = {f"{d.value:.0f}px" for d in ds.spacing.values()}
            known_rounded = {f"{d.value:.0f}px" for d in ds.rounded.values()}
            if found_value not in known_spacing and found_value not in known_rounded:
                violations.append(f"硬编码间距 '{found_value}' 不在设计规范令牌中")

        if violations:
            return ToolResult(
                success=True,
                output=f"发现 {len(violations)} 个规范违反:\n" + "\n".join(f"- {v}" for v in violations),
                data={"violations": violations, "count": len(violations)},
            )

        return ToolResult(
            success=True,
            output="代码片段符合设计规范。",
            data={"violations": [], "count": 0},
        )
