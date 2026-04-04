"""
FoxCode 配置模块

管理应用程序配置，支持多种配置来源：
- 环境变量
- 配置文件 (.foxcode.toml, foxcode.toml)
- 命令行参数
"""

from __future__ import annotations

import os
import sys
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import ClassVar

from foxcode.core.work_mode_config import WorkModeConfig

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


class ModelProvider(str, Enum):
    """支持的 AI 模型提供者"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    STEP = "step"
    LOCAL = "local"
    CUSTOM = "custom"


class RunMode(str, Enum):
    """运行模式"""
    DEFAULT = "default"          # 默认模式，需要确认
    YOLO = "yolo"                # 自动执行所有操作
    ACCEPT_EDITS = "accept_edits" # 自动接受文件编辑
    PLAN = "plan"                # 规划模式，只读


class AgentRole(str, Enum):
    """
    代理角色枚举
    
    定义多代理系统中各代理的角色类型，用于实现代理间的协作和切换机制。
    每个角色负责特定的任务领域，通过 handoff 机制进行代理间的任务传递。
    
    Attributes:
        PLANNER: 规划器代理 - 负责分析需求、制定计划和分解任务
        GENERATOR: 生成器代理 - 负责根据计划生成代码和实现功能
        EVALUATOR: 评估器代理 - 负责评估生成结果的质量和正确性
    """
    PLANNER = "planner"      # 规划器代理：负责需求分析和任务规划
    GENERATOR = "generator"  # 生成器代理：负责代码生成和功能实现
    EVALUATOR = "evaluator"  # 评估器代理：负责质量评估和结果验证


class ModelConfig(BaseModel):
    """模型配置"""
    model_config = ConfigDict(protected_namespaces=())
    
    provider: ModelProvider = ModelProvider.OPENAI
    model_name: str = "gpt-4o"
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)
    timeout: int = Field(default=120, ge=1)
    
    # 模型别名映射（类变量）
    MODEL_ALIASES: ClassVar[dict[str, tuple[ModelProvider, str]]] = {
        "claude": (ModelProvider.ANTHROPIC, "claude-sonnet-4-20250514"),
        "claude-sonnet": (ModelProvider.ANTHROPIC, "claude-sonnet-4-20250514"),
        "claude-opus": (ModelProvider.ANTHROPIC, "claude-opus-4-20250514"),
        "gpt-4": (ModelProvider.OPENAI, "gpt-4o"),
        "gpt-4o": (ModelProvider.OPENAI, "gpt-4o"),
        "gpt-4-turbo": (ModelProvider.OPENAI, "gpt-4-turbo"),
        "gpt-3.5": (ModelProvider.OPENAI, "gpt-3.5-turbo"),
        "deepseek": (ModelProvider.DEEPSEEK, "deepseek-chat"),
        "deepseek-coder": (ModelProvider.DEEPSEEK, "deepseek-coder"),
        "step": (ModelProvider.STEP, "step-1-8k"),
        "step-1": (ModelProvider.STEP, "step-1-8k"),
        "step-1-8k": (ModelProvider.STEP, "step-1-8k"),
        "step-1-32k": (ModelProvider.STEP, "step-1-32k"),
        "step-2": (ModelProvider.STEP, "step-2-16k"),
        "step-3": (ModelProvider.STEP, "step-3.5-flash"),
        "step-3.5": (ModelProvider.STEP, "step-3.5-flash"),
        "step-3.5-flash": (ModelProvider.STEP, "step-3.5-flash"),
    }
    
    @field_validator("model_name", mode="before")
    @classmethod
    def resolve_model_alias(cls, v: str) -> str:
        """解析模型别名"""
        if v in cls.MODEL_ALIASES:
            return cls.MODEL_ALIASES[v][1]
        return v
    
    def get_effective_api_key(self) -> str:
        """获取有效的 API Key"""
        if self.api_key:
            return self.api_key
        
        # 从环境变量获取
        env_keys = {
            ModelProvider.OPENAI: "OPENAI_API_KEY",
            ModelProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
            ModelProvider.DEEPSEEK: "DEEPSEEK_API_KEY",
            ModelProvider.STEP: "STEP_API_KEY",
        }
        
        env_key = env_keys.get(self.provider)
        if env_key:
            key = os.environ.get(env_key)
            if key:
                return key
        
        raise ValueError(f"未找到 {self.provider.value} 的 API Key，请设置环境变量或配置")


class PlaywrightConfig(BaseModel):
    """Playwright 浏览器配置"""
    browser_type: str = Field(default="chromium", description="浏览器类型: chromium, firefox, webkit")
    headless: bool = Field(default=True, description="是否使用无头模式")
    viewport_width: int = Field(default=1280, ge=320, description="视口宽度")
    viewport_height: int = Field(default=720, ge=240, description="视口高度")
    default_timeout: int = Field(default=30000, ge=1000, description="默认超时时间（毫秒）")
    navigation_timeout: int = Field(default=30000, ge=1000, description="导航超时时间（毫秒）")
    screenshot_dir: str = Field(default=".foxcode/screenshots", description="截图保存目录")
    enable_playwright: bool = Field(default=True, description="是否启用 Playwright 工具")


class SandboxMode(str, Enum):
    """沙箱模式"""
    DISABLED = "disabled"       # 禁用沙箱
    BLACKLIST = "blacklist"     # 黑名单模式（默认，阻止危险命令）
    WHITELIST = "whitelist"     # 白名单模式（只允许白名单命令）


class SandboxConfigModel(BaseModel):
    """安全沙箱配置"""
    enabled: bool = Field(default=True, description="是否启用沙箱")
    mode: SandboxMode = Field(default=SandboxMode.BLACKLIST, description="沙箱模式: disabled, blacklist, whitelist")
    allow_path_traversal: bool = Field(default=False, description="是否允许路径穿越")
    max_command_length: int = Field(default=10000, ge=100, description="最大命令长度")
    allowed_commands: list[str] = Field(
        default_factory=lambda: [
            "ls", "dir", "cat", "type", "echo", "pwd", "cd",
            "git", "npm", "node", "python", "python3", "pip", "pip3",
            "cargo", "rustc", "go", "java", "javac", "mvn", "gradle",
            "make", "cmake", "gcc", "g++", "clang", "clang++",
            "docker", "docker-compose",
            "pytest", "jest", "mocha", "unittest",
            "curl", "wget",
            "tar", "zip", "unzip", "gzip", "gunzip",
            "grep", "find", "sed", "awk",
            "touch", "mkdir", "cp", "mv",
        ],
        description="白名单命令列表（白名单模式下生效）"
    )
    blocked_commands: list[str] = Field(
        default_factory=list,
        description="黑名单命令列表（黑名单模式下生效，为空则使用默认黑名单）"
    )
    
    @field_validator("allowed_commands", "blocked_commands", mode="before")
    @classmethod
    def validate_commands(cls, v: list[str] | None) -> list[str]:
        """验证命令列表格式，防止命令注入"""
        if v is None:
            return []
        
        validated = []
        dangerous_chars = [';', '|', '&', '$', '`', '(', ')', '{', '}', '<', '>', '\n', '\r']
        
        for cmd in v:
            # 跳过空值
            if not cmd or not isinstance(cmd, str):
                continue
            
            # 去除首尾空白
            cmd = cmd.strip()
            if not cmd:
                continue
            
            # 检查危险字符
            if any(char in cmd for char in dangerous_chars):
                continue  # 跳过包含危险字符的命令
            
            # 只允许字母、数字、连字符、下划线和点号
            if not all(c.isalnum() or c in '-_.' for c in cmd):
                continue
            
            # 长度限制
            if len(cmd) > 50:
                continue
            
            validated.append(cmd.lower())
        
        return validated


class ToolConfig(BaseModel):
    """工具配置"""
    enable_file_ops: bool = True
    enable_shell: bool = True
    enable_web_search: bool = False
    enable_code_execution: bool = True
    shell_timeout: int = Field(default=300, ge=1)
    max_file_size: int = Field(default=10 * 1024 * 1024)  # 10MB
    allowed_extensions: list[str] = Field(default_factory=lambda: [
        ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs",
        ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
        ".kt", ".scala", ".lua", ".r", ".sql", ".sh", ".bash",
        ".json", ".yaml", ".yml", ".toml", ".xml", ".html", ".css",
        ".md", ".txt", ".rst", ".ini", ".cfg", ".env", ".gitignore",
    ])
    
    @field_validator("allowed_extensions", mode="before")
    @classmethod
    def validate_extensions(cls, v: list[str] | None) -> list[str]:
        """验证文件扩展名格式"""
        if v is None:
            return []
        
        validated = []
        for ext in v:
            # 跳过空值
            if not ext or not isinstance(ext, str):
                continue
            
            # 确保以 '.' 开头（对于没有点的扩展名自动添加）
            if not ext.startswith('.'):
                ext = '.' + ext
            
            # 验证扩展名只包含有效字符（字母、数字、连字符、下划线）
            ext_part = ext[1:]  # 去掉点号
            if not ext_part:
                continue  # 跳过只有点号的扩展名
            
            if not all(c.isalnum() or c in '-_' for c in ext_part):
                continue  # 跳过包含无效字符的扩展名
            
            validated.append(ext.lower())
        
        return validated


class UIConfig(BaseModel):
    """UI 配置"""
    theme: str = "dark"
    show_token_usage: bool = True
    show_timing: bool = True
    compact_mode: bool = False
    syntax_highlight: bool = True
    mouse_support: bool = True


class EvaluatorCriteriaConfig(BaseModel):
    """
    评估器评估标准配置
    
    定义评估器代理在评估代码质量时使用的各项标准及其权重。
    所有权重值应在 0.0 到 1.0 之间，评估结果为加权平均分（满分 10 分）。
    
    Attributes:
        code_correctness_weight: 代码正确性权重 - 评估代码是否正确实现功能
        test_coverage_weight: 测试覆盖率权重 - 评估测试用例的覆盖程度
        code_style_weight: 代码风格权重 - 评估代码风格和可读性
        error_handling_weight: 错误处理权重 - 评估异常处理和边界情况
        passing_threshold: 通过阈值 - 评估通过的最低分数（满分10分）
        design_requirements_weight: 需求覆盖权重 - 评估是否满足设计需求
        architecture_weight: 架构合理性权重 - 评估架构设计的合理性
        extensibility_weight: 可扩展性权重 - 评估代码的可扩展能力
        documentation_weight: 文档完整性权重 - 评估文档的完整程度
    """
    code_correctness_weight: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="代码正确性权重"
    )
    test_coverage_weight: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="测试覆盖率权重"
    )
    code_style_weight: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="代码风格权重"
    )
    error_handling_weight: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="错误处理权重"
    )
    passing_threshold: float = Field(
        default=7.0,
        ge=0.0,
        le=10.0,
        description="通过阈值（满分10分）"
    )
    design_requirements_weight: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="需求覆盖权重"
    )
    architecture_weight: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="架构合理性权重"
    )
    extensibility_weight: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="可扩展性权重"
    )
    documentation_weight: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="文档完整性权重"
    )


class LongRunningConfig(BaseModel):
    """
    长时间运行模式配置
    
    管理长时间运行会话的配置选项，包括进度跟踪、上下文管理、
    多代理协作等功能。
    
    Attributes:
        progress_file: 进度文件路径
        feature_list_file: 功能列表文件路径
        summary_file: 摘要文件路径
        auto_generate_summary: 是否自动生成会话摘要
        context_compression_threshold: 上下文压缩阈值
        enable_long_running_mode: 是否启用长时间运行模式
        context_reset_threshold: 上下文重置阈值（百分比）
        context_warning_threshold: 上下文警告阈值
        enable_multi_agent: 是否启用多代理模式
        max_context_tokens: 最大上下文 token 数
        handoff_dir: HandoffArtifact 存储目录
        evaluator_criteria: 评估器评估标准配置
    """
    progress_file: str = ".foxcode/progress.md"  # 进度文件路径
    feature_list_file: str = ".foxcode/features.md"  # 功能列表文件路径
    summary_file: str = ".foxcode/summary.md"  # 摘要文件路径
    auto_generate_summary: bool = True  # 是否自动生成会话摘要
    context_compression_threshold: int = Field(default=4000, ge=500)  # 上下文压缩阈值
    enable_long_running_mode: bool = False  # 是否启用长时间运行模式
    
    context_reset_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="上下文重置阈值（百分比），当上下文使用率达到此阈值时触发重置"
    )
    context_warning_threshold: float = Field(
        default=0.70,
        ge=0.0,
        le=1.0,
        description="上下文警告阈值，当上下文使用率达到此阈值时发出警告"
    )
    enable_multi_agent: bool = Field(
        default=False,
        description="是否启用多代理模式，启用后将使用 Planner-Generator-Evaluator 架构"
    )
    max_context_tokens: int = Field(
        default=128000,
        ge=1000,
        description="最大上下文 token 数，用于控制上下文窗口大小"
    )
    handoff_dir: str = Field(
        default=".foxcode/handoffs",
        description="HandoffArtifact 存储目录，用于代理间任务传递"
    )
    evaluator_criteria: EvaluatorCriteriaConfig = Field(
        default_factory=EvaluatorCriteriaConfig,
        description="评估器评估标准配置"
    )


class WorkflowConfig(BaseModel):
    """工作流程配置"""
    # 工作流程存储目录
    workflow_dir: str = ".foxcode/workflows"
    # 是否自动推进工作流程
    auto_advance: bool = False
    # 主分支名称
    main_branch: str = "main"
    # 远程仓库名称
    remote_name: str = "origin"
    # 测试命令
    test_command: str = "pytest"
    # 是否在推送前运行测试
    test_before_push: bool = True
    # 是否自动创建分支
    auto_create_branch: bool = True
    # 分支命名模板
    branch_template: str = "feature/{feature_id}"


class MCPServerConfigModel(BaseModel):
    """MCP 服务器配置模型（用于配置文件）"""
    name: str = Field(description="服务器名称")
    command: str = Field(description="启动命令")
    args: list[str] = Field(default_factory=list, description="命令参数")
    env: dict[str, str] = Field(default_factory=dict, description="环境变量")
    cwd: str | None = Field(default=None, description="工作目录")
    enabled: bool = Field(default=True, description="是否启用")
    auto_start: bool = Field(default=True, description="是否自动启动")


class MCPConfig(BaseModel):
    """MCP (Model Context Protocol) 配置"""
    enabled: bool = Field(default=True, description="是否启用 MCP 功能")
    servers: list[MCPServerConfigModel] = Field(
        default_factory=list,
        description="MCP 服务器列表"
    )
    auto_discover: bool = Field(default=True, description="是否自动发现 MCP 服务器")
    config_file: str = Field(
        default=".foxcode/mcp.json",
        description="MCP 配置文件路径"
    )
    connection_timeout: int = Field(default=30, ge=5, description="连接超时时间（秒）")
    request_timeout: int = Field(default=60, ge=10, description="请求超时时间（秒）")


class SkillConfigModel(BaseModel):
    """技能配置模型（用于配置文件）"""
    name: str = Field(description="技能名称")
    enabled: bool = Field(default=True, description="是否启用")
    config: dict[str, Any] = Field(default_factory=dict, description="技能特定配置")


class SkillsConfig(BaseModel):
    """技能系统配置"""
    enabled: bool = Field(default=True, description="是否启用技能系统")
    skills: list[SkillConfigModel] = Field(
        default_factory=list,
        description="技能配置列表"
    )
    auto_discover: bool = Field(default=True, description="是否自动发现技能")
    skills_dir: str = Field(
        default=".foxcode/skills",
        description="技能目录"
    )
    enable_builtin: bool = Field(default=True, description="是否启用内置技能")


class Config(BaseSettings):
    """
    FoxCode 主配置类
    
    配置优先级（从高到低）：
    1. 命令行参数
    2. 环境变量
    3. 项目配置文件 (.foxcode.toml)
    4. 用户配置文件 (~/.foxcode/config.toml)
    5. 默认值
    """
    model_config = SettingsConfigDict(
        env_prefix="FOXCODE_",
        env_nested_delimiter="__",
        extra="ignore",
    )
    
    # 基本配置
    run_mode: RunMode = RunMode.DEFAULT
    debug: bool = False
    log_level: str = "INFO"
    
    # 子配置
    model: ModelConfig = Field(default_factory=ModelConfig)
    tools: ToolConfig = Field(default_factory=ToolConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    long_running: LongRunningConfig = Field(default_factory=LongRunningConfig)
    playwright: PlaywrightConfig = Field(default_factory=PlaywrightConfig)
    sandbox: SandboxConfigModel = Field(default_factory=SandboxConfigModel)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    work_mode: WorkModeConfig = Field(default_factory=WorkModeConfig, description="Work模式配置（默认启用）")
    
    # 工作目录
    working_dir: Path = Field(default_factory=lambda: Path.cwd())
    
    # 会话配置 - 默认在工作目录下的 .foxcode 目录
    session_dir: Path | None = Field(default=None)
    auto_save_session: bool = True
    max_history: int = Field(default=100, ge=0)
    
    def model_post_init(self, __context: Any) -> None:
        """Pydantic 模型初始化后处理"""
        # 如果未指定会话目录，使用工作目录下的 .foxcode/sessions
        if self.session_dir is None:
            self.session_dir = self.working_dir / ".foxcode" / "sessions"
    
    @classmethod
    def load_from_file(cls, config_path: Path | None = None) -> dict[str, Any]:
        """
        从配置文件加载配置
        
        Args:
            config_path: 配置文件路径，如果为 None 则自动查找
            
        Returns:
            配置字典
        """
        if config_path and config_path.exists():
            with open(config_path, "rb") as f:
                return tomllib.load(f)
        
        # 自动查找配置文件
        search_paths = [
            Path.cwd() / ".foxcode.toml",
            Path.cwd() / "foxcode.toml",
            Path.home() / ".foxcode" / "config.toml",
        ]
        
        for path in search_paths:
            if path.exists():
                with open(path, "rb") as f:
                    return tomllib.load(f)
        
        return {}
    
    @classmethod
    def create(cls, **overrides: Any) -> "Config":
        """
        创建配置实例，合并所有配置来源
        
        Args:
            **overrides: 命令行参数覆盖
            
        Returns:
            配置实例
        """
        # 从文件加载
        file_config = cls.load_from_file()
        
        # 合并配置
        return cls(**{**file_config, **overrides})
    
    @classmethod
    def validate_file(cls, config_path: Path | None = None) -> tuple[bool, str]:
        """
        验证配置文件
        
        Args:
            config_path: 配置文件路径，如果为 None 则自动查找
            
        Returns:
            (是否有效, 验证报告)
        """
        from foxcode.core.config_validator import validate_config_file
        
        if config_path is None:
            # 自动查找配置文件
            search_paths = [
                Path.cwd() / ".foxcode.toml",
                Path.cwd() / "foxcode.toml",
                Path.home() / ".foxcode" / "config.toml",
            ]
            for path in search_paths:
                if path.exists():
                    config_path = path
                    break
        
        if config_path is None or not config_path.exists():
            return True, "未找到配置文件，将使用默认配置"
        
        return validate_config_file(config_path)
    
    def validate(self) -> tuple[bool, list[dict[str, Any]], list[dict[str, Any]]]:
        """
        验证当前配置
        
        Returns:
            (是否有效, 错误列表, 警告列表)
        """
        from foxcode.core.config_validator import validate_config
        
        # 将配置转换为字典
        config_dict = {
            "model": {
                "provider": self.model.provider.value,
                "model_name": self.model.model_name,
                "api_key": self.model.api_key,
                "base_url": self.model.base_url,
                "temperature": self.model.temperature,
                "max_tokens": self.model.max_tokens,
                "timeout": self.model.timeout,
            },
            "tools": {
                "enable_file_ops": self.tools.enable_file_ops,
                "enable_shell": self.tools.enable_shell,
                "enable_web_search": self.tools.enable_web_search,
                "shell_timeout": self.tools.shell_timeout,
                "max_file_size": self.tools.max_file_size,
                "allowed_extensions": self.tools.allowed_extensions,
            },
            "ui": {
                "theme": self.ui.theme,
                "show_token_usage": self.ui.show_token_usage,
                "show_timing": self.ui.show_timing,
            },
            "session": {
                "auto_save_session": self.auto_save_session,
                "max_history": self.max_history,
            },
            "working_dir": str(self.working_dir),
            "session_dir": str(self.session_dir) if self.session_dir else None,
        }
        
        return validate_config(config_dict)
    
    def get_session_path(self, session_id: str) -> Path:
        """获取会话文件路径"""
        return self.session_dir / f"{session_id}.json"
    
    def ensure_directories(self) -> None:
        """确保必要的目录存在"""
        self.session_dir.mkdir(parents=True, exist_ok=True)
