"""
design_md 包：DESIGN.md 格式的设计系统规范检查和导出工具。

将 TypeScript 版 design.md 项目完整重写为 Python，集成到 foxcode 中。
提供 lint（验证）、diff（比较）、export（导出）、spec（规范输出）四大功能。

核心调用方式：
    from foxcode.design_md import lint
    report = lint(content)
"""

from foxcode.design_md.lint import lint, LintReport, LintOptions

from foxcode.design_md.model.spec import (
    DesignSystemState,
    ResolvedColor,
    ResolvedDimension,
    ResolvedTypography,
    ResolvedValue,
    ComponentDef,
    Finding,
    Severity,
)

from foxcode.design_md.linter.runner import run_linter, pre_evaluate
from foxcode.design_md.linter.rules import DEFAULT_RULES, DEFAULT_RULE_DESCRIPTORS
from foxcode.design_md.linter.rules.types import LintRule, RuleDescriptor
from foxcode.design_md.linter.spec import GradedTokenEdits, TokenEditEntry

from foxcode.design_md.model.handler import contrast_ratio
from foxcode.design_md.tailwind.handler import TailwindEmitterHandler
from foxcode.design_md.tailwind.v4.handler import TailwindV4EmitterHandler
from foxcode.design_md.tailwind.v4.serialize import serialize_to_css as serialize_tailwind_v4
from foxcode.design_md.dtcg.handler import DtcgEmitterHandler
from foxcode.design_md.fixer.handler import fix_section_order
from foxcode.design_md.fixer.spec import FixerInput, FixerResult
