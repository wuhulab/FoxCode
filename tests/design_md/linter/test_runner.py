"""
test_runner.py — 规则运行器测试。
"""

import pytest
from foxcode.design_md.linter.runner import run_linter, pre_evaluate
from foxcode.design_md.model.spec import DesignSystemState, Finding, ResolvedColor


class TestRunLinter:
    def test_default_rules_on_empty_state(self):
        state = DesignSystemState()
        result = run_linter(state)
        assert result.summary["errors"] == 0

    def test_default_rules_on_state_with_colors(self):
        state = DesignSystemState(colors={"secondary": ResolvedColor(hex="#6C7278", r=108, g=114, b=120, luminance=0.15)})
        result = run_linter(state)
        assert result.summary["warnings"] > 0

    def test_custom_rules(self):
        def custom_rule(state):
            return [Finding(severity="info", message="custom")]
        result = run_linter(DesignSystemState(), rules=[custom_rule])
        assert len(result.findings) == 1

    def test_empty_rules(self):
        result = run_linter(DesignSystemState(), rules=[])
        assert len(result.findings) == 0


class TestPreEvaluate:
    def test_grade_errors_as_fixes(self):
        graded = pre_evaluate([Finding(severity="error", message="err")])
        assert len(graded.fixes) == 1

    def test_grade_warnings_as_improvements(self):
        graded = pre_evaluate([Finding(severity="warning", message="warn")])
        assert len(graded.improvements) == 1

    def test_grade_infos_as_suggestions(self):
        graded = pre_evaluate([Finding(severity="info", message="info")])
        assert len(graded.suggestions) == 1
