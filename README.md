# FoxCode

**A Powerful AI Terminal Coding Assistant**

[English](#english) | [简体中文](#简体中文)

### Note: FoxCode follows AGPLv3, but AGPLv3 is not triggered if you do not modify the software code

---

## 简体中文

### 简介

FoxCode 是一个类似 Claude Code 的终端 AI 编码助手，使用 Python 编写。它支持多种 AI 模型，提供智能代码生成、文件操作、任务规划、工作流程管理等功能，帮助开发者提高编码效率。

### 特性

#### 核心功能
- **多模型支持**: OpenAI、Anthropic Claude、DeepSeek、Step、本地模型
- **文件操作**: 读取、写入、编辑、搜索文件
- **Shell 执行**: 在终端中安全执行命令
- **任务规划**: 管理复杂任务的执行流程
- **工作流程管理**: 标准化的开发工作流程（设计→编码→测试→合并→推送）
- **技能系统**: 可扩展的技能框架，支持动态加载
- **MCP 协议**: 支持 Model Context Protocol，连接外部工具
- **公司模式**: 长期工作模式，支持 QQbot 集成
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
# 使用 pip 安装
pip install foxcode

# 或从源码安装
git clone https://github.com/foxcode/foxcode.git
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