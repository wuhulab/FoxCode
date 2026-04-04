"""
FoxCode 评估器代理模块

实现独立的评估器代理，用于评估生成器代理的工作质量。
支持代码质量评估和设计质量评估。
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class EvaluationType(str, Enum):
    """评估类型枚举"""
    CODE_QUALITY = "code_quality"
    DESIGN_QUALITY = "design_quality"
    FULL = "full"


@dataclass
class EvaluationScore:
    """
    评估分数
    
    Attributes:
        category: 评分类别
        score: 分数 (0-10)
        max_score: 最高分
        comments: 评语
    """
    category: str
    score: float
    max_score: float = 10.0
    comments: str = ""
    
    @property
    def percentage(self) -> float:
        """
        获取百分比分数
        
        Returns:
            百分比分数 (0-100)
        """
        if self.max_score <= 0:
            return 0.0
        return (self.score / self.max_score) * 100
    
    def to_dict(self) -> dict[str, Any]:
        """
        转换为字典格式
        
        Returns:
            包含分数信息的字典
        """
        return {
            "category": self.category,
            "score": self.score,
            "max_score": self.max_score,
            "percentage": self.percentage,
            "comments": self.comments,
        }


@dataclass
class EvaluationReport:
    """
    评估报告
    
    Attributes:
        evaluation_type: 评估类型
        timestamp: 评估时间戳
        scores: 评分列表
        total_score: 总分
        passed: 是否通过
        threshold: 通过阈值
        recommendations: 改进建议列表
        summary: 总结
    """
    evaluation_type: EvaluationType
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    scores: list[EvaluationScore] = field(default_factory=list)
    total_score: float = 0.0
    passed: bool = False
    threshold: float = 7.0
    recommendations: list[str] = field(default_factory=list)
    summary: str = ""
    
    def calculate_total(self) -> float:
        """
        计算总分
        
        Returns:
            平均分数
        """
        if not self.scores:
            return 0.0
        return sum(s.score for s in self.scores) / len(self.scores)
    
    def check_passed(self) -> bool:
        """
        检查是否通过评估
        
        Returns:
            是否通过
        """
        self.total_score = self.calculate_total()
        self.passed = self.total_score >= self.threshold
        return self.passed
    
    def to_dict(self) -> dict[str, Any]:
        """
        转换为字典格式
        
        Returns:
            包含报告信息的字典
        """
        return {
            "evaluation_type": self.evaluation_type.value,
            "timestamp": self.timestamp,
            "scores": [s.to_dict() for s in self.scores],
            "total_score": self.total_score,
            "passed": self.passed,
            "threshold": self.threshold,
            "recommendations": self.recommendations,
            "summary": self.summary,
        }
    
    def to_markdown(self) -> str:
        """
        转换为 Markdown 格式
        
        Returns:
            Markdown 格式的报告字符串
        """
        lines = [
            f"# 评估报告",
            f"",
            f"- **评估类型**: {self.evaluation_type.value}",
            f"- **评估时间**: {self.timestamp}",
            f"- **总分**: {self.total_score:.1f}/10",
            f"- **结果**: {'✅ 通过' if self.passed else '❌ 未通过'}",
            f"",
            "## 详细评分",
            "",
        ]
        
        for score in self.scores:
            status = "✅" if score.score >= self.threshold else "❌"
            lines.append(f"### {status} {score.category}")
            lines.append(f"- 分数: {score.score:.1f}/{score.max_score:.1f}")
            if score.comments:
                lines.append(f"- 评语: {score.comments}")
            lines.append("")
        
        if self.recommendations:
            lines.append("## 改进建议")
            for i, rec in enumerate(self.recommendations, 1):
                lines.append(f"{i}. {rec}")
            lines.append("")
        
        if self.summary:
            lines.append("## 总结")
            lines.append(self.summary)
        
        return "\n".join(lines)
    
    def add_score(self, score: EvaluationScore) -> None:
        """
        添加评分项
        
        Args:
            score: 评分对象
        """
        self.scores.append(score)


class CodeAnalyzer:
    """
    代码分析器
    
    提供静态代码分析功能，用于评估代码质量。
    """
    
    @staticmethod
    def count_lines(code: str) -> dict[str, int]:
        """
        统计代码行数
        
        Args:
            code: 代码内容
            
        Returns:
            包含各类行数统计的字典
        """
        lines = code.split('\n')
        total_lines = len(lines)
        blank_lines = 0
        comment_lines = 0
        code_lines = 0
        
        in_multiline_comment = False
        
        for line in lines:
            stripped = line.strip()
            
            if not stripped:
                blank_lines += 1
                continue
            
            if in_multiline_comment:
                comment_lines += 1
                if '"""' in stripped or "'''" in stripped:
                    in_multiline_comment = False
                continue
            
            if stripped.startswith('#'):
                comment_lines += 1
                continue
            
            if stripped.startswith('"""') or stripped.startswith("'''"):
                comment_lines += 1
                if stripped.count('"""') == 1 and stripped.count("'''") == 0:
                    in_multiline_comment = True
                continue
            
            code_lines += 1
        
        return {
            "total": total_lines,
            "blank": blank_lines,
            "comment": comment_lines,
            "code": code_lines,
        }
    
    @staticmethod
    def check_syntax(code: str) -> tuple[bool, str]:
        """
        检查代码语法
        
        Args:
            code: 代码内容
            
        Returns:
            (是否通过, 错误信息)
        """
        try:
            ast.parse(code)
            return True, ""
        except SyntaxError as e:
            return False, f"语法错误 (行 {e.lineno}): {e.msg}"
        except Exception as e:
            return False, f"解析错误: {str(e)}"
    
    @staticmethod
    def count_functions_and_classes(code: str) -> dict[str, int]:
        """
        统计函数和类数量
        
        Args:
            code: 代码内容
            
        Returns:
            包含函数和类数量的字典
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return {"functions": 0, "classes": 0, "methods": 0}
        
        functions = 0
        classes = 0
        methods = 0
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if any(isinstance(parent, ast.ClassDef) for parent in ast.walk(tree)):
                    methods += 1
                else:
                    functions += 1
            elif isinstance(node, ast.ClassDef):
                classes += 1
        
        return {
            "functions": functions,
            "classes": classes,
            "methods": methods,
        }
    
    @staticmethod
    def check_error_handling(code: str) -> dict[str, Any]:
        """
        检查错误处理
        
        Args:
            code: 代码内容
            
        Returns:
            包含错误处理统计的字典
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return {"try_blocks": 0, "except_handlers": 0, "has_finally": False}
        
        try_blocks = 0
        except_handlers = 0
        has_finally = False
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                try_blocks += 1
                except_handlers += len(node.handlers)
                if node.finalbody:
                    has_finally = True
        
        return {
            "try_blocks": try_blocks,
            "except_handlers": except_handlers,
            "has_finally": has_finally,
        }
    
    @staticmethod
    def check_docstrings(code: str) -> dict[str, Any]:
        """
        检查文档字符串
        
        Args:
            code: 代码内容
            
        Returns:
            包含文档字符串统计的字典
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return {"total_items": 0, "with_docstrings": 0, "coverage": 0.0}
        
        total_items = 0
        with_docstrings = 0
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                total_items += 1
                if ast.get_docstring(node):
                    with_docstrings += 1
        
        coverage = (with_docstrings / total_items * 100) if total_items > 0 else 100.0
        
        return {
            "total_items": total_items,
            "with_docstrings": with_docstrings,
            "coverage": coverage,
        }
    
    @staticmethod
    def check_type_hints(code: str) -> dict[str, Any]:
        """
        检查类型提示
        
        Args:
            code: 代码内容
            
        Returns:
            包含类型提示统计的字典
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return {"total_functions": 0, "with_hints": 0, "coverage": 0.0}
        
        total_functions = 0
        with_hints = 0
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                total_functions += 1
                
                has_return_hint = node.returns is not None
                has_arg_hints = any(
                    arg.annotation is not None
                    for arg in node.args.args
                )
                
                if has_return_hint or has_arg_hints:
                    with_hints += 1
        
        coverage = (with_hints / total_functions * 100) if total_functions > 0 else 100.0
        
        return {
            "total_functions": total_functions,
            "with_hints": with_hints,
            "coverage": coverage,
        }


class EvaluatorAgent:
    """
    评估器代理
    
    独立的评估器代理，用于评估生成器代理的工作质量。
    支持代码质量评估和设计质量评估。
    
    Attributes:
        passing_threshold: 通过阈值
        code_weights: 代码质量评估权重
        design_weights: 设计质量评估权重
    """
    
    def __init__(
        self,
        passing_threshold: float = 7.0,
        code_weights: dict[str, float] | None = None,
        design_weights: dict[str, float] | None = None,
    ):
        """
        初始化评估器代理
        
        Args:
            passing_threshold: 通过阈值 (默认 7.0)
            code_weights: 代码质量评估权重字典
            design_weights: 设计质量评估权重字典
        """
        self.passing_threshold = passing_threshold
        
        self.code_weights = code_weights or {
            "correctness": 0.3,
            "test_coverage": 0.25,
            "code_style": 0.2,
            "error_handling": 0.25,
        }
        
        self.design_weights = design_weights or {
            "requirements": 0.3,
            "architecture": 0.3,
            "extensibility": 0.2,
            "documentation": 0.2,
        }
        
        self._analyzer = CodeAnalyzer()
        
        logger.info(f"评估器代理初始化完成，通过阈值: {passing_threshold}")
    
    async def evaluate_code(
        self,
        code_content: str,
        file_path: str | Path | None = None,
        test_results: dict[str, Any] | None = None,
        style_check_results: dict[str, Any] | None = None,
    ) -> EvaluationReport:
        """
        评估代码质量
        
        对代码进行全面的质量评估，包括正确性、测试覆盖率、
        代码风格和错误处理等方面。
        
        Args:
            code_content: 代码内容字符串
            file_path: 文件路径（可选，用于日志记录）
            test_results: 测试结果字典，包含测试通过率等信息
            style_check_results: 风格检查结果字典
            
        Returns:
            EvaluationReport: 评估报告对象
            
        Raises:
            ValueError: 当代码内容为空时抛出
        """
        if not code_content or not code_content.strip():
            raise ValueError("代码内容不能为空")
        
        file_name = Path(file_path).name if file_path else "未知文件"
        logger.info(f"开始评估代码质量: {file_name}")
        
        report = EvaluationReport(
            evaluation_type=EvaluationType.CODE_QUALITY,
            threshold=self.passing_threshold,
        )
        
        try:
            correctness_score = self._evaluate_correctness(code_content)
            report.add_score(correctness_score)
            
            test_score = self._evaluate_test_coverage(test_results)
            report.add_score(test_score)
            
            style_score = self._evaluate_code_style(code_content, style_check_results)
            report.add_score(style_score)
            
            error_handling_score = self._evaluate_error_handling(code_content)
            report.add_score(error_handling_score)
            
            report.recommendations = self._generate_code_recommendations(report)
            
            report.summary = self._generate_code_summary(report, file_name)
            
            report.check_passed()
            
            logger.info(
                f"代码质量评估完成: {file_name}, "
                f"总分: {report.total_score:.1f}, "
                f"{'通过' if report.passed else '未通过'}"
            )
            
        except Exception as e:
            logger.error(f"代码质量评估失败: {e}")
            report.summary = f"评估过程中发生错误: {str(e)}"
            report.passed = False
        
        return report
    
    async def evaluate_design(
        self,
        design_doc: str,
        requirements: list[str] | None = None,
        architecture_diagram: str | None = None,
    ) -> EvaluationReport:
        """
        评估设计质量
        
        对设计文档进行全面的质量评估，包括需求覆盖、架构设计、
        可扩展性和文档完整性等方面。
        
        Args:
            design_doc: 设计文档内容字符串
            requirements: 需求列表
            architecture_diagram: 架构图描述（可选）
            
        Returns:
            EvaluationReport: 评估报告对象
            
        Raises:
            ValueError: 当设计文档为空时抛出
        """
        if not design_doc or not design_doc.strip():
            raise ValueError("设计文档不能为空")
        
        logger.info("开始评估设计质量")
        
        report = EvaluationReport(
            evaluation_type=EvaluationType.DESIGN_QUALITY,
            threshold=self.passing_threshold,
        )
        
        try:
            requirements_score = self._evaluate_requirements(design_doc, requirements)
            report.add_score(requirements_score)
            
            architecture_score = self._evaluate_architecture(design_doc, architecture_diagram)
            report.add_score(architecture_score)
            
            extensibility_score = self._evaluate_extensibility(design_doc)
            report.add_score(extensibility_score)
            
            documentation_score = self._evaluate_documentation(design_doc)
            report.add_score(documentation_score)
            
            report.recommendations = self._generate_design_recommendations(report)
            
            report.summary = self._generate_design_summary(report)
            
            report.check_passed()
            
            logger.info(
                f"设计质量评估完成, "
                f"总分: {report.total_score:.1f}, "
                f"{'通过' if report.passed else '未通过'}"
            )
            
        except Exception as e:
            logger.error(f"设计质量评估失败: {e}")
            report.summary = f"评估过程中发生错误: {str(e)}"
            report.passed = False
        
        return report
    
    async def evaluate_full(
        self,
        code_content: str,
        design_doc: str,
        requirements: list[str] | None = None,
        test_results: dict[str, Any] | None = None,
        style_check_results: dict[str, Any] | None = None,
    ) -> EvaluationReport:
        """
        执行完整评估
        
        同时评估代码质量和设计质量，生成综合评估报告。
        
        Args:
            code_content: 代码内容
            design_doc: 设计文档
            requirements: 需求列表
            test_results: 测试结果
            style_check_results: 风格检查结果
            
        Returns:
            EvaluationReport: 综合评估报告
        """
        logger.info("开始执行完整评估")
        
        code_report = await self.evaluate_code(
            code_content=code_content,
            test_results=test_results,
            style_check_results=style_check_results,
        )
        
        design_report = await self.evaluate_design(
            design_doc=design_doc,
            requirements=requirements,
        )
        
        combined_report = EvaluationReport(
            evaluation_type=EvaluationType.FULL,
            threshold=self.passing_threshold,
        )
        
        for score in code_report.scores:
            combined_report.add_score(EvaluationScore(
                category=f"代码 - {score.category}",
                score=score.score,
                max_score=score.max_score,
                comments=score.comments,
            ))
        
        for score in design_report.scores:
            combined_report.add_score(EvaluationScore(
                category=f"设计 - {score.category}",
                score=score.score,
                max_score=score.max_score,
                comments=score.comments,
            ))
        
        combined_report.recommendations = (
            code_report.recommendations + design_report.recommendations
        )
        
        combined_report.summary = self._generate_full_summary(code_report, design_report)
        
        combined_report.check_passed()
        
        logger.info(
            f"完整评估完成, "
            f"总分: {combined_report.total_score:.1f}, "
            f"{'通过' if combined_report.passed else '未通过'}"
        )
        
        return combined_report
    
    def _evaluate_correctness(self, code: str) -> EvaluationScore:
        """
        评估代码正确性
        
        通过语法检查、AST 解析等方式评估代码的正确性。
        
        Args:
            code: 代码内容
            
        Returns:
            EvaluationScore: 正确性评分
        """
        score = 10.0
        comments_parts = []
        
        syntax_ok, syntax_error = self._analyzer.check_syntax(code)
        if not syntax_ok:
            score -= 5.0
            comments_parts.append(f"存在语法错误: {syntax_error}")
        else:
            comments_parts.append("语法检查通过")
        
        line_stats = self._analyzer.count_lines(code)
        if line_stats["code"] > 500:
            score -= 1.0
            comments_parts.append("代码行数较多，建议拆分")
        
        func_stats = self._analyzer.count_functions_and_classes(code)
        if func_stats["functions"] > 20 or func_stats["classes"] > 10:
            score -= 1.0
            comments_parts.append("函数/类数量较多，考虑模块化")
        
        doc_stats = self._analyzer.check_docstrings(code)
        if doc_stats["coverage"] < 50:
            score -= 1.0
            comments_parts.append(f"文档字符串覆盖率较低 ({doc_stats['coverage']:.1f}%)")
        
        score = max(0.0, min(10.0, score))
        
        return EvaluationScore(
            category="正确性",
            score=score,
            comments="; ".join(comments_parts),
        )
    
    def _evaluate_test_coverage(
        self,
        test_results: dict[str, Any] | None
    ) -> EvaluationScore:
        """
        评估测试覆盖率
        
        根据测试结果评估测试覆盖率。
        
        Args:
            test_results: 测试结果字典，应包含:
                - total_tests: 总测试数
                - passed_tests: 通过测试数
                - coverage_percent: 覆盖率百分比
                
        Returns:
            EvaluationScore: 测试覆盖率评分
        """
        if not test_results:
            return EvaluationScore(
                category="测试覆盖率",
                score=5.0,
                comments="未提供测试结果，给予中等评分",
            )
        
        score = 10.0
        comments_parts = []
        
        total_tests = test_results.get("total_tests", 0)
        passed_tests = test_results.get("passed_tests", 0)
        coverage_percent = test_results.get("coverage_percent", 0)
        
        if total_tests == 0:
            score -= 5.0
            comments_parts.append("未发现测试用例")
        else:
            pass_rate = (passed_tests / total_tests) * 100
            if pass_rate < 80:
                score -= 3.0
                comments_parts.append(f"测试通过率较低 ({pass_rate:.1f}%)")
            elif pass_rate < 95:
                score -= 1.0
                comments_parts.append(f"测试通过率良好 ({pass_rate:.1f}%)")
            else:
                comments_parts.append(f"测试通过率优秀 ({pass_rate:.1f}%)")
        
        if coverage_percent < 50:
            score -= 3.0
            comments_parts.append(f"代码覆盖率较低 ({coverage_percent:.1f}%)")
        elif coverage_percent < 80:
            score -= 1.0
            comments_parts.append(f"代码覆盖率良好 ({coverage_percent:.1f}%)")
        else:
            comments_parts.append(f"代码覆盖率优秀 ({coverage_percent:.1f}%)")
        
        score = max(0.0, min(10.0, score))
        
        return EvaluationScore(
            category="测试覆盖率",
            score=score,
            comments="; ".join(comments_parts),
        )
    
    def _evaluate_code_style(
        self,
        code: str,
        style_results: dict[str, Any] | None
    ) -> EvaluationScore:
        """
        评估代码风格
        
        检查代码风格是否符合规范，包括命名规范、缩进、
        行长度等方面。
        
        Args:
            code: 代码内容
            style_results: 风格检查结果（可选）
            
        Returns:
            EvaluationScore: 代码风格评分
        """
        score = 10.0
        comments_parts = []
        
        lines = code.split('\n')
        long_lines = sum(1 for line in lines if len(line) > 100)
        if long_lines > 0:
            ratio = long_lines / len(lines) if lines else 0
            if ratio > 0.2:
                score -= 2.0
                comments_parts.append(f"存在较多超长行 ({long_lines} 行)")
            else:
                score -= 0.5
                comments_parts.append(f"存在少量超长行 ({long_lines} 行)")
        
        type_stats = self._analyzer.check_type_hints(code)
        if type_stats["total_functions"] > 0:
            if type_stats["coverage"] < 30:
                score -= 2.0
                comments_parts.append(f"类型提示覆盖率较低 ({type_stats['coverage']:.1f}%)")
            elif type_stats["coverage"] < 70:
                score -= 0.5
                comments_parts.append(f"类型提示覆盖率良好 ({type_stats['coverage']:.1f}%)")
            else:
                comments_parts.append(f"类型提示覆盖率优秀 ({type_stats['coverage']:.1f}%)")
        
        snake_case_pattern = r'^[a-z][a-z0-9_]*$'
        camel_case_pattern = r'^[A-Z][a-zA-Z0-9]*$'
        
        try:
            tree = ast.parse(code)
            naming_issues = 0
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if not (re.match(snake_case_pattern, node.name) or 
                            node.name.startswith('_')):
                        naming_issues += 1
                elif isinstance(node, ast.ClassDef):
                    if not re.match(camel_case_pattern, node.name):
                        naming_issues += 1
            
            if naming_issues > 0:
                score -= min(2.0, naming_issues * 0.5)
                comments_parts.append(f"存在命名规范问题 ({naming_issues} 处)")
            else:
                comments_parts.append("命名规范检查通过")
                
        except SyntaxError:
            comments_parts.append("无法检查命名规范（语法错误）")
        
        if style_results:
            errors = style_results.get("errors", [])
            warnings = style_results.get("warnings", [])
            
            if errors:
                score -= min(3.0, len(errors) * 0.5)
                comments_parts.append(f"风格检查错误: {len(errors)} 个")
            if warnings:
                score -= min(1.0, len(warnings) * 0.1)
                comments_parts.append(f"风格检查警告: {len(warnings)} 个")
        
        score = max(0.0, min(10.0, score))
        
        return EvaluationScore(
            category="代码风格",
            score=score,
            comments="; ".join(comments_parts),
        )
    
    def _evaluate_error_handling(self, code: str) -> EvaluationScore:
        """
        评估错误处理
        
        检查代码中的错误处理机制是否完善。
        
        Args:
            code: 代码内容
            
        Returns:
            EvaluationScore: 错误处理评分
        """
        score = 10.0
        comments_parts = []
        
        error_stats = self._analyzer.check_error_handling(code)
        
        try:
            tree = ast.parse(code)
            
            dangerous_operations = 0
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func_name = ""
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr
                    
                    if func_name in ["open", "exec", "eval", "compile"]:
                        dangerous_operations += 1
            
            if dangerous_operations > 0:
                if error_stats["try_blocks"] == 0:
                    score -= 3.0
                    comments_parts.append(
                        f"存在 {dangerous_operations} 处潜在危险操作，但缺少错误处理"
                    )
                else:
                    comments_parts.append(
                        f"存在 {dangerous_operations} 处潜在危险操作，已有错误处理"
                    )
        except SyntaxError:
            pass
        
        func_stats = self._analyzer.count_functions_and_classes(code)
        total_functions = func_stats["functions"] + func_stats["methods"]
        
        if total_functions > 0:
            try_block_ratio = error_stats["try_blocks"] / total_functions
            
            if try_block_ratio < 0.1:
                score -= 2.0
                comments_parts.append("错误处理覆盖率较低")
            elif try_block_ratio < 0.3:
                score -= 0.5
                comments_parts.append("错误处理覆盖率良好")
            else:
                comments_parts.append("错误处理覆盖率优秀")
        
        if error_stats["try_blocks"] > 0:
            if error_stats["has_finally"]:
                comments_parts.append("使用了 finally 块进行资源清理")
            
            if error_stats["except_handlers"] > error_stats["try_blocks"] * 2:
                comments_parts.append("异常处理粒度良好")
            else:
                score -= 1.0
                comments_parts.append("建议使用更具体的异常类型")
        else:
            if total_functions > 5:
                score -= 2.0
                comments_parts.append("未发现 try-except 错误处理块")
            else:
                comments_parts.append("代码规模较小，错误处理要求较低")
        
        bare_except_pattern = r'except\s*:'
        bare_excepts = len(re.findall(bare_except_pattern, code))
        if bare_excepts > 0:
            score -= bare_excepts * 1.0
            comments_parts.append(f"存在 {bare_excepts} 处裸 except 子句")
        
        score = max(0.0, min(10.0, score))
        
        return EvaluationScore(
            category="错误处理",
            score=score,
            comments="; ".join(comments_parts),
        )
    
    def _evaluate_requirements(
        self,
        design_doc: str,
        requirements: list[str] | None
    ) -> EvaluationScore:
        """
        评估需求覆盖
        
        检查设计文档是否覆盖了所有需求。
        
        Args:
            design_doc: 设计文档内容
            requirements: 需求列表
            
        Returns:
            EvaluationScore: 需求覆盖评分
        """
        score = 10.0
        comments_parts = []
        
        if not requirements:
            comments_parts.append("未提供需求列表，无法评估需求覆盖")
            return EvaluationScore(
                category="需求覆盖",
                score=7.0,
                comments="; ".join(comments_parts),
            )
        
        design_lower = design_doc.lower()
        covered_count = 0
        uncovered_requirements = []
        
        for req in requirements:
            req_keywords = self._extract_keywords(req)
            
            matched = sum(
                1 for keyword in req_keywords
                if keyword.lower() in design_lower
            )
            
            if matched >= len(req_keywords) * 0.5:
                covered_count += 1
            else:
                uncovered_requirements.append(req[:50] + "..." if len(req) > 50 else req)
        
        coverage_rate = (covered_count / len(requirements)) * 100
        
        if coverage_rate >= 90:
            comments_parts.append(f"需求覆盖率优秀 ({coverage_rate:.1f}%)")
        elif coverage_rate >= 70:
            score -= 1.0
            comments_parts.append(f"需求覆盖率良好 ({coverage_rate:.1f}%)")
        elif coverage_rate >= 50:
            score -= 3.0
            comments_parts.append(f"需求覆盖率一般 ({coverage_rate:.1f}%)")
        else:
            score -= 5.0
            comments_parts.append(f"需求覆盖率较低 ({coverage_rate:.1f}%)")
        
        if uncovered_requirements:
            comments_parts.append(
                f"未覆盖需求示例: {uncovered_requirements[0]}"
            )
        
        score = max(0.0, min(10.0, score))
        
        return EvaluationScore(
            category="需求覆盖",
            score=score,
            comments="; ".join(comments_parts),
        )
    
    def _evaluate_architecture(
        self,
        design_doc: str,
        architecture_diagram: str | None
    ) -> EvaluationScore:
        """
        评估架构设计
        
        检查设计文档中的架构描述是否清晰完整。
        
        Args:
            design_doc: 设计文档内容
            architecture_diagram: 架构图描述
            
        Returns:
            EvaluationScore: 架构设计评分
        """
        score = 10.0
        comments_parts = []
        
        architecture_keywords = [
            "架构", "architecture", "模块", "module", "组件", "component",
            "层次", "layer", "接口", "interface", "依赖", "dependency",
            "数据流", "data flow", "通信", "communication",
        ]
        
        design_lower = design_doc.lower()
        matched_keywords = sum(
            1 for keyword in architecture_keywords
            if keyword.lower() in design_lower
        )
        
        keyword_coverage = matched_keywords / len(architecture_keywords)
        
        if keyword_coverage >= 0.6:
            comments_parts.append("架构描述完整")
        elif keyword_coverage >= 0.3:
            score -= 2.0
            comments_parts.append("架构描述基本完整")
        else:
            score -= 4.0
            comments_parts.append("架构描述不够详细")
        
        if architecture_diagram:
            comments_parts.append("包含架构图描述")
        else:
            score -= 1.0
            comments_parts.append("缺少架构图描述")
        
        section_patterns = [
            (r'##?\s*系统架构', "系统架构章节"),
            (r'##?\s*模块设计', "模块设计章节"),
            (r'##?\s*接口设计', "接口设计章节"),
            (r'##?\s*数据设计', "数据设计章节"),
        ]
        
        found_sections = []
        for pattern, section_name in section_patterns:
            if re.search(pattern, design_doc, re.IGNORECASE):
                found_sections.append(section_name)
        
        if len(found_sections) >= 3:
            comments_parts.append(f"架构文档结构完整 ({len(found_sections)} 个关键章节)")
        elif len(found_sections) >= 1:
            score -= 1.0
            comments_parts.append(f"架构文档结构基本完整 ({len(found_sections)} 个关键章节)")
        else:
            score -= 2.0
            comments_parts.append("建议添加标准架构章节")
        
        score = max(0.0, min(10.0, score))
        
        return EvaluationScore(
            category="架构设计",
            score=score,
            comments="; ".join(comments_parts),
        )
    
    def _evaluate_extensibility(self, design_doc: str) -> EvaluationScore:
        """
        评估可扩展性
        
        检查设计是否考虑了未来的扩展需求。
        
        Args:
            design_doc: 设计文档内容
            
        Returns:
            EvaluationScore: 可扩展性评分
        """
        score = 10.0
        comments_parts = []
        
        extensibility_keywords = [
            "扩展", "extend", "插件", "plugin", "配置", "config",
            "接口", "interface", "抽象", "abstract", "继承", "inherit",
            "策略", "strategy", "工厂", "factory", "观察者", "observer",
            "解耦", "decouple", "模块化", "modular",
        ]
        
        design_lower = design_doc.lower()
        matched_keywords = sum(
            1 for keyword in extensibility_keywords
            if keyword.lower() in design_lower
        )
        
        keyword_coverage = matched_keywords / len(extensibility_keywords)
        
        if keyword_coverage >= 0.4:
            comments_parts.append("可扩展性设计良好")
        elif keyword_coverage >= 0.2:
            score -= 2.0
            comments_parts.append("可扩展性设计一般")
        else:
            score -= 4.0
            comments_parts.append("建议加强可扩展性设计")
        
        pattern_keywords = [
            "设计模式", "design pattern", "单例", "singleton",
            "工厂模式", "factory pattern", "策略模式", "strategy pattern",
            "观察者模式", "observer pattern", "装饰器", "decorator",
        ]
        
        pattern_matches = sum(
            1 for keyword in pattern_keywords
            if keyword.lower() in design_lower
        )
        
        if pattern_matches > 0:
            comments_parts.append(f"提及 {pattern_matches} 种设计模式")
        else:
            score -= 1.0
        
        future_keywords = ["未来", "future", "扩展点", "extension point", "预留", "reserve"]
        future_matches = sum(
            1 for keyword in future_keywords
            if keyword.lower() in design_lower
        )
        
        if future_matches > 0:
            comments_parts.append("考虑了未来扩展需求")
        else:
            score -= 0.5
        
        score = max(0.0, min(10.0, score))
        
        return EvaluationScore(
            category="可扩展性",
            score=score,
            comments="; ".join(comments_parts),
        )
    
    def _evaluate_documentation(self, design_doc: str) -> EvaluationScore:
        """
        评估文档完整性
        
        检查设计文档的结构和内容是否完整。
        
        Args:
            design_doc: 设计文档内容
            
        Returns:
            EvaluationScore: 文档完整性评分
        """
        score = 10.0
        comments_parts = []
        
        required_sections = [
            (r'##?\s*概述|##?\s*简介|##?\s*Introduction', "概述/简介"),
            (r'##?\s*目标|##?\s*目的|##?\s*Objective', "目标/目的"),
            (r'##?\s*功能|##?\s*特性|##?\s*Feature', "功能/特性"),
            (r'##?\s*技术|##?\s*实现|##?\s*Technical', "技术/实现"),
        ]
        
        found_sections = []
        for pattern, section_name in required_sections:
            if re.search(pattern, design_doc, re.IGNORECASE):
                found_sections.append(section_name)
        
        section_coverage = len(found_sections) / len(required_sections)
        
        if section_coverage >= 0.75:
            comments_parts.append(f"文档结构完整 ({len(found_sections)}/{len(required_sections)} 关键章节)")
        elif section_coverage >= 0.5:
            score -= 2.0
            comments_parts.append(f"文档结构基本完整 ({len(found_sections)}/{len(required_sections)} 关键章节)")
        else:
            score -= 4.0
            comments_parts.append(f"文档结构不完整 ({len(found_sections)}/{len(required_sections)} 关键章节)")
        
        lines = design_doc.split('\n')
        word_count = sum(len(line.split()) for line in lines)
        
        if word_count < 100:
            score -= 3.0
            comments_parts.append("文档内容较少")
        elif word_count < 300:
            score -= 1.0
            comments_parts.append("文档内容适中")
        else:
            comments_parts.append("文档内容详实")
        
        code_blocks = len(re.findall(r'```', design_doc))
        tables = len(re.findall(r'\|.*\|', design_doc))
        lists = len(re.findall(r'^\s*[-*+]\s', design_doc, re.MULTILINE))
        
        format_score = 0
        if code_blocks > 0:
            format_score += 1
            comments_parts.append("包含代码示例")
        if tables > 0:
            format_score += 1
            comments_parts.append("包含表格")
        if lists > 5:
            format_score += 1
            comments_parts.append("包含列表结构")
        
        if format_score < 2:
            score -= 1.0
        
        score = max(0.0, min(10.0, score))
        
        return EvaluationScore(
            category="文档完整性",
            score=score,
            comments="; ".join(comments_parts),
        )
    
    def _extract_keywords(self, text: str) -> list[str]:
        """
        从文本中提取关键词
        
        Args:
            text: 输入文本
            
        Returns:
            关键词列表
        """
        stop_words = {
            "的", "是", "在", "和", "了", "有", "我", "他", "她", "它",
            "这", "那", "就", "也", "都", "而", "及", "与", "或", "等",
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "need", "dare", "ought", "used", "to", "of", "in",
            "for", "on", "with", "at", "by", "from", "as", "into",
            "through", "during", "before", "after", "above", "below",
            "between", "under", "again", "further", "then", "once",
        }
        
        words = re.findall(r'\b[a-zA-Z]+\b|\b[\u4e00-\u9fff]+\b', text.lower())
        
        keywords = [word for word in words if word not in stop_words and len(word) > 1]
        
        return keywords[:10]
    
    def _generate_code_recommendations(self, report: EvaluationReport) -> list[str]:
        """
        生成代码改进建议
        
        根据评估报告生成具体的代码改进建议。
        
        Args:
            report: 评估报告
            
        Returns:
            改进建议列表
        """
        recommendations = []
        
        for score in report.scores:
            if score.score < self.passing_threshold:
                if score.category == "正确性":
                    recommendations.extend([
                        "修复代码中的语法错误",
                        "检查并修复 AST 解析问题",
                        "确保代码可以正常编译运行",
                    ])
                elif score.category == "测试覆盖率":
                    recommendations.extend([
                        "添加单元测试以提高测试覆盖率",
                        "确保测试覆盖边界条件和异常情况",
                        "考虑使用测试覆盖率工具（如 coverage.py）",
                    ])
                elif score.category == "代码风格":
                    recommendations.extend([
                        "使用代码格式化工具（如 black、autopep8）",
                        "使用代码检查工具（如 flake8、pylint）",
                        "遵循 PEP 8 编码规范",
                    ])
                elif score.category == "错误处理":
                    recommendations.extend([
                        "添加 try-except 块处理潜在异常",
                        "使用具体的异常类型而非裸 except",
                        "考虑添加 finally 块进行资源清理",
                    ])
        
        if not recommendations:
            recommendations.append("代码质量良好，继续保持！")
        
        return recommendations
    
    def _generate_design_recommendations(self, report: EvaluationReport) -> list[str]:
        """
        生成设计改进建议
        
        根据评估报告生成具体的设计改进建议。
        
        Args:
            report: 评估报告
            
        Returns:
            改进建议列表
        """
        recommendations = []
        
        for score in report.scores:
            if score.score < self.passing_threshold:
                if score.category == "需求覆盖":
                    recommendations.extend([
                        "确保设计文档覆盖所有需求",
                        "为每个需求添加对应的设计说明",
                        "建立需求追踪矩阵",
                    ])
                elif score.category == "架构设计":
                    recommendations.extend([
                        "添加系统架构图",
                        "描述模块间的依赖关系",
                        "明确各层次的职责边界",
                    ])
                elif score.category == "可扩展性":
                    recommendations.extend([
                        "考虑使用设计模式提高可扩展性",
                        "定义清晰的扩展点",
                        "使用依赖注入降低耦合",
                    ])
                elif score.category == "文档完整性":
                    recommendations.extend([
                        "添加缺失的文档章节",
                        "补充代码示例和图表",
                        "使用标准文档模板",
                    ])
        
        if not recommendations:
            recommendations.append("设计文档质量良好，继续保持！")
        
        return recommendations
    
    def _generate_code_summary(
        self,
        report: EvaluationReport,
        file_name: str
    ) -> str:
        """
        生成代码评估总结
        
        Args:
            report: 评估报告
            file_name: 文件名
            
        Returns:
            总结文本
        """
        status = "通过" if report.passed else "未通过"
        
        summary = (
            f"代码质量评估完成：{file_name}\n"
            f"总分：{report.total_score:.1f}/10\n"
            f"状态：{status}\n\n"
        )
        
        if report.passed:
            summary += "代码质量达到要求，主要优点：\n"
            for score in report.scores:
                if score.score >= self.passing_threshold:
                    summary += f"- {score.category}：{score.comments}\n"
        else:
            summary += "代码质量需要改进，主要问题：\n"
            for score in report.scores:
                if score.score < self.passing_threshold:
                    summary += f"- {score.category}：{score.comments}\n"
        
        return summary
    
    def _generate_design_summary(self, report: EvaluationReport) -> str:
        """
        生成设计评估总结
        
        Args:
            report: 评估报告
            
        Returns:
            总结文本
        """
        status = "通过" if report.passed else "未通过"
        
        summary = (
            f"设计质量评估完成\n"
            f"总分：{report.total_score:.1f}/10\n"
            f"状态：{status}\n\n"
        )
        
        if report.passed:
            summary += "设计质量达到要求，主要优点：\n"
            for score in report.scores:
                if score.score >= self.passing_threshold:
                    summary += f"- {score.category}：{score.comments}\n"
        else:
            summary += "设计质量需要改进，主要问题：\n"
            for score in report.scores:
                if score.score < self.passing_threshold:
                    summary += f"- {score.category}：{score.comments}\n"
        
        return summary
    
    def _generate_full_summary(
        self,
        code_report: EvaluationReport,
        design_report: EvaluationReport
    ) -> str:
        """
        生成完整评估总结
        
        Args:
            code_report: 代码评估报告
            design_report: 设计评估报告
            
        Returns:
            总结文本
        """
        summary = (
            f"完整评估报告\n"
            f"{'='*50}\n\n"
            f"代码质量评分：{code_report.total_score:.1f}/10 "
            f"({'通过' if code_report.passed else '未通过'})\n"
            f"设计质量评分：{design_report.total_score:.1f}/10 "
            f"({'通过' if design_report.passed else '未通过'})\n\n"
        )
        
        if code_report.passed and design_report.passed:
            summary += "✅ 整体评估通过，代码和设计质量均达到要求。\n"
        elif code_report.passed:
            summary += "⚠️ 代码质量通过，但设计质量需要改进。\n"
        elif design_report.passed:
            summary += "⚠️ 设计质量通过，但代码质量需要改进。\n"
        else:
            summary += "❌ 整体评估未通过，代码和设计质量都需要改进。\n"
        
        return summary


evaluator_agent = EvaluatorAgent()
