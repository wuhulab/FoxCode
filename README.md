# FoxCode | 简体中文

**新一代 AI 终端编码助手**

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19433875.svg)](https://zenodo.org/records/19433875)

### 贡献

#### 我们欢迎对 FoxCode 的贡献！您可以通过以下方式贡献：
1,贡献代码 您可以提交新功能或者修复bug，优化代码

2，贡献文档 您可以为 FoxCode 编写文档，包括用户手册、开发指南、API 文档等

3，维护问题：帮助管理 GitHub 问题，包括修复 bug、优化性能、添加新功能等


#### 怎么做
克隆到本地：克隆您的 Fork 仓库到本地

创建新分支：在本地创建一个新的分支，用于您的贡献

提交贡献：在您的分支上进行贡献，提交到您的 Fork 仓库

创建 Pull Request：创建一个 Pull Request 到 FoxCode 仓库，描述您的贡献内容，请求您的贡献被合并


#### 贡献者奖励计划
我们计划在5月份发放赞助商api站点，参与有用贡献都会获得积分以奖励贡献者。

### News

#### 2026
4.8 shunian 我需要一个foxcode的启动自动检查更新 ok

4.8 shunian 在每次工程完成后记录反思存在的问题，下次加入上下文中，可以大大提高效率，减少犯错 ok?

4.6 shunian 如果使用/mcp url就可以直接安装mcp，或许可以极大地推动mcp的发展 ok

### 请注意，foxcode遵循AGPLv3，但不更改本软件代码不触发AGPLv3

### 简介

FoxCode 是一个终端 AI 编码助手，使用 Python 编写。它支持多种 AI 模型，提供智能代码生成、文件操作、任务规划、工作流程管理等功能，帮助开发者提高编码效率

### 特性

#### 核心功能
- **多模型支持**: OpenAI、Anthropic Claude、DeepSeek、Step、本地模型
- **文件操作**: 读取、写入、编辑、搜索文件
- **Shell 执行**: 在终端中安全执行命令
- **任务规划**: 管理复杂任务的执行流程
- **工作流程管理**: 标准化的开发工作流程（设计→编码→测试→合并→推送）
- **技能系统**: 可扩展的技能框架，支持动态加载
- **MCP 协议**: 支持 Model Context Protocol，连接外部工具
- **安全沙箱**: 可配置的命令执行安全策略
- **交互式界面**: 现代化的 TUI 终端界面
- **会话管理**: 保存和恢复对话历史，支持加密
- **多种运行模式**: 默认、YOLO、规划模式、自动接受编辑模式

#### 高级功能 (v2.0 新增)
- **语义代码索引**: 基于向量嵌入的代码语义搜索，支持增量更新和依赖图生成
- **知识库管理**: 跨会话知识存储，支持分类、标签和语义检索
- **上下文压缩**: 智能对话压缩和知识蒸馏，优化长对话处理
- **智能任务规划**: 自动任务分解、依赖分析和拓扑排序
- **项目结构分析**: 自动检测技术栈、代码质量评分和架构模式识别
- **错误分析**: 智能错误解析、根因分析和修复建议
- **高级调试**: 条件断点、日志断点、变量监视和调用栈分析
- **性能分析**: 执行时间分析、内存追踪和瓶颈识别
- **安全扫描**: 漏洞检测、敏感信息扫描和依赖安全检查
- **代码格式化**: 多语言代码格式化（Python、JavaScript、TypeScript 等）
- **重构建议**: 代码异味检测、设计模式建议和重构方案
- **依赖解析**: Python/Node.js 依赖分析和冲突检测
- **测试生成**: pytest 风格测试生成、边界用例和 TDD 支持
- **文档生成**: API 文档、docstring 和 README 自动生成
- **Git 高级操作**: 智能提交、冲突解决和分支管理
- **多模态处理**: 图像分析、Mermaid/PlantUML 图表生成

### 安装

```bash
# 从源码安装
git clone https://github.com/wuhulab/foxcode.git
cd foxcode
pip install -e .

# 安装开发依赖
pip install -e ".[dev]"

# 安装本地模型支持
pip install -e ".[local]"
```

### 快速开始

```bash
# 启动交互式会话
foxcode

# 直接提问
foxcode "帮我分析这个项目的结构"

# YOLO 模式（自动执行）
foxcode --yolo "创建一个 Flask 应用"

# 规划模式（只读）
foxcode --plan "分析代码库中的安全问题"

# 指定模型
foxcode -m claude "帮我重构这段代码"

# 恢复上次会话
foxcode -r
```

### 命令行选项

| 选项 | 说明 |
|------|------|
| `--model, -m` | 指定 AI 模型（支持别名） |
| `--mode` | 运行模式 (default/yolo/plan/accept_edits) |
| `--yolo` | 快捷启用 YOLO 模式 |
| `--plan` | 快捷启用规划模式 |
| `--resume, -r` | 恢复上次会话 |
| `--session` | 指定会话 ID |
| `--list-sessions` | 列出所有会话 |
| `--config` | 显示配置 |
| `--debug` | 启用调试模式 |
| `--no-tui` | 禁用 TUI 界面 |
| `--version, -v` | 显示版本 |
| `--help, -h` | 显示帮助 |

### 交互式命令

在交互式会话中，可以使用以下命令：

#### 基本命令

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助 |
| `/clear` | 清空对话 |
| `/save` | 保存会话 |
| `/load <id>` | 加载会话 |
| `/mode <mode>` | 切换模式 |
| `/model <name>` | 切换模型 |
| `/token` | 显示 Token 使用统计 |
| `/sessions` | 列出会话 |
| `/exit` 或 `/quit` | 退出 |

#### 长时间运行模式命令

| 命令 | 说明 |
|------|------|
| `/init` | 生成项目初始化脚本 |
| `/progress` | 显示当前进度 |
| `/features [add/complete/list]` | 管理功能列表 |
| `/summary` | 生成会话摘要 |
| `/next` | 获取下一个建议任务 |
| `/long-running [on/off]` | 切换长时间运行模式 |

#### 工作流程命令

| 命令 | 说明 |
|------|------|
| `/workflow` 或 `/wf` | 显示当前工作流程状态 |
| `/workflow start <feature_id>` | 为功能启动工作流程 |
| `/workflow list` | 列出所有工作流程 |
| `/workflow status <id>` | 显示工作流程详情 |
| `/workflow advance` | 推进当前工作流程到下一阶段 |
| `/workflow skip` | 跳过当前阶段 |
| `/phase` | 显示当前阶段 |
| `/phase complete` | 完成当前阶段 |
| `/phase fail` | 标记当前阶段失败 |

#### 公司模式命令

| 命令 | 说明 |
|------|------|
| `/work <任务描述>` | 以长期工作模式启动任务 |
| `/work status` | 查看当前任务状态 |
| `/work list` | 列出所有任务 |
| `/work stop <task_id>` | 停止指定任务 |

#### 高级功能命令 (v2.0 新增)

| 命令 | 说明 |
|------|------|
| `/index` | 构建语义代码索引 |
| `/index status` | 查看索引状态 |
| `/index update` | 增量更新索引 |
| `/search <query>` | 语义搜索代码 |
| `/kb` | 显示知识库状态 |
| `/kb add <content>` | 添加知识条目 |
| `/kb search <query>` | 搜索知识库 |
| `/kb tags` | 列出所有标签 |
| `/analyze` | 分析当前项目 |
| `/analyze tech` | 分析技术栈 |
| `/analyze quality` | 分析代码质量（bug） |
| `/debug start` | 启动调试会话 |
| `/debug break <file:line>` | 设置断点 |
| `/debug continue` | 继续执行 |
| `/debug step` | 单步执行 |
| `/debug vars` | 显示变量 |
| `/profile` | 启动性能分析 |
| `/profile report` | 查看分析报告 |
| `/security` | 运行安全扫描（bug） |
| `/security deps` | 扫描依赖漏洞（bug） |
| `/topic` | 显示当前输出主题模式 |
| `/topic default` | 切换到默认模式（完整输出） |
| `/topic debug` | 切换到调试模式（详细输出） |
| `/topic minimalism` | 切换到极简模式（精简输出） |
| `/format [files]` | 格式化代码 |
| `/refactor` | 获取重构建议 |
| `/test gen <file>` | 生成测试用例 |
| `/doc gen <file>` | 生成文档 |
| `/git smart-commit` | 智能提交 |
| `/git conflicts` | 分析冲突 |
| `/diagram <type>` | 生成图表 (mermaid/plantuml) |

### 配置

配置文件位置（按优先级排序）：
1. 项目级: `.foxcode.toml` 或 `foxcode.toml`
2. 用户级: `~/.foxcode/config.toml`

#### 完整配置示例

```toml
# 模型配置
[model]
provider = "openai"                    # 提供者: openai, anthropic, deepseek, step, local
model_name = "gpt-4o"                  # 模型名称
api_key = "your-api-key-here"          # API Key（建议使用环境变量）
base_url = ""                          # API 基础 URL（可选）
temperature = 0.7                      # 温度参数 (0.0 - 2.0)
max_tokens = 4096                      # 最大 token 数
timeout = 120                          # 请求超时时间 (秒)

# 工具配置
[tools]
enable_file_ops = true                 # 启用文件操作
enable_shell = true                    # 启用 Shell 执行
enable_web_search = false              # 启用网络搜索
enable_code_execution = true           # 启用代码执行
shell_timeout = 300                    # Shell 命令超时时间 (秒)
max_file_size = 10485760               # 最大文件大小 (10MB)

# UI 配置
[ui]
theme = "dark"                         # 主题: dark, light
show_token_usage = true                # 显示 token 使用统计
show_timing = true                     # 显示响应时间
compact_mode = false                   # 紧凑模式
syntax_highlight = true                # 语法高亮
mouse_support = true                   # 鼠标支持

# 会话配置
[session]
auto_save_session = true               # 自动保存会话
max_history = 100                      # 最大历史记录数

# 沙箱配置
[sandbox]
enabled = true                         # 启用沙箱
mode = "blacklist"                     # 模式: disabled, blacklist, whitelist
allow_path_traversal = false           # 允许路径穿越
max_command_length = 10000             # 最大命令长度
allowed_commands = ["ls", "git", "npm", "python"]
blocked_commands = ["format", "shutdown"]

# Playwright 配置
[playwright]
browser_type = "chromium"              # 浏览器类型: chromium, firefox, webkit
headless = true                        # 无头模式
viewport_width = 1280                  # 视口宽度
viewport_height = 720                  # 视口高度
default_timeout = 30000                # 默认超时 (毫秒)
enable_playwright = true               # 启用 Playwright

# 长时间运行模式配置
[long_running]
enable_long_running_mode = false       # 启用长时间运行模式
enable_multi_agent = false             # 启用多代理模式
context_reset_threshold = 0.85         # 上下文重置阈值
context_warning_threshold = 0.70       # 上下文警告阈值
max_context_tokens = 128000            # 最大上下文 token 数
auto_generate_summary = true           # 自动生成摘要

# 工作流程配置
[workflow]
workflow_dir = ".foxcode/workflows"    # 工作流程存储目录
auto_advance = false                   # 自动推进工作流程
main_branch = "main"                   # 主分支名称
test_before_push = true                # 推送前运行测试
auto_create_branch = true              # 自动创建分支

# MCP 配置
[mcp]
enabled = true                         # 启用 MCP
auto_discover = true                   # 自动发现 MCP 服务器
config_file = ".foxcode/mcp.json"      # MCP 配置文件路径
connection_timeout = 30                # 连接超时 (秒)
request_timeout = 60                   # 请求超时 (秒)

# 技能系统配置
[skills]
enabled = true                         # 启用技能系统
auto_discover = true                   # 自动发现技能
skills_dir = ".foxcode/skills"         # 技能目录
enable_builtin = true                  # 启用内置技能

# 语义索引配置 (v2.0 新增)
[semantic_index]
enabled = true                         # 启用语义索引
index_dir = ".foxcode/semantic_index"  # 索引存储目录
embedding_model = "text-embedding-3-small" # 嵌入模型
chunk_size = 500                       # 代码块大小
chunk_overlap = 50                     # 代码块重叠
auto_update = true                     # 自动增量更新

# 知识库配置 (v2.0 新增)
[knowledge_base]
enabled = true                         # 启用知识库
storage_dir = ".foxcode/knowledge"     # 知识库存储目录
max_entries = 10000                    # 最大条目数
auto_tag = true                        # 自动标签
cross_session = true                   # 跨会话共享

# 调试器配置 (v2.0 新增)
[debugger]
enabled = true                         # 启用高级调试
max_breakpoints = 100                  # 最大断点数
default_timeout = 30000                # 默认超时 (毫秒)
log_breakpoints = true                 # 启用日志断点

# 性能分析配置 (v2.0 新增)
[performance]
enabled = true                         # 启用性能分析
profile_memory = true                  # 内存分析
profile_time = true                    # 时间分析
output_dir = ".foxcode/profiles"       # 分析结果目录

# 安全扫描配置 (v2.0 新增)
[security_scanner]
enabled = true                         # 启用安全扫描
scan_secrets = true                    # 扫描敏感信息
scan_dependencies = true               # 扫描依赖漏洞
severity_threshold = "medium"          # 严重性阈值 (low/medium/high/critical)
```

### 工作流程

FoxCode 提供了标准化的开发工作流程：

```
设计规划 → 编码实现 → 质量评估 → 本地测试 → 合并主分支 → 集成测试 → 推送分支
```

每个阶段都有状态追踪：
- 待处理 (pending)
- 进行中 (in_progress)
- 已完成 (completed)
- 失败 (failed)
- 已跳过 (skipped)
- 已阻塞 (blocked)

### 安全特性

- **沙箱模式**: 支持黑名单/白名单模式限制命令执行
- **命令验证**: 防止危险的命令注入攻击
- **敏感信息过滤**: 自动过滤 API Key 等敏感信息
- **会话加密**: 支持会话数据加密存储
- **安全审计**: 记录安全事件日志

### 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 代码检查
ruff check src/

# 类型检查
mypy src/

# 格式化代码
black src/
isort src/

# 运行所有检查
pre-commit run --all-files
```

### 项目结构

```
foxcode/
├── src/foxcode/
│   ├── __init__.py              # 包入口
│   ├── cli.py                   # CLI 入口
│   ├── core/                    # 核心模块
│   │   ├── agent.py             # AI 代理
│   │   ├── config.py            # 配置管理
│   │   ├── config_validator.py  # 配置验证
│   │   ├── message.py           # 消息类型
│   │   ├── providers.py         # 模型提供者
│   │   ├── session.py           # 会话管理
│   │   ├── session_encryption.py # 会话加密
│   │   ├── tasks.py             # 任务管理
│   │   ├── workflow.py          # 工作流程
│   │   ├── skill.py             # 技能系统
│   │   ├── mcp.py               # MCP 协议
│   │   ├── sandbox.py           # 安全沙箱
│   │   ├── security_filter.py   # 安全过滤
│   │   ├── sensitive_masker.py  # 敏感信息屏蔽
│   │   ├── company_mode.py      # 公司模式
│   │   ├── company_mode_config.py # 公司模式配置
│   │   ├── qqbot_service.py     # QQbot 服务
│   │   ├── progress.py          # 进度管理
│   │   ├── feature_list.py      # 功能列表
│   │   ├── context_bridge.py    # 上下文桥接
│   │   ├── context_reset.py     # 上下文重置
│   │   ├── handoff.py           # 代理切换
│   │   ├── evaluator.py         # 评估器
│   │   ├── orchestrator.py      # 编排器
│   │   ├── statistics.py        # 统计信息
│   │   ├── encoding.py          # 编码处理
│   │   ├── command_manager.py   # 命令管理
│   │   ├── init_script.py       # 初始化脚本
│   │   │
│   │   │── 高级功能模块 (v2.0 新增) ──│
│   │   ├── semantic_index.py    # 语义代码索引
│   │   ├── knowledge_base.py    # 知识库管理
│   │   ├── context_compressor.py # 上下文压缩
│   │   ├── task_planner.py      # 智能任务规划
│   │   ├── project_analyzer.py  # 项目结构分析
│   │   ├── error_analyzer.py    # 错误分析
│   │   ├── advanced_debugger.py # 高级调试器
│   │   ├── performance_analyzer.py # 性能分析
│   │   ├── security_scanner.py  # 安全扫描
│   │   ├── code_formatter.py    # 代码格式化
│   │   ├── refactoring_suggester.py # 重构建议
│   │   ├── dependency_resolver.py # 依赖解析
│   │   ├── test_generator.py    # 测试生成
│   │   ├── doc_generator.py     # 文档生成
│   │   ├── git_advanced_ops.py  # Git 高级操作
│   │   ├── multimodal_processor.py # 多模态处理
│   │   └── enhanced_tools.py    # 增强工具集成
│   ├── tools/                   # 工具模块
│   │   ├── base.py              # 工具基类
│   │   ├── file_tools.py        # 文件操作
│   │   ├── shell_tools.py       # Shell 执行
│   │   ├── code_tools.py        # 代码分析
│   │   ├── mcp_tools.py         # MCP 工具
│   │   └── playwright_tools.py  # Playwright 工具
│   └── tui/                     # TUI 界面
│       ├── __init__.py
│       └── app.py               # 终端应用
├── tests/                       # 测试文件
├── .foxcode.toml.example        # 配置示例
├── pyproject.toml               # 项目配置
├── LICENSE                      # 许可证
└── README.md                    # 说明文档
```

### 环境变量

| 变量名 | 说明 |
|--------|------|
| `OPENAI_API_KEY` | OpenAI API Key |
| `ANTHROPIC_API_KEY` | Anthropic API Key |
| `DEEPSEEK_API_KEY` | DeepSeek API Key |
| `STEP_API_KEY` | Step API Key |
| `FOXCODE_DEBUG` | 启用调试模式 |
| `FOXCODE_LOG_LEVEL` | 日志级别 |

### 常见问题

**Q: 如何使用本地模型？**

```bash
foxcode --model local --base-url http://localhost:8000/v1
```

**Q: 如何查看 Token 使用情况？**

在交互式会话中使用 `/token` 命令。

**Q: 如何启用调试模式？**

```bash
foxcode --debug
```

**Q: 配置文件放在哪里？**

项目级配置放在项目根目录的 `.foxcode.toml`，用户级配置放在 `~/.foxcode/config.toml`。

### 贡献

欢迎贡献代码，用于修复bug或添加新功能！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

### License

AGPLv3 License - 详见 [LICENSE](LICENSE.txt) 文件
