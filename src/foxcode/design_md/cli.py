"""
cli.py — Click 命令注册。

使用 Click 定义主命令和 4 个子命令：lint、diff、export、spec。

调用方式：
    from foxcode.design_md.cli import design_md_cli
    design_md_cli()
"""

from __future__ import annotations

import json
import sys

import click

from foxcode.design_md.lint import lint, LintReport
from foxcode.design_md.utils import read_input, format_output, diff_maps
from foxcode.design_md.dtcg.handler import DtcgEmitterHandler
from foxcode.design_md.tailwind.v4.handler import TailwindV4EmitterHandler
from foxcode.design_md.tailwind.v4.serialize import serialize_to_css
from foxcode.design_md.spec_gen.helpers import get_spec_content, get_rules_table
from foxcode.design_md.linter.rules import DEFAULT_RULE_DESCRIPTORS


@click.group()
def design_md_cli():
    """DESIGN.md — AI 代理优先的设计系统 CLI 工具。"""
    pass


@design_md_cli.command()
@click.argument("file")
@click.option("--format", "fmt", default="json", help="输出格式: json 或 text")
def lint_cmd(file: str, fmt: str):
    """验证 DESIGN.md 文件的结构正确性。"""
    content = read_input(file)
    report = lint(content)

    output = {
        "findings": [
            {"severity": f.severity, "path": f.path, "message": f.message}
            for f in report.findings
        ],
        "summary": report.summary,
    }

    click.echo(format_output(output, fmt))
    sys.exit(1 if report.summary["errors"] > 0 else 0)


@design_md_cli.command()
@click.argument("before")
@click.argument("after")
@click.option("--format", "fmt", default="json", help="输出格式: json 或 text")
def diff_cmd(before: str, after: str, fmt: str):
    """比较两个 DESIGN.md 文件的令牌级变更。"""
    before_content = read_input(before)
    after_content = read_input(after)

    before_report = lint(before_content)
    after_report = lint(after_content)

    def _serialize_components(components):
        return {name: {k: str(v) for k, v in comp.properties.items()} for name, comp in components.items()}

    diff_result = {
        "tokens": {
            "colors": diff_maps(
                {k: v.hex for k, v in before_report.designSystem.colors.items()},
                {k: v.hex for k, v in after_report.designSystem.colors.items()},
            ),
            "typography": diff_maps(
                {k: str(v.__dict__) for k, v in before_report.designSystem.typography.items()},
                {k: str(v.__dict__) for k, v in after_report.designSystem.typography.items()},
            ),
            "rounded": diff_maps(
                {k: f"{v.value}{v.unit}" for k, v in before_report.designSystem.rounded.items()},
                {k: f"{v.value}{v.unit}" for k, v in after_report.designSystem.rounded.items()},
            ),
            "spacing": diff_maps(
                {k: f"{v.value}{v.unit}" for k, v in before_report.designSystem.spacing.items()},
                {k: f"{v.value}{v.unit}" for k, v in after_report.designSystem.spacing.items()},
            ),
            "components": diff_maps(
                _serialize_components(before_report.designSystem.components),
                _serialize_components(after_report.designSystem.components),
            ),
        },
        "findings": {
            "before": before_report.summary,
            "after": after_report.summary,
            "delta": {
                "errors": after_report.summary["errors"] - before_report.summary["errors"],
                "warnings": after_report.summary["warnings"] - before_report.summary["warnings"],
            },
        },
        "regression": (
            after_report.summary["errors"] > before_report.summary["errors"]
            or after_report.summary["warnings"] > before_report.summary["warnings"]
        ),
    }

    click.echo(format_output(diff_result, fmt))
    sys.exit(1 if diff_result["regression"] else 0)


@design_md_cli.command()
@click.argument("file")
@click.argument("format_type", required=True)
def export_cmd(file: str, format_type: str):
    """导出 DESIGN.md 令牌为其他格式。

    支持的格式: css-tailwind, json-tailwind, tailwind, dtcg
    """
    valid_formats = ("css-tailwind", "json-tailwind", "tailwind", "dtcg")
    if format_type not in valid_formats:
        click.echo(json.dumps({"error": f"无效格式 '{format_type}'。有效格式: {', '.join(valid_formats)}"}))
        sys.exit(1)

    content = read_input(file)
    report = lint(content)

    if format_type == "css-tailwind":
        handler = TailwindV4EmitterHandler()
        result = handler.execute(report.designSystem)
        if not result.success:
            click.echo(json.dumps({"error": result.error.get("message", "导出失败")}))
            sys.exit(1)
        click.echo(serialize_to_css(result.data["theme"]))

    elif format_type in ("json-tailwind", "tailwind"):
        from foxcode.design_md.tailwind.handler import TailwindEmitterHandler
        handler = TailwindEmitterHandler()
        result = handler.execute(report.designSystem)
        if not result.success:
            click.echo(json.dumps({"error": result.error.get("message", "导出失败")}))
            sys.exit(1)
        click.echo(json.dumps(result.data, default=str, indent=2, ensure_ascii=False))

    elif format_type == "dtcg":
        handler = DtcgEmitterHandler()
        result = handler.execute(report.designSystem)
        if not result.success:
            click.echo(json.dumps({"error": result.error.get("message", "导出失败")}))
            sys.exit(1)
        click.echo(json.dumps(result.data, default=str, indent=2, ensure_ascii=False))

    sys.exit(1 if report.summary["errors"] > 0 else 0)


@design_md_cli.command()
@click.option("--rules", is_flag=True, help="追加活跃的 lint 规则表。")
@click.option("--rules-only", "rules_only", is_flag=True, help="仅输出活跃的 lint 规则表。")
@click.option("--format", "fmt", default="markdown", help="输出格式 (markdown, json)。")
def spec_cmd(rules: bool, rules_only: bool, fmt: str):
    """输出 DESIGN.md 格式规范。"""
    rules_table = get_rules_table()

    if fmt == "json":
        json_output = {}
        if rules_only:
            json_output["rules"] = [
                {"name": r.name, "severity": r.severity, "description": r.description}
                for r in DEFAULT_RULE_DESCRIPTORS
            ]
        else:
            json_output["spec"] = get_spec_content()
            if rules:
                json_output["rules"] = [
                    {"name": r.name, "severity": r.severity, "description": r.description}
                    for r in DEFAULT_RULE_DESCRIPTORS
                ]
        click.echo(json.dumps(json_output, indent=2, ensure_ascii=False))
        return

    if rules_only:
        click.echo(rules_table)
        return

    output = get_spec_content()
    if rules:
        output += f"\n\n## Active Linting Rules\n\n{rules_table}"
    click.echo(output)
