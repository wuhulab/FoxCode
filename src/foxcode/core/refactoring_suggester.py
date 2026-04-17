"""
FoxCode 重构建议工具

提供代码异味检测、设计模式建议和重构功能。

主要功能：
- 代码异味检测
- 设计模式建议
- 代码简化建议
- 一键重构功能
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CodeSmellType(str, Enum):
    """代码异味类型"""
    LONG_METHOD = "long_method"               # 过长方法
    LONG_CLASS = "long_class"                 # 过大类
    LONG_PARAMETER_LIST = "long_parameter_list"  # 过长参数列表
    DUPLICATE_CODE = "duplicate_code"         # 重复代码
    DEAD_CODE = "dead_code"                   # 死代码
    MAGIC_NUMBER = "magic_number"             # 魔法数字
    MAGIC_STRING = "magic_string"             # 魔法字符串
    NESTED_IF = "nested_if"                   # 嵌套 if
    NESTED_LOOP = "nested_loop"               # 嵌套循环
    COMPLEX_CONDITION = "complex_condition"   # 复杂条件
    GOD_CLASS = "god_class"                   # 上帝类
    FEATURE_ENVY = "feature_envy"             # 特性嫉妒
    DATA_CLUMP = "data_clump"                 # 数据泥团
    PRIMITIVE_OBSESSION = "primitive_obsession"  # 基本类型偏执
    SHOTGUN_SURGERY = "shotgun_surgery"       # 散弹式修改
    DIVERGENT_CHANGE = "divergent_change"     # 发散式变化
    COMMENTS = "comments"                     # 过多注释
    SPECULATIVE_GENERALITY = "speculative_generality"  # 投机泛化


class DesignPattern(str, Enum):
    """设计模式"""
    SINGLETON = "singleton"           # 单例模式
    FACTORY = "factory"               # 工厂模式
    ABSTRACT_FACTORY = "abstract_factory"  # 抽象工厂
    BUILDER = "builder"               # 建造者模式
    PROTOTYPE = "prototype"           # 原型模式
    ADAPTER = "adapter"               # 适配器模式
    BRIDGE = "bridge"                 # 桥接模式
    COMPOSITE = "composite"           # 组合模式
    DECORATOR = "decorator"           # 装饰器模式
    FACADE = "facade"                 # 外观模式
    FLYWEIGHT = "flyweight"           # 享元模式
    PROXY = "proxy"                   # 代理模式
    CHAIN_OF_RESPONSIBILITY = "chain_of_responsibility"  # 责任链
    COMMAND = "command"               # 命令模式
    ITERATOR = "iterator"             # 迭代器模式
    MEDIATOR = "mediator"             # 中介者模式
    MEMENTO = "memento"               # 备忘录模式
    OBSERVER = "observer"             # 观察者模式
    STATE = "state"                   # 状态模式
    STRATEGY = "strategy"             # 策略模式
    TEMPLATE = "template"             # 模板方法
    VISITOR = "visitor"               # 访问者模式


class Severity(str, Enum):
    """严重程度"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class CodeSmell:
    """
    代码异味
    
    Attributes:
        type: 异味类型
        location: 位置
        description: 描述
        severity: 严重程度
        suggestion: 建议修复
        code_snippet: 代码片段
    """
    type: CodeSmellType
    location: str
    description: str
    severity: Severity = Severity.MEDIUM
    suggestion: str = ""
    code_snippet: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "location": self.location,
            "description": self.description,
            "severity": self.severity.value,
            "suggestion": self.suggestion,
            "code_snippet": self.code_snippet,
        }


@dataclass
class PatternSuggestion:
    """
    设计模式建议
    
    Attributes:
        pattern: 设计模式
        applicability: 适用性描述
        benefits: 好处
        implementation_hint: 实现提示
        confidence: 置信度
    """
    pattern: DesignPattern
    applicability: str = ""
    benefits: list[str] = field(default_factory=list)
    implementation_hint: str = ""
    confidence: float = 0.7

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern": self.pattern.value,
            "applicability": self.applicability,
            "benefits": self.benefits,
            "implementation_hint": self.implementation_hint,
            "confidence": self.confidence,
        }


@dataclass
class RefactoringAction:
    """
    重构动作
    
    Attributes:
        title: 标题
        description: 描述
        original_code: 原始代码
        refactored_code: 重构后代码
        changes: 变更说明
        risks: 风险提示
    """
    title: str
    description: str = ""
    original_code: str = ""
    refactored_code: str = ""
    changes: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "original_code": self.original_code,
            "refactored_code": self.refactored_code,
            "changes": self.changes,
            "risks": self.risks,
        }


@dataclass
class RefactoringReport:
    """
    重构报告
    
    Attributes:
        file_path: 文件路径
        smells: 代码异味列表
        pattern_suggestions: 设计模式建议
        refactoring_actions: 重构动作
        complexity_score: 复杂度评分
        maintainability_index: 可维护性指数
    """
    file_path: str = ""
    smells: list[CodeSmell] = field(default_factory=list)
    pattern_suggestions: list[PatternSuggestion] = field(default_factory=list)
    refactoring_actions: list[RefactoringAction] = field(default_factory=list)
    complexity_score: float = 0.0
    maintainability_index: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "smells": [s.to_dict() for s in self.smells],
            "pattern_suggestions": [p.to_dict() for p in self.pattern_suggestions],
            "refactoring_actions": [a.to_dict() for a in self.refactoring_actions],
            "complexity_score": self.complexity_score,
            "maintainability_index": self.maintainability_index,
        }


class RefactoringConfig(BaseModel):
    """
    重构配置
    
    Attributes:
        max_method_lines: 方法最大行数
        max_class_lines: 类最大行数
        max_parameters: 最大参数数量
        max_nesting_depth: 最大嵌套深度
        max_cyclomatic_complexity: 最大圈复杂度
        detect_patterns: 是否检测设计模式
        auto_refactor: 是否自动重构
    """
    max_method_lines: int = Field(default=30, ge=10)
    max_class_lines: int = Field(default=300, ge=50)
    max_parameters: int = Field(default=5, ge=2)
    max_nesting_depth: int = Field(default=4, ge=2)
    max_cyclomatic_complexity: int = Field(default=10, ge=3)
    detect_patterns: bool = True
    auto_refactor: bool = False


class RefactoringSuggester:
    """
    重构建议工具
    
    提供代码异味检测、设计模式建议和重构功能。
    
    Example:
        >>> suggester = RefactoringSuggester()
        >>> report = suggester.analyze_file(Path("main.py"))
        >>> for smell in report.smells:
        ...     print(f"{smell.type}: {smell.description}")
    """

    def __init__(self, config: RefactoringConfig | None = None):
        """
        初始化重构建议工具
        
        Args:
            config: 重构配置
        """
        self.config = config or RefactoringConfig()
        logger.info("重构建议工具初始化完成")

    def analyze_file(self, file_path: Path) -> RefactoringReport:
        """
        分析文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            重构报告
        """
        report = RefactoringReport(file_path=str(file_path))

        try:
            with open(file_path, encoding="utf-8") as f:
                source = f.read()

            # 解析 AST
            tree = ast.parse(source)

            # 检测代码异味
            report.smells = self._detect_smells(tree, source)

            # 检测设计模式机会
            if self.config.detect_patterns:
                report.pattern_suggestions = self._suggest_patterns(tree, source)

            # 生成重构动作
            report.refactoring_actions = self._generate_refactoring_actions(
                tree, source, report.smells
            )

            # 计算复杂度
            report.complexity_score = self._calculate_complexity(tree)
            report.maintainability_index = self._calculate_maintainability(tree, source)

        except SyntaxError as e:
            report.smells.append(CodeSmell(
                type=CodeSmellType.DEAD_CODE,
                location=f"{file_path}:{e.lineno}",
                description=f"语法错误: {e.msg}",
                severity=Severity.HIGH,
            ))
        except Exception as e:
            logger.error(f"分析文件失败: {e}")

        return report

    def analyze_code(self, code: str) -> RefactoringReport:
        """
        分析代码字符串
        
        Args:
            code: 代码字符串
            
        Returns:
            重构报告
        """
        report = RefactoringReport()

        try:
            tree = ast.parse(code)
            report.smells = self._detect_smells(tree, code)

            if self.config.detect_patterns:
                report.pattern_suggestions = self._suggest_patterns(tree, code)

            report.refactoring_actions = self._generate_refactoring_actions(
                tree, code, report.smells
            )

            report.complexity_score = self._calculate_complexity(tree)
            report.maintainability_index = self._calculate_maintainability(tree, code)

        except SyntaxError as e:
            report.smells.append(CodeSmell(
                type=CodeSmellType.DEAD_CODE,
                location=f"line {e.lineno}",
                description=f"语法错误: {e.msg}",
                severity=Severity.HIGH,
            ))

        return report

    def _detect_smells(self, tree: ast.AST, source: str) -> list[CodeSmell]:
        """检测代码异味"""
        smells = []

        for node in ast.walk(tree):
            # 检测过长方法
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                smells.extend(self._check_long_method(node, source))
                smells.extend(self._check_long_parameters(node))
                smells.extend(self._check_nested_complexity(node))

            # 检测过大类
            if isinstance(node, ast.ClassDef):
                smells.extend(self._check_long_class(node, source))
                smells.extend(self._check_god_class(node))

            # 检测魔法数字
            if isinstance(node, ast.Constant):
                smells.extend(self._check_magic_number(node))

        # 检测重复代码（简化版）
        smells.extend(self._check_duplicate_code(source))

        return smells

    def _check_long_method(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        source: str,
    ) -> list[CodeSmell]:
        """检查过长方法"""
        smells = []

        # 计算方法行数
        start_line = node.lineno
        end_line = node.end_lineno or start_line
        lines = end_line - start_line + 1

        if lines > self.config.max_method_lines:
            smells.append(CodeSmell(
                type=CodeSmellType.LONG_METHOD,
                location=f"line {start_line}",
                description=f"方法 '{node.name}' 有 {lines} 行，超过建议的 {self.config.max_method_lines} 行",
                severity=Severity.MEDIUM if lines < self.config.max_method_lines * 2 else Severity.HIGH,
                suggestion="考虑将方法拆分为更小的、单一职责的方法",
                code_snippet=source.split("\n")[start_line - 1][:100] if source else "",
            ))

        return smells

    def _check_long_parameters(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> list[CodeSmell]:
        """检查过长参数列表"""
        smells = []

        # 计算参数数量
        param_count = len(node.args.args)
        if node.args.vararg:
            param_count += 1
        if node.args.kwarg:
            param_count += 1

        if param_count > self.config.max_parameters:
            smells.append(CodeSmell(
                type=CodeSmellType.LONG_PARAMETER_LIST,
                location=f"line {node.lineno}",
                description=f"方法 '{node.name}' 有 {param_count} 个参数，超过建议的 {self.config.max_parameters} 个",
                severity=Severity.MEDIUM,
                suggestion="考虑使用参数对象或建造者模式",
            ))

        return smells

    def _check_nested_complexity(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> list[CodeSmell]:
        """检查嵌套复杂度"""
        smells = []

        max_depth = self._get_max_nesting_depth(node)

        if max_depth > self.config.max_nesting_depth:
            smells.append(CodeSmell(
                type=CodeSmellType.NESTED_IF,
                location=f"line {node.lineno}",
                description=f"方法 '{node.name}' 有最大嵌套深度 {max_depth}，超过建议的 {self.config.max_nesting_depth}",
                severity=Severity.MEDIUM,
                suggestion="考虑使用提前返回或提取方法来减少嵌套",
            ))

        return smells

    def _get_max_nesting_depth(self, node: ast.AST, current_depth: int = 0) -> int:
        """获取最大嵌套深度"""
        max_depth = current_depth

        nesting_nodes = (ast.If, ast.For, ast.While, ast.With, ast.Try)

        for child in ast.iter_child_nodes(node):
            if isinstance(child, nesting_nodes):
                child_depth = self._get_max_nesting_depth(child, current_depth + 1)
                max_depth = max(max_depth, child_depth)
            else:
                child_depth = self._get_max_nesting_depth(child, current_depth)
                max_depth = max(max_depth, child_depth)

        return max_depth

    def _check_long_class(
        self,
        node: ast.ClassDef,
        source: str,
    ) -> list[CodeSmell]:
        """检查过大类"""
        smells = []

        start_line = node.lineno
        end_line = node.end_lineno or start_line
        lines = end_line - start_line + 1

        if lines > self.config.max_class_lines:
            smells.append(CodeSmell(
                type=CodeSmellType.LONG_CLASS,
                location=f"line {start_line}",
                description=f"类 '{node.name}' 有 {lines} 行，超过建议的 {self.config.max_class_lines} 行",
                severity=Severity.MEDIUM,
                suggestion="考虑将类拆分为更小的、单一职责的类",
            ))

        return smells

    def _check_god_class(self, node: ast.ClassDef) -> list[CodeSmell]:
        """检查上帝类"""
        smells = []

        # 计算方法数量
        methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

        if len(methods) > 15:
            smells.append(CodeSmell(
                type=CodeSmellType.GOD_CLASS,
                location=f"line {node.lineno}",
                description=f"类 '{node.name}' 有 {len(methods)} 个方法，可能承担了过多职责",
                severity=Severity.HIGH,
                suggestion="考虑按职责拆分类，遵循单一职责原则",
            ))

        return smells

    def _check_magic_number(self, node: ast.Constant) -> list[CodeSmell]:
        """检查魔法数字"""
        smells = []

        if isinstance(node.value, (int, float)):
            # 排除常见的非魔法数字
            if node.value not in (0, 1, 2, -1, 0.0, 1.0, 2.0, 100, 1000):
                smells.append(CodeSmell(
                    type=CodeSmellType.MAGIC_NUMBER,
                    location=f"line {node.lineno}",
                    description=f"发现魔法数字: {node.value}",
                    severity=Severity.LOW,
                    suggestion="考虑将数字定义为有意义的常量",
                ))

        return smells

    def _check_duplicate_code(self, source: str) -> list[CodeSmell]:
        """检查重复代码（简化版）"""
        smells = []

        lines = source.split("\n")

        # 简单的重复行检测
        seen_lines = {}
        for i, line in enumerate(lines):
            line = line.strip()
            if len(line) > 20 and not line.startswith("#"):
                if line in seen_lines:
                    smells.append(CodeSmell(
                        type=CodeSmellType.DUPLICATE_CODE,
                        location=f"line {i + 1}",
                        description=f"重复代码行: {line[:50]}...",
                        severity=Severity.LOW,
                        suggestion="考虑提取为公共方法或常量",
                    ))
                else:
                    seen_lines[line] = i + 1

        return smells[:10]  # 限制数量

    def _suggest_patterns(self, tree: ast.AST, source: str) -> list[PatternSuggestion]:
        """建议设计模式"""
        suggestions = []

        for node in ast.walk(tree):
            # 检测单例模式机会
            if isinstance(node, ast.ClassDef):
                if self._could_be_singleton(node):
                    suggestions.append(PatternSuggestion(
                        pattern=DesignPattern.SINGLETON,
                        applicability="类似乎只需要一个实例",
                        benefits=["全局访问点", "延迟初始化", "控制实例数量"],
                        implementation_hint="使用类变量存储实例，私有化构造函数",
                        confidence=0.5,
                    ))

                # 检测工厂模式机会
                if self._could_use_factory(node):
                    suggestions.append(PatternSuggestion(
                        pattern=DesignPattern.FACTORY,
                        applicability="类创建逻辑复杂，可能需要工厂模式",
                        benefits=["封装创建逻辑", "解耦客户端和具体类", "易于扩展"],
                        implementation_hint="创建工厂类，将创建逻辑移入工厂方法",
                        confidence=0.5,
                    ))

                # 检测策略模式机会
                if self._could_use_strategy(node):
                    suggestions.append(PatternSuggestion(
                        pattern=DesignPattern.STRATEGY,
                        applicability="类中有多个条件分支选择不同行为",
                        benefits=["消除条件语句", "易于添加新策略", "运行时切换行为"],
                        implementation_hint="定义策略接口，将不同行为封装为策略类",
                        confidence=0.6,
                    ))

        return suggestions

    def _could_be_singleton(self, node: ast.ClassDef) -> bool:
        """检查是否可能是单例"""
        # 简单启发式：类名包含 Manager, Registry, Config 等
        singleton_keywords = ["manager", "registry", "config", "settings", "cache", "pool"]
        return any(kw in node.name.lower() for kw in singleton_keywords)

    def _could_use_factory(self, node: ast.ClassDef) -> bool:
        """检查是否可能需要工厂模式"""
        # 检查是否有多个创建对象的地方
        create_count = 0
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    create_count += 1

        return create_count > 3

    def _could_use_strategy(self, node: ast.ClassDef) -> bool:
        """检查是否可能需要策略模式"""
        # 检查是否有多个 if-elif 分支
        if_count = 0
        for child in ast.walk(node):
            if isinstance(child, ast.If):
                if_count += 1

        return if_count > 3

    def _generate_refactoring_actions(
        self,
        tree: ast.AST,
        source: str,
        smells: list[CodeSmell],
    ) -> list[RefactoringAction]:
        """生成重构动作"""
        actions = []

        for smell in smells:
            if smell.type == CodeSmellType.LONG_METHOD:
                actions.append(RefactoringAction(
                    title="提取方法",
                    description=f"将 '{smell.location}' 的长方法拆分为更小的方法",
                    changes=["识别方法中的独立功能块", "提取为独立方法", "调用新方法"],
                    risks=["可能需要传递较多参数", "需要确保方法命名清晰"],
                ))

            elif smell.type == CodeSmellType.LONG_PARAMETER_LIST:
                actions.append(RefactoringAction(
                    title="引入参数对象",
                    description="将多个参数封装为参数对象",
                    changes=["创建参数类", "将相关参数移入类中", "使用参数对象替代多个参数"],
                    risks=["需要修改所有调用点", "可能增加类的数量"],
                ))

            elif smell.type == CodeSmellType.NESTED_IF:
                actions.append(RefactoringAction(
                    title="使用提前返回",
                    description="使用提前返回减少嵌套",
                    changes=["反转条件", "提前返回", "减少缩进层级"],
                    risks=["需要仔细处理逻辑顺序"],
                ))

            elif smell.type == CodeSmellType.MAGIC_NUMBER:
                actions.append(RefactoringAction(
                    title="提取常量",
                    description="将魔法数字提取为命名常量",
                    changes=["定义常量", "使用有意义的名称", "替换所有使用处"],
                    risks=["需要确保常量名称有意义"],
                ))

        return actions

    def _calculate_complexity(self, tree: ast.AST) -> float:
        """计算复杂度评分"""
        complexity = 1  # 基础复杂度

        for node in ast.walk(tree):
            # 每个决策点增加复杂度
            if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1
            elif isinstance(node, ast.comprehension):
                complexity += 1
                if node.ifs:
                    complexity += len(node.ifs)

        return complexity

    def _calculate_maintainability(self, tree: ast.AST, source: str) -> float:
        """计算可维护性指数"""
        # 简化的可维护性指数计算
        lines = len(source.split("\n"))
        complexity = self._calculate_complexity(tree)

        # 计算注释率
        comment_lines = sum(1 for line in source.split("\n") if line.strip().startswith("#"))
        comment_ratio = comment_lines / lines if lines > 0 else 0

        # 可维护性指数 (简化版)
        # 范围 0-100，越高越好
        mi = max(0, 100 - (complexity * 2) - (lines / 10) + (comment_ratio * 20))

        return min(100, max(0, mi))

    def suggest_simplification(self, code: str) -> list[RefactoringAction]:
        """
        建议代码简化
        
        Args:
            code: 代码字符串
            
        Returns:
            简化建议列表
        """
        actions = []

        # 检测可以简化的模式
        patterns = [
            (
                r"if\s+(\w+):\s*\n\s*return\s+True\s*\n\s*else:\s*\n\s*return\s+False",
                "return \\1",
                "简化布尔返回",
            ),
            (
                r"if\s+(\w+)\s+is\s+not\s+None:\s*\n\s*return\s+\1\s*\n\s*else:\s*\n\s*return\s+None",
                "return \\1",
                "简化 None 检查返回",
            ),
            (
                r"for\s+(\w+)\s+in\s+(\w+):\s*\n\s*(\w+)\.append\(\1\)",
                "\\3 = list(\\2)",
                "使用 list() 替代循环",
            ),
        ]

        for pattern, replacement, title in patterns:
            if re.search(pattern, code):
                actions.append(RefactoringAction(
                    title=title,
                    description="可以简化的代码模式",
                    original_code=re.search(pattern, code).group(0) if re.search(pattern, code) else "",
                    refactored_code=re.sub(pattern, replacement, code),
                    changes=["使用更简洁的语法"],
                ))

        return actions

    def apply_refactoring(
        self,
        code: str,
        action: RefactoringAction,
    ) -> str:
        """
        应用重构动作
        
        Args:
            code: 原始代码
            action: 重构动作
            
        Returns:
            重构后的代码
        """
        # 简单实现：返回重构后代码
        if action.refactored_code:
            return action.refactored_code
        return code


# 创建默认重构建议工具实例
refactoring_suggester = RefactoringSuggester()
