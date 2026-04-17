"""
FoxCode Skill 技能系统模块

实现可扩展的技能系统，支持动态加载和执行技能
Skill 是一种封装好的能力，可以被 Agent 在特定场景下调用

技能系统特点：
1. 支持动态注册和发现
2. 支持技能提示词注入
3. 支持技能状态管理
4. 支持技能依赖关系
"""

from __future__ import annotations

import importlib.util
import inspect
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SkillState(str, Enum):
    """技能状态"""
    IDLE = "idle"              # 空闲状态
    LOADING = "loading"        # 加载中
    ACTIVE = "active"          # 活跃状态（正在执行）
    ERROR = "error"            # 错误状态
    DISABLED = "disabled"      # 禁用状态


class SkillPriority(str, Enum):
    """技能优先级"""
    CRITICAL = "critical"      # 关键技能，必须成功
    HIGH = "high"              # 高优先级
    NORMAL = "normal"          # 正常优先级
    LOW = "low"                # 低优先级


class SkillTrigger(str, Enum):
    """技能触发方式"""
    MANUAL = "manual"          # 手动触发
    KEYWORD = "keyword"        # 关键词触发
    PATTERN = "pattern"        # 正则模式触发
    AUTO = "auto"              # 自动触发（基于上下文）


@dataclass
class SkillContext:
    """
    技能执行上下文
    
    包含技能执行时需要的所有信息
    """
    user_input: str                                    # 用户输入
    conversation_history: list[dict[str, Any]] = field(default_factory=list)  # 对话历史
    working_dir: Path = field(default_factory=Path.cwd)  # 工作目录
    config: dict[str, Any] = field(default_factory=dict)  # 配置
    metadata: dict[str, Any] = field(default_factory=dict)  # 元数据

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_input": self.user_input,
            "conversation_history": self.conversation_history,
            "working_dir": str(self.working_dir),
            "config": self.config,
            "metadata": self.metadata,
        }


class SkillResult(BaseModel):
    """技能执行结果"""
    success: bool = Field(description="是否成功")
    output: str = Field(default="", description="输出内容")
    error: str | None = Field(default=None, description="错误信息")
    should_continue: bool = Field(default=True, description="是否继续正常对话流程")
    modified_input: str | None = Field(default=None, description="修改后的用户输入")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")

    @classmethod
    def ok(cls, output: str = "", **kwargs) -> SkillResult:
        """创建成功结果"""
        return cls(success=True, output=output, **kwargs)

    @classmethod
    def fail(cls, error: str, output: str = "") -> SkillResult:
        """创建失败结果"""
        return cls(success=False, error=error, output=output)

    @classmethod
    def redirect(cls, modified_input: str, output: str = "") -> SkillResult:
        """创建重定向结果（修改用户输入后继续）"""
        return cls(
            success=True,
            output=output,
            modified_input=modified_input,
            should_continue=True,
        )


class SkillConfig(BaseModel):
    """技能配置"""
    name: str = Field(description="技能名称")
    description: str = Field(default="", description="技能描述")
    version: str = Field(default="1.0.0", description="技能版本")
    author: str = Field(default="", description="作者")
    priority: SkillPriority = Field(default=SkillPriority.NORMAL, description="优先级")
    trigger: SkillTrigger = Field(default=SkillTrigger.MANUAL, description="触发方式")
    keywords: list[str] = Field(default_factory=list, description="触发关键词")
    patterns: list[str] = Field(default_factory=list, description="触发正则模式")
    enabled: bool = Field(default=True, description="是否启用")
    dependencies: list[str] = Field(default_factory=list, description="依赖的其他技能")
    config_schema: dict[str, Any] = Field(default_factory=dict, description="配置 Schema")
    default_config: dict[str, Any] = Field(default_factory=dict, description="默认配置")


class BaseSkill(ABC):
    """
    技能基类
    
    所有技能必须继承此类并实现相应方法
    """

    # 子类必须定义的类属性
    name: str = "base_skill"
    description: str = "基础技能"
    version: str = "1.0.0"
    priority: SkillPriority = SkillPriority.NORMAL
    trigger: SkillTrigger = SkillTrigger.MANUAL
    keywords: list[str] = []
    patterns: list[str] = []
    dependencies: list[str] = []

    def __init__(self, config: dict[str, Any] | None = None):
        """
        初始化技能
        
        Args:
            config: 技能配置
        """
        self._config = config or {}
        self._state = SkillState.IDLE
        self._logger = logging.getLogger(f"foxcode.skill.{self.name}")
        self._compiled_patterns: list[re.Pattern] = []

        # 编译正则模式
        for pattern in self.patterns:
            try:
                self._compiled_patterns.append(re.compile(pattern, re.IGNORECASE))
            except re.error as e:
                self._logger.warning(f"Invalid pattern '{pattern}': {e}")

    @property
    def state(self) -> SkillState:
        return self._state

    @property
    def config(self) -> dict[str, Any]:
        return self._config

    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        return self._config.get(key, default)

    def get_info(self) -> SkillConfig:
        """获取技能信息"""
        return SkillConfig(
            name=self.name,
            description=self.description,
            version=self.version,
            priority=self.priority,
            trigger=self.trigger,
            keywords=self.keywords,
            patterns=self.patterns,
            dependencies=self.dependencies,
        )

    def can_trigger(self, context: SkillContext) -> bool:
        """
        检查是否可以触发技能
        
        Args:
            context: 技能上下文
            
        Returns:
            是否可以触发
        """
        if self._state == SkillState.DISABLED:
            return False

        if self.trigger == SkillTrigger.MANUAL:
            return False

        user_input = context.user_input.lower()

        # 关键词触发
        if self.trigger == SkillTrigger.KEYWORD:
            for keyword in self.keywords:
                if keyword.lower() in user_input:
                    return True
            return False

        # 正则模式触发
        if self.trigger == SkillTrigger.PATTERN:
            for pattern in self._compiled_patterns:
                if pattern.search(user_input):
                    return True
            return False

        # 自动触发（子类可重写）
        if self.trigger == SkillTrigger.AUTO:
            return self._auto_trigger_check(context)

        return False

    def _auto_trigger_check(self, context: SkillContext) -> bool:
        """
        自动触发检查（子类可重写）
        
        Args:
            context: 技能上下文
            
        Returns:
            是否应该触发
        """
        return False

    async def initialize(self) -> None:
        """
        初始化技能（子类可重写）
        
        用于加载资源、建立连接等初始化操作
        """
        self._state = SkillState.IDLE
        self._logger.debug(f"Skill {self.name} initialized")

    async def cleanup(self) -> None:
        """
        清理技能资源（子类可重写）
        
        用于释放资源、关闭连接等清理操作
        """
        self._state = SkillState.IDLE
        self._logger.debug(f"Skill {self.name} cleaned up")

    @abstractmethod
    async def execute(self, context: SkillContext) -> SkillResult:
        """
        执行技能（子类必须实现）
        
        Args:
            context: 技能上下文
            
        Returns:
            执行结果
        """
        pass

    def get_prompt_injection(self) -> str | None:
        """
        获取要注入到系统提示的内容（子类可重写）
        
        Returns:
            要注入的提示内容，None 表示不注入
        """
        return None

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """
        获取技能提供的工具定义（子类可重写）
        
        Returns:
            工具定义列表
        """
        return []


class SkillManager:
    """
    技能管理器
    
    管理所有注册的技能，处理技能发现、加载和执行
    """

    def __init__(self):
        self._skills: dict[str, BaseSkill] = {}
        self._skill_configs: dict[str, dict[str, Any]] = {}
        self._logger = logging.getLogger("foxcode.skill.manager")

    def register(self, skill: BaseSkill, config: dict[str, Any] | None = None) -> bool:
        """
        注册技能
        
        Args:
            skill: 技能实例
            config: 技能配置
            
        Returns:
            是否成功注册
        """
        if skill.name in self._skills:
            self._logger.warning(f"Skill {skill.name} already registered")
            return False

        # 应用配置
        if config:
            skill._config = {**skill._config, **config}

        self._skills[skill.name] = skill
        self._skill_configs[skill.name] = config or {}

        self._logger.info(f"Registered skill: {skill.name}")
        return True

    def unregister(self, name: str) -> bool:
        """
        注销技能
        
        Args:
            name: 技能名称
            
        Returns:
            是否成功注销
        """
        if name not in self._skills:
            return False

        skill = self._skills.pop(name)
        self._skill_configs.pop(name, None)

        self._logger.info(f"Unregistered skill: {name}")
        return True

    def get_skill(self, name: str) -> BaseSkill | None:
        """获取技能实例"""
        return self._skills.get(name)

    def list_skills(self) -> list[SkillConfig]:
        """列出所有技能信息"""
        return [skill.get_info() for skill in self._skills.values()]

    def list_enabled_skills(self) -> list[BaseSkill]:
        """列出所有启用的技能"""
        return [
            skill for skill in self._skills.values()
            if skill.state != SkillState.DISABLED
        ]

    async def initialize_all(self) -> None:
        """初始化所有技能"""
        for skill in self._skills.values():
            try:
                await skill.initialize()
            except Exception as e:
                self._logger.error(f"Failed to initialize skill {skill.name}: {e}")
                skill._state = SkillState.ERROR

    async def cleanup_all(self) -> None:
        """清理所有技能"""
        for skill in self._skills.values():
            try:
                await skill.cleanup()
            except Exception as e:
                self._logger.error(f"Failed to cleanup skill {skill.name}: {e}")

    def find_triggered_skills(self, context: SkillContext) -> list[BaseSkill]:
        """
        查找所有被触发的技能
        
        Args:
            context: 技能上下文
            
        Returns:
            被触发的技能列表（按优先级排序）
        """
        triggered = []
        for skill in self._skills.values():
            if skill.can_trigger(context):
                triggered.append(skill)

        # 按优先级排序
        priority_order = {
            SkillPriority.CRITICAL: 0,
            SkillPriority.HIGH: 1,
            SkillPriority.NORMAL: 2,
            SkillPriority.LOW: 3,
        }
        triggered.sort(key=lambda s: priority_order.get(s.priority, 2))

        return triggered

    async def execute_skill(self, name: str, context: SkillContext) -> SkillResult:
        """
        执行指定技能
        
        Args:
            name: 技能名称
            context: 技能上下文
            
        Returns:
            执行结果
        """
        skill = self._skills.get(name)
        if not skill:
            return SkillResult.fail(f"Skill not found: {name}")

        if skill.state == SkillState.DISABLED:
            return SkillResult.fail(f"Skill {name} is disabled")

        try:
            skill._state = SkillState.ACTIVE
            result = await skill.execute(context)
            skill._state = SkillState.IDLE
            return result

        except Exception as e:
            skill._state = SkillState.ERROR
            self._logger.error(f"Skill {name} execution failed: {e}")
            return SkillResult.fail(str(e))

    async def execute_triggered_skills(self, context: SkillContext) -> list[tuple[str, SkillResult]]:
        """
        执行所有被触发的技能
        
        Args:
            context: 技能上下文
            
        Returns:
            (技能名称, 执行结果) 列表
        """
        results = []
        triggered = self.find_triggered_skills(context)

        for skill in triggered:
            result = await self.execute_skill(skill.name, context)
            results.append((skill.name, result))

            # 如果技能返回不继续，停止执行后续技能
            if not result.should_continue:
                break

        return results

    def get_prompt_injections(self) -> str:
        """
        获取所有技能的提示注入
        
        在开头列出所有可用的 skills 文件名，让 AI 决定要调用什么
        
        Returns:
            合并后的提示注入内容
        """
        if not self._skills:
            return ""

        lines = []
        lines.append("## Available Skills")
        lines.append("")

        # 在开头列出所有可用的 skills 文件名
        lines.append("**可用的 Skills (使用 Skill 工具调用):**")
        lines.append("")

        for skill in self._skills.values():
            status = "✅" if skill.state != SkillState.DISABLED else "❌"
            desc = skill.description[:60] if skill.description else "无描述"
            lines.append(f"- {status} `{skill.name}`: {desc}")

        lines.append("")
        lines.append("**调用方式:** 使用 Skill 工具，传入 skill 名称即可激活对应的技能。")
        lines.append("**示例:** `Skill(name=\"error-solver\")` 将激活错误解决技能。")
        lines.append("")

        # 添加每个 skill 的详细提示
        injections = []
        for skill in self._skills.values():
            injection = skill.get_prompt_injection()
            if injection:
                injections.append(f"### {skill.name}\n{injection}")

        if injections:
            lines.append("---")
            lines.append("")
            lines.append("## Skills 详细说明")
            lines.append("")
            lines.append("\n\n".join(injections))

        return "\n".join(lines)

    def get_skill_names(self) -> list[str]:
        """
        获取所有已注册的 skill 名称列表
        
        Returns:
            skill 名称列表
        """
        return list(self._skills.keys())

    def get_enabled_skill_names(self) -> list[str]:
        """
        获取所有启用的 skill 名称列表
        
        Returns:
            启用的 skill 名称列表
        """
        return [
            name for name, skill in self._skills.items()
            if skill.state != SkillState.DISABLED
        ]

    def get_all_tool_definitions(self) -> list[dict[str, Any]]:
        """
        获取所有技能提供的工具定义
        
        Returns:
            工具定义列表
        """
        tools = []
        for skill in self._skills.values():
            tools.extend(skill.get_tool_definitions())
        return tools

    async def load_from_directory(self, directory: Path) -> int:
        """
        从目录加载技能
        
        支持 Python skill 文件 (.py) 和 Markdown skill 文件 (.md)
        
        Args:
            directory: 技能目录
            
        Returns:
            成功加载的技能数量
        """
        if not directory.exists():
            self._logger.warning(f"Skill directory not found: {directory}")
            return 0

        loaded = 0

        # 加载 Python skill 文件
        for skill_file in directory.glob("**/skill.py"):
            try:
                skill = await self._load_skill_from_file(skill_file)
                if skill and self.register(skill):
                    loaded += 1
            except Exception as e:
                self._logger.error(f"Failed to load skill from {skill_file}: {e}")

        # 加载 Markdown skill 文件 (.foxcode/skills/**/*.md)
        for skill_file in directory.glob("**/*.md"):
            try:
                skill = self._load_skill_from_markdown(skill_file)
                if skill and self.register(skill):
                    loaded += 1
            except Exception as e:
                self._logger.error(f"Failed to load skill from markdown {skill_file}: {e}")

        return loaded

    def _load_skill_from_markdown(self, file_path: Path) -> BaseSkill | None:
        """
        从 Markdown 文件加载技能
        
        Markdown skill 文件格式:
        - 文件名作为 skill 名称
        - 第一行标题 (# xxx) 作为 skill 名称（可选）
        - 内容作为 skill 提示注入
        
        Args:
            file_path: Markdown 文件路径
            
        Returns:
            技能实例
        """
        try:
            content = file_path.read_text(encoding="utf-8")

            # 提取名称
            name = file_path.stem

            # 尝试从第一行标题提取名称
            lines = content.split("\n")
            for line in lines[:5]:
                if line.startswith("# "):
                    name = line[2:].strip()
                    break

            # 提取描述（第一个非标题非空行）
            description = ""
            for line in lines[1:10]:
                line = line.strip()
                if line and not line.startswith("#"):
                    description = line[:200]
                    break

            # 创建动态 skill 类
            class MarkdownSkill(BaseSkill):
                pass

            MarkdownSkill.name = name.lower().replace(" ", "-").replace("_", "-")
            MarkdownSkill.description = description or f"Skill from {file_path.name}"
            MarkdownSkill.version = "1.0.0"
            MarkdownSkill.priority = SkillPriority.NORMAL
            MarkdownSkill.trigger = SkillTrigger.MANUAL

            # 存储原始内容
            MarkdownSkill._markdown_content = content
            MarkdownSkill._markdown_file = file_path

            def get_prompt_injection(self) -> str | None:
                return self._markdown_content

            async def execute(self, context: SkillContext) -> SkillResult:
                return SkillResult.ok(f"Skill '{self.name}' activated from {self._markdown_file}")

            MarkdownSkill.get_prompt_injection = get_prompt_injection
            MarkdownSkill.execute = execute

            return MarkdownSkill()

        except Exception as e:
            self._logger.error(f"Failed to parse markdown skill {file_path}: {e}")
            return None

    async def _load_skill_from_file(self, file_path: Path) -> BaseSkill | None:
        """
        从文件加载技能
        
        Args:
            file_path: 技能文件路径
            
        Returns:
            技能实例
        """
        # 动态导入模块
        spec = importlib.util.spec_from_file_location("skill_module", file_path)
        if not spec or not spec.loader:
            return None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # 查找 BaseSkill 的子类
        for name in dir(module):
            obj = getattr(module, name)
            if (
                inspect.isclass(obj)
                and issubclass(obj, BaseSkill)
                and obj is not BaseSkill
            ):
                return obj()

        return None

    def enable_skill(self, name: str) -> bool:
        """启用技能"""
        skill = self._skills.get(name)
        if skill:
            skill._state = SkillState.IDLE
            return True
        return False

    def disable_skill(self, name: str) -> bool:
        """禁用技能"""
        skill = self._skills.get(name)
        if skill:
            skill._state = SkillState.DISABLED
            return True
        return False


# ============================================================
# 内置技能示例
# ============================================================

class ErrorSolverSkill(BaseSkill):
    """
    错误解决技能
    
    分析和修复编程错误，支持多种编程语言
    """

    name = "error-solver"
    description = "分析和修复编程错误，支持多种编程语言"
    version = "1.0.0"
    priority = SkillPriority.HIGH
    trigger = SkillTrigger.KEYWORD
    keywords = ["error", "错误", "bug", "fix", "修复", "debug", "调试", "exception", "异常"]

    def get_prompt_injection(self) -> str | None:
        return """
当用户遇到错误时，请按以下步骤处理：
1. 分析错误信息和堆栈跟踪
2. 定位错误原因
3. 提供修复建议
4. 如果需要，提供修复代码

常见错误类型：
- 编译错误：语法错误、类型错误
- 运行时错误：空指针、数组越界
- 逻辑错误：条件判断错误、循环问题
"""

    async def execute(self, context: SkillContext) -> SkillResult:
        # 此技能主要通过提示注入工作
        # 实际的错误分析和修复由 Agent 完成
        return SkillResult.ok("Error solver skill activated")


class SkillCreatorSkill(BaseSkill):
    """
    技能创建技能
    
    用于创建新的技能
    """

    name = "skill-creator"
    description = "创建新的技能，支持生成技能模板和配置"
    version = "1.0.0"
    priority = SkillPriority.NORMAL
    trigger = SkillTrigger.KEYWORD
    keywords = ["create skill", "创建技能", "new skill", "新建技能"]

    def get_prompt_injection(self) -> str | None:
        return """
当用户想要创建新技能时，请帮助用户：
1. 确定技能名称和描述
2. 定义触发条件（关键词、模式等）
3. 实现技能逻辑
4. 生成技能配置

技能模板结构：
```python
from foxcode.core.skill import BaseSkill, SkillContext, SkillResult, SkillPriority, SkillTrigger

class MySkill(BaseSkill):
    name = "my-skill"
    description = "技能描述"
    priority = SkillPriority.NORMAL
    trigger = SkillTrigger.KEYWORD
    keywords = ["关键词"]
    
    async def execute(self, context: SkillContext) -> SkillResult:
        # 实现技能逻辑
        return SkillResult.ok("执行结果")
```
"""

    async def execute(self, context: SkillContext) -> SkillResult:
        return SkillResult.ok("Skill creator activated")


class CodeReviewSkill(BaseSkill):
    """
    代码审查技能
    
    提供代码审查和质量检查功能
    """

    name = "code-review"
    description = "代码审查和质量检查"
    version = "1.0.0"
    priority = SkillPriority.NORMAL
    trigger = SkillTrigger.KEYWORD
    keywords = ["review", "审查", "code review", "代码审查", "check code", "检查代码"]

    def get_prompt_injection(self) -> str | None:
        return """
当用户请求代码审查时，请检查以下方面：
1. 代码风格和格式
2. 潜在的 bug 和错误
3. 性能问题
4. 安全漏洞
5. 可维护性
6. 测试覆盖率

提供具体的改进建议和示例代码。
"""

    async def execute(self, context: SkillContext) -> SkillResult:
        return SkillResult.ok("Code review skill activated")


class DocumentationSkill(BaseSkill):
    """
    文档生成技能
    
    自动生成代码文档
    """

    name = "documentation"
    description = "生成代码文档和注释"
    version = "1.0.0"
    priority = SkillPriority.LOW
    trigger = SkillTrigger.KEYWORD
    keywords = ["document", "文档", "docstring", "注释", "comment", "generate docs"]

    def get_prompt_injection(self) -> str | None:
        return """
当用户需要生成文档时，请：
1. 分析代码结构和功能
2. 生成清晰的文档字符串
3. 添加必要的注释
4. 生成 README 或 API 文档

文档格式：
- Python: Google 或 NumPy 风格的 docstring
- JavaScript: JSDoc 格式
- 通用: Markdown 格式
"""

    async def execute(self, context: SkillContext) -> SkillResult:
        return SkillResult.ok("Documentation skill activated")


class RefactoringSkill(BaseSkill):
    """
    重构技能
    
    提供代码重构建议和实现
    """

    name = "refactoring"
    description = "代码重构和优化"
    version = "1.0.0"
    priority = SkillPriority.NORMAL
    trigger = SkillTrigger.KEYWORD
    keywords = ["refactor", "重构", "optimize", "优化", "clean code", "整洁代码"]

    def get_prompt_injection(self) -> str | None:
        return """
当用户请求重构时，请考虑：
1. 代码重复（DRY 原则）
2. 函数长度和复杂度
3. 命名规范
4. 设计模式应用
5. 依赖注入
6. 接口隔离

提供重构前后的对比和改进说明。
"""

    async def execute(self, context: SkillContext) -> SkillResult:
        return SkillResult.ok("Refactoring skill activated")


class TestingSkill(BaseSkill):
    """
    测试技能
    
    生成和运行测试用例
    """

    name = "testing"
    description = "生成和运行测试用例"
    version = "1.0.0"
    priority = SkillPriority.NORMAL
    trigger = SkillTrigger.KEYWORD
    keywords = ["test", "测试", "unit test", "单元测试", "pytest", "jest"]

    def get_prompt_injection(self) -> str | None:
        return """
        当用户需要测试时，请：
        1. 分析代码功能和边界条件
        2. 生成单元测试用例
        3. 考虑边缘情况和异常处理
        4. 提供测试覆盖率建议

        测试框架：
        - Python: pytest, unittest
        - JavaScript: Jest, Mocha
        - Java: JUnit
        """

    async def execute(self, context: SkillContext) -> SkillResult:
        return SkillResult.ok("Testing skill activated")


class RuleBasedSkillGenerator(BaseSkill):
    """
    规则基于技能生成器
    
    根据规则文件生成技能，触发方式为查看规则文件生成 skills
    
    功能：
    - 读取规则文件 S:/shunxcode/.trae/rules/rule.md
    - 分析规则内容，提取各个章节
    - 为每个章节生成一个独立的技能
    - 生成一个综合的 UOP 代码规范技能
    - 自动注册生成的技能到技能管理器
    
    使用方法：
    1. 确保规则文件 S:/shunxcode/.trae/rules/rule.md 存在且包含有效的规则内容
    2. 在聊天中输入关键词："generate skill"、"生成技能"、"rule based skill" 或 "基于规则的技能"
    3. 或者使用 Skill 工具调用：Skill(name="rule-based-skill-generator")
    4. 技能生成器会自动生成并注册技能
    5. 生成的技能可以通过 Skill 工具调用，例如：Skill(name="rule-核心原则")
    
    生成的技能：
    - rule-核心原则：基于核心原则章节的技能
    - rule-命名规则：基于命名规则章节的技能
    - rule-函数规则：基于函数规则章节的技能
    - rule-注释规则：基于注释规则章节的技能
    - rule-文件规则：基于文件规则章节的技能
    - rule-视觉规则：基于视觉规则章节的技能
    - rule-复用规则：基于复用规则章节的技能
    - uop-coding-standard：综合所有规则的技能
    """

    name = "rule-based-skill-generator"
    description = "根据规则文件生成技能，符合 doge-code 规定格式"
    version = "1.0.0"
    priority = SkillPriority.HIGH
    trigger = SkillTrigger.KEYWORD
    keywords = ["generate skill", "生成技能", "rule based skill", "基于规则的技能"]

    def get_prompt_injection(self) -> str | None:
        return """
        当用户需要根据规则文件生成技能时，请：
        1. 读取规则文件 S:/shunxcode/.trae/rules/rule.md
        2. 分析规则内容，提取关键信息
        3. 根据 doge-code 的技能格式生成技能
        4. 注册生成的技能到技能管理器
        5. 提供生成技能的摘要和使用方法
        """

    async def execute(self, context: SkillContext) -> SkillResult:
        try:
            # 读取规则文件
            rule_file = Path("S:/shunxcode/.trae/rules/rule.md")
            if not rule_file.exists():
                return SkillResult.fail("规则文件不存在: S:/shunxcode/.trae/rules/rule.md")

            content = rule_file.read_text(encoding="utf-8")
            
            # 解析规则内容
            rules = self._parse_rules(content)
            
            # 生成技能
            generated_skills = await self._generate_skills(rules, content)
            
            # 注册技能
            for skill in generated_skills:
                skill_manager.register(skill)
            
            return SkillResult.ok(f"成功生成并注册了 {len(generated_skills)} 个技能")
        except Exception as e:
            return SkillResult.fail(f"生成技能失败: {str(e)}")

    def _parse_rules(self, content: str) -> dict[str, str]:
        """
        解析规则文件内容
        
        Args:
            content: 规则文件内容
            
        Returns:
            解析后的规则字典
        """
        rules = {}
        lines = content.split("\n")
        current_section = ""
        
        for line in lines:
            line = line.strip()
            if line.startswith("## "):
                current_section = line[3:].strip()
                rules[current_section] = ""
            elif current_section and line:
                rules[current_section] += line + "\n"
        
        return rules

    async def _generate_skills(self, rules: dict[str, str], content: str) -> list[BaseSkill]:
        """
        根据规则生成技能
        
        Args:
            rules: 解析后的规则字典
            content: 规则文件完整内容
            
        Returns:
            生成的技能列表
        """
        skills = []
        
        # 为每个规则部分生成一个技能
        for section, section_content in rules.items():
            skill_name = section.lower().replace(" ", "-")
            skill_description = f"基于规则 '{section}' 的技能"
            
            # 创建动态技能类
            class RuleBasedSkill(BaseSkill):
                _rule_section = section
                _rule_content = section_content
                
                def get_prompt_injection(self) -> str | None:
                    return f"""
                    # {self._rule_section}
                    
                    {self._rule_content}
                    """
                
                async def execute(self, context: SkillContext) -> SkillResult:
                    return SkillResult.ok(f"规则 '{self._rule_section}' 技能激活")
            
            RuleBasedSkill.name = f"rule-{skill_name}"
            RuleBasedSkill.description = skill_description
            RuleBasedSkill.version = "1.0.0"
            RuleBasedSkill.priority = SkillPriority.NORMAL
            RuleBasedSkill.trigger = SkillTrigger.MANUAL
            
            skills.append(RuleBasedSkill())
        
        # 生成一个综合规则技能
        class UOPSkill(BaseSkill):
            name = "uop-coding-standard"
            description = "面向理解编程（UOP）代码生成规范技能"
            version = "1.0.0"
            priority = SkillPriority.HIGH
            trigger = SkillTrigger.KEYWORD
            keywords = ["uop", "面向理解编程", "coding standard", "代码规范"]
            
            def get_prompt_injection(self) -> str | None:
                return f"""
                # 面向理解编程（UOP）代码生成规范
                
                {content}
                """
            
            async def execute(self, context: SkillContext) -> SkillResult:
                return SkillResult.ok("UOP 代码规范技能激活")
        
        skills.append(UOPSkill())
        
        return skills


# 全局技能管理器实例
skill_manager = SkillManager()


def register_builtin_skills() -> None:
    """注册内置技能"""
    builtin_skills = [
        ErrorSolverSkill(),
        SkillCreatorSkill(),
        CodeReviewSkill(),
        DocumentationSkill(),
        RefactoringSkill(),
        TestingSkill(),
        RuleBasedSkillGenerator(),
    ]

    for skill in builtin_skills:
        skill_manager.register(skill)

    logger.info(f"Registered {len(builtin_skills)} builtin skills")
