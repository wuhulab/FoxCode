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

import asyncio
import importlib.util
import inspect
import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Coroutine

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
    def ok(cls, output: str = "", **kwargs) -> "SkillResult":
        """创建成功结果"""
        return cls(success=True, output=output, **kwargs)
    
    @classmethod
    def fail(cls, error: str, output: str = "") -> "SkillResult":
        """创建失败结果"""
        return cls(success=False, error=error, output=output)
    
    @classmethod
    def redirect(cls, modified_input: str, output: str = "") -> "SkillResult":
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
        
        Returns:
            合并后的提示注入内容
        """
        injections = []
        for skill in self._skills.values():
            injection = skill.get_prompt_injection()
            if injection:
                injections.append(f"### {skill.name}\n{injection}")
        
        if not injections:
            return ""
        
        return "## Available Skills\n\n" + "\n\n".join(injections)
    
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
        
        Args:
            directory: 技能目录
            
        Returns:
            成功加载的技能数量
        """
        if not directory.exists():
            self._logger.warning(f"Skill directory not found: {directory}")
            return 0
        
        loaded = 0
        for skill_file in directory.glob("**/skill.py"):
            try:
                skill = await self._load_skill_from_file(skill_file)
                if skill and self.register(skill):
                    loaded += 1
            except Exception as e:
                self._logger.error(f"Failed to load skill from {skill_file}: {e}")
        
        return loaded
    
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
    ]
    
    for skill in builtin_skills:
        skill_manager.register(skill)
    
    logger.info(f"Registered {len(builtin_skills)} builtin skills")
