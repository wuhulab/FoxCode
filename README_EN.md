# FoxCode | English

[简体中文](README.md) | [English](README_EN.md)

**Warning: The English document is lacking in maintenance. Please refer to the simplified Chinese version for the latest maintained version.**

**Next-Generation AI Terminal Coding Assistant**

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19433875.svg)](https://zenodo.org/records/19433875)

### Contributing

#### We welcome contributions to FoxCode! You can contribute in the following ways:

1. **Code Contributions**: Submit new features, fix bugs, or optimize code

2. **Documentation Contributions**: Write documentation for FoxCode, including user manuals, development guides, API documentation, etc.

3. **Issue Maintenance**: Help manage GitHub issues, including fixing bugs, optimizing performance, adding new features, etc.


#### How to Contribute?

**Clone to Local**: Clone your forked repository to your local machine

**Create New Branch**: Create a new branch in your local repository for your contribution

**Submit Contribution**: Make your contributions on your branch and push to your forked repository

**Create Pull Request**: Create a Pull Request to the FoxCode repository, describe your contribution, and request your contribution to be merged

### What You Can Do

1. **Code Contributions**: Submit new features, fix bugs, or optimize code (Long-term plan)

2. **Write Multi-language Documentation**: Multi-language modules (Long-term plan)

3. **Issue Maintenance**: Help manage GitHub issues, including fixing bugs, optimizing performance, adding new features, etc. (Long-term plan)

#### Contributor Reward Program

We plan to distribute sponsor API sites in May. All useful contributions will receive points as rewards for contributors.

### Development Notes

1. Update version number in pyproject.toml
2. Update version number in __init__.py
3. Tag Actions

### News

#### 2026

4.8 shunian: I need FoxCode to automatically check for updates on startup - OK

4.8 shunian: Record reflections on issues after each project completion, add them to the context next time, which can greatly improve efficiency and reduce errors - OK

4.6 shunian: If using /mcp url, you can directly install MCP, which may greatly promote the development of MCP - OK

### Note: FoxCode follows AGPLv3, but not changing the software code does not trigger AGPLv3

### Introduction

FoxCode is a terminal CLI AI coding assistant written in Python. It supports multiple AI models, provides intelligent code generation, file operations, task planning, workflow management, and other features to help developers improve coding efficiency.

### Features

#### Core Features
- **Multi-Model Support**: OpenAI, Anthropic Claude, DeepSeek, Step, local models
- **File Operations**: Read, write, edit, search files
- **Shell Execution**: Safely execute commands in the terminal
- **Task Planning**: Manage execution flow of complex tasks
- **Workflow Management**: Standardized development workflow (Design → Code → Test → Merge → Push)
- **Skill System**: Extensible skill framework with dynamic loading support
- **MCP Protocol**: Support for Model Context Protocol to connect external tools
- **Security Sandbox**: Configurable command execution security policies
- **Interactive Interface**: Modern TUI terminal interface
- **Session Management**: Save and restore conversation history with encryption support
- **Multiple Running Modes**: Default, YOLO, Plan mode, Auto-accept edits mode
- **Semantic Code Indexing**: Vector embedding-based code semantic search with incremental updates and dependency graph generation
- **Knowledge Base Management**: Cross-session knowledge storage with categorization, tags, and semantic retrieval
- **Context Compression**: Intelligent conversation compression and knowledge distillation for optimized long conversation handling
- **Intelligent Task Planning**: Automatic task decomposition, dependency analysis, and topological sorting
- **Project Structure Analysis**: Automatic tech stack detection, code quality scoring, and architecture pattern recognition
- **Error Analysis**: Intelligent error parsing, root cause analysis, and fix suggestions
- **Advanced Debugging**: Conditional breakpoints, log breakpoints, variable watching, and call stack analysis
- **Performance Analysis**: Execution time analysis, memory tracking, and bottleneck identification
- **Security Scanning**: Vulnerability detection, sensitive information scanning, and dependency security checks
- **Code Formatting**: Multi-language code formatting (Python, JavaScript, TypeScript, etc.)
- **Refactoring Suggestions**: Code smell detection, design pattern suggestions, and refactoring plans
- **Dependency Resolution**: Python/Node.js dependency analysis and conflict detection
- **Test Generation**: pytest-style test generation, boundary cases, and TDD support
- **Documentation Generation**: API documentation, docstring, and README auto-generation
- **Git Advanced Operations**: Smart commits, conflict resolution, and branch management
- **Multimodal Processing**: Image analysis, Mermaid/PlantUML diagram generation

### Installation

```bash
pip install foxcode
```

### Quick Start

```bash
# Start interactive session
foxcode

# Ask a question directly
foxcode "Help me analyze the project structure"

# YOLO mode (auto-execute)
foxcode --yolo "Create a Flask application"

# Plan mode (read-only)
foxcode --plan "Analyze security issues in the codebase"

# Specify model
foxcode -m claude "Help me refactor this code"

# Resume last session
foxcode -r
```

### Command Line Options

| Option | Description |
|--------|-------------|
| `--model, -m` | Specify AI model (supports aliases) |
| `--mode` | Running mode (default/yolo/plan/accept_edits) |
| `--yolo` | Quick enable YOLO mode |
| `--plan` | Quick enable Plan mode |
| `--resume, -r` | Resume last session |
| `--session` | Specify session ID |
| `--list-sessions` | List all sessions |
| `--config` | Display configuration |
| `--debug` | Enable debug mode |
| `--no-tui` | Disable TUI interface |
| `--version, -v` | Display version |
| `--help, -h` | Display help |

### Interactive Commands

In interactive sessions, you can use the following commands:

#### Basic Commands

| Command | Description |
|---------|-------------|
| `/help` | Display help |
| `/clear` | Clear conversation |
| `/save` | Save session |
| `/load <id>` | Load session |
| `/mode <mode>` | Switch mode |
| `/model <name>` | Switch model |
| `/token` | Display token usage statistics |
| `/sessions` | List sessions |
| `/exit` or `/quit` | Exit |

#### Long-Running Mode Commands

| Command | Description |
|---------|-------------|
| `/init` | Generate project initialization script |
| `/progress` | Display current progress |
| `/features [add/complete/list]` | Manage feature list |
| `/summary` | Generate session summary |
| `/next` | Get next suggested task |
| `/long-running [on/off]` | Toggle long-running mode |
| `/index` | Build semantic code index |
| `/index status` | View index status |
| `/index update` | Incremental update index |
| `/search <query>` | Semantic search code |
| `/kb` | Display knowledge base status |
| `/kb add <content>` | Add knowledge entry |
| `/kb search <query>` | Search knowledge base |
| `/kb tags` | List all tags |
| `/analyze` | Analyze current project |
| `/analyze tech` | Analyze tech stack |
| `/analyze quality` | Analyze code quality |
| `/debug start` | Start debug session |
| `/debug break <file:line>` | Set breakpoint |
| `/debug continue` | Continue execution |
| `/debug step` | Step execution |
| `/debug vars` | Display variables |
| `/profile` | Start performance analysis |
| `/profile report` | View analysis report |
| `/security` | Run security scan |
| `/security deps` | Scan dependency vulnerabilities |
| `/topic` | Display current output topic mode |
| `/topic default` | Switch to default mode (full output) |
| `/topic debug` | Switch to debug mode (verbose output) |
| `/topic minimalism` | Switch to minimal mode (concise output) |
| `/format [files]` | Format code |
| `/refactor` | Get refactoring suggestions |
| `/test gen <file>` | Generate test cases |
| `/doc gen <file>` | Generate documentation |
| `/git smart-commit` | Smart commit |
| `/git conflicts` | Analyze conflicts |
| `/diagram <type>` | Generate diagrams (mermaid/plantuml) |

### Configuration

Configuration file locations (in priority order):
1. Project level: `.foxcode.toml` or `foxcode.toml`
2. User level: `~/.foxcode/config.toml`


### Workflow

FoxCode provides a standardized development workflow:

```
Design Planning → Code Implementation → Quality Assessment → Local Testing → Merge to Main → Integration Testing → Push Branch
```

Each stage has status tracking:
- Pending
- In Progress
- Completed
- Failed
- Skipped
- Blocked

### Security Features

- **Sandbox Mode**: Support blacklist/whitelist mode to restrict command execution
- **Command Validation**: Prevent dangerous command injection attacks
- **Sensitive Information Filtering**: Automatically filter API keys and other sensitive information
- **Session Encryption**: Support encrypted storage of session data
- **Security Audit**: Record security event logs

### Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
foxcode
```

### Project Structure

```
src/foxcode/
├── __init__.py              # Package entry
├── cli.py                   # CLI entry
│
├── core/                    # Core modules
│   ├── __init__.py
│   ├── agent.py             # AI agent
│   ├── config.py            # Configuration management
│   ├── config_validator.py  # Configuration validation
│   ├── providers.py         # Model providers
│   ├── session.py           # Session management
│   ├── session_encryption.py # Session encryption
│   ├── tasks.py             # Task management
│   ├── workflow.py          # Workflow
│   ├── skill.py             # Skill system
│   ├── sandbox.py           # Security sandbox
│   ├── sensitive_masker.py  # Sensitive information masking
│   ├── progress.py          # Progress management
│   ├── feature_list.py      # Feature list
│   ├── handoff.py           # Agent handoff
│   ├── evaluator.py         # Evaluator
│   ├── orchestrator.py      # Orchestrator
│   ├── command_manager.py   # Command management
│   ├── init_script.py       # Initialization script
│   ├── hooks.py             # Hook management
│   ├── work_mode.py         # Work mode
│   ├── work_mode_config.py  # Work mode configuration
│   ├── open_space.py        # Open space
│   ├── process_watchdog.py  # Process watchdog
│   ├── updater.py           # Updater
│   │
│   │── Advanced Feature Modules ──
│   ├── semantic_index.py    # Semantic code index
│   ├── knowledge_base.py    # Knowledge base management
│   ├── task_planner.py      # Intelligent task planning
│   ├── project_analyzer.py  # Project structure analysis
│   ├── error_analyzer.py    # Error analysis
│   ├── advanced_debugger.py # Advanced debugger
│   ├── performance_analyzer.py # Performance analysis
│   ├── security_scanner.py  # Security scanner
│   ├── code_formatter.py    # Code formatter
│   ├── refactoring_suggester.py # Refactoring suggester
│   ├── dependency_resolver.py # Dependency resolver
│   ├── test_generator.py    # Test generator
│   ├── doc_generator.py     # Documentation generator
│   ├── git_advanced_ops.py  # Git advanced operations
│   ├── multimodal_processor.py # Multimodal processor
│   ├── enhanced_tools.py    # Enhanced tools integration
│   │
│   └── hooks/               # Hook modules
│       ├── __init__.py
│       ├── base.py          # Hook base class
│       ├── app_hooks.py     # App hooks
│       ├── command_hooks.py # Command hooks
│       ├── config_hooks.py  # Config hooks
│       ├── service_hooks.py # Service hooks
│       ├── session_hooks.py # Session hooks
│       ├── skill_hooks.py   # Skill hooks
│       ├── tool_hooks.py    # Tool hooks
│       └── work_mode_hooks.py # Work mode hooks
│
├── commands/                # Command modules
│   ├── __init__.py
│   ├── command.py           # Command base class
│   ├── help.py              # Help command
│   ├── prompt.py            # Prompt command
│   └── tool.py              # Tool command
│
├── tools/                   # Tool modules
│   ├── __init__.py
│   ├── base.py              # Tool base class
│   ├── ai_tools.py          # AI tools
│   ├── file_tools.py        # File operations
│   ├── shell_tools.py       # Shell execution
│   ├── code_tools.py        # Code analysis
│   ├── mcp_tools.py         # MCP tools
│   └── playwright_tools.py  # Playwright tools
│
├── services/                # Service modules
│   ├── __init__.py
│   ├── mcp.py               # MCP protocol
│   ├── mcp_installer.py     # MCP installer
│   └── api/                 # API clients
│       ├── client.py        # API client
│       └── unified_client.py # Unified client
│
├── context/                 # Context modules
│   ├── __init__.py
│   ├── context_bridge.py    # Context bridge
│   ├── context_compressor.py # Context compression
│   └── context_reset.py     # Context reset
│
├── tui/                     # TUI interface
│   ├── __init__.py
│   └── app.py               # Terminal application
│
├── types/                   # Type definitions
│   ├── __init__.py
│   └── message.py           # Message types
│
├── utils/                   # Utility functions
│   ├── __init__.py
│   ├── encoding.py          # Encoding handling
│   └── statistics.py        # Statistics
│
├── hooks/                   # Global hooks
│   └── __init__.py
│
├── constants/               # Constants
│   └── __init__.py
│
├── components/              # Components
│   └── __init__.py
│
└── screens/                 # Screens
    └── __init__.py
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API Key |
| `ANTHROPIC_API_KEY` | Anthropic API Key |
| `DEEPSEEK_API_KEY` | DeepSeek API Key |
| `STEP_API_KEY` | Step API Key |
| `FOXCODE_DEBUG` | Enable debug mode |
| `FOXCODE_LOG_LEVEL` | Log level |

### FAQ

Q: How to enable terminal minimal mode if you think there's too much content?

/topic minimalism

Q: How to use local models?

```bash
foxcode --model local --base-url http://localhost:8000/v1
```

Q: How to view token usage?

Use the `/token` command in an interactive session.

Q: How to enable debug mode?

```bash
foxcode --debug
```

Q: Where to put configuration files?

Project-level configuration goes in `.foxcode.toml` in the project root, user-level configuration goes in `~/.foxcode/config.toml`.


### License

AGPLv3 License - See [LICENSE](LICENSE.txt) file for details
