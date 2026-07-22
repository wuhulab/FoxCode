# FoxCode | 繁體中文

### 贊助商

[Fai](https://Fai.shunx.top/)

[English](README_EN.md) | [簡體中文](README.md) | [繁體中文](README_TW.md)

**新一代 AI 終端編碼助手**

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19433875.svg)](https://zenodo.org/records/19433875)

### 貢獻

#### 我們歡迎對 FoxCode 的貢獻！您可以透過以下方式貢獻：

1，貢獻程式碼 您可以提交新功能或者修復 bug，優化程式碼

2，貢獻文件 您可以為 FoxCode 編寫文件，包括使用者手冊、開發指南、API 文件等

3，維護問題：幫助管理 GitHub 問題，包括修復 bug、優化效能、添加新功能等

### Future

#### 貢獻者獎勵計畫

(貢獻者獎勵計畫由 Fai 提供)

我們將視貢獻情況給予不同獎勵

獎勵使用模型包括：gpt-oss-120b，laguna-xs-2.1 等等

（請查看 issue 和 pr，重複的不給予獎勵）

#### TODO

- [ ] 進一步完善 TUI

- [ ] 修復 TUI 歷史聊天的 3 個點的 BUG

#### 怎麼做？

克隆到本地：克隆您的 Fork 倉庫到本地

建立新分支：在本地建立一個新的分支，用於您的貢獻

提交貢獻：在您的分支上進行貢獻，提交到您的 Fork 倉庫

建立 Pull Request：建立一個 Pull Request 到 FoxCode 倉庫，描述您的貢獻內容，請求您的貢獻被合併

### 您可以做什麼

1，貢獻程式碼 您可以提交新功能或者修復 bug，優化程式碼（長期計畫）

2，編寫多語言文件，多語言模組（長期計畫）

3，維護問題：幫助管理 GitHub 問題，包括修復 bug、優化效能、添加新功能等（長期計畫）

#### 貢獻者獎勵計畫

我們計畫在 5 月份發放贊助商 api 站點，參與有用貢獻都會獲得積分以獎勵貢獻者。

### 我的文件

1. 更新 pyproject.toml 中的版本號
2. 更新 __init__.py 中的版本號
3. tag Actions

### News

#### 2026

4.8 shunian 我需要一個 foxcode 的啟動自動檢查更新 ok

4.8 shunian 在每次工程完成後記錄反思存在的問題，下次加入上下文中，可以大幅提高效率，減少犯錯 ok

4.6 shunian 如果使用 /mcp url 就可以直接安裝 mcp，或許可以大幅推動 mcp 的發展 ok

### 請注意，foxcode 遵循 AGPLv3，但不更改本軟體程式碼不觸發 AGPLv3

### 簡介

FoxCode 是一個終端 cli AI 編碼助手，使用 Python 編寫。它支援多種 AI 模型，提供智慧程式碼生成、檔案操作、任務規劃、工作流程管理等功能，幫助開發者提高編碼效率

### 特性

#### 核心功能
- **多模型支援**: OpenAI、Anthropic Claude、DeepSeek、Step、本地模型
- **檔案操作**: 讀取、寫入、編輯、搜尋檔案
- **Shell 執行**: 在終端中安全執行命令
- **任務規劃**: 管理複雜任務的執行流程
- **工作流程管理**: 標準化的開發工作流程（設計→編碼→測試→合併→推送）
- **技能系統**: 可擴展的技能框架，支援動態載入
- **MCP 協議**: 支援 Model Context Protocol，連接外部工具
- **安全沙箱**: 可配置的命令執行安全策略
- **互動式介面**: 現代化的 TUI 終端介面
- **會話管理**: 儲存和恢復對話歷史，支援加密
- **多種執行模式**: 預設、Build、規劃模式、自動接受編輯模式
- **語義程式碼索引**: 基於向量嵌入的程式碼語義搜尋，支援增量更新和依賴圖生成
- **知識庫管理**: 跨會話知識儲存，支援分類、標籤和語義檢索
- **上下文壓縮**: 智慧對話壓縮和知識蒸餾，最佳化長對話處理
- **智慧任務規劃**: 自動任務分解、依賴分析和拓撲排序
- **專案結構分析**: 自動檢測技術棧、程式碼品質評分和架構模式識別
- **錯誤分析**: 智慧錯誤解析、根因分析和修復建議
- **高級除錯**: 條件中斷點、日誌中斷點、變數監視和呼叫堆疊分析
- **效能分析**: 執行時間分析、記憶體追蹤和瓶頸識別
- **安全掃描**: 漏洞檢測、敏感資訊掃描和依賴安全檢查
- **程式碼格式化**: 多語言程式碼格式化（Python、JavaScript、TypeScript 等）
- **重構建議**: 程式碼異味檢測、設計模式建議和重構方案
- **依賴解析**: Python/Node.js 依賴分析和衝突檢測
- **測試生成**: pytest 風格測試生成、邊界用例和 TDD 支援
- **文件生成**: API 文件、docstring 和 README 自動生成
- **Git 高級操作**: 智慧提交、衝突解決和分支管理
- **多模態處理**: 影像分析、Mermaid/PlantUML 圖表生成

### 安裝


pip install foxcode

### 快速開始


# 啟動互動式會話 (CLI 模式)
foxcode

# 啟動 TUI 圖形終端介面
foxcode --tui

# 或透過 Python 直接啟動 TUI
python -c "from foxcode.tui import run_tui; run_tui()"

# 直接提問
foxcode "幫我分析這個專案的結構"

# Build 模式（自動執行）
foxcode --build "建立一個 Flask 應用"

# 規劃模式（唯讀）
foxcode --plan "分析程式碼庫中的安全問題"

# 指定模型
foxcode -m claude "幫我重構這段程式碼"

# 恢復上次會話
foxcode -r

### TUI 終端介面

FoxCode 提供基於 Textual 構建的全功能 TUI（終端使用者介面），1:1 復刻 Claude Code 的互動體驗。

#### TUI 鍵盤快捷鍵

| 快捷鍵 | 動作 |
|--------|------|
| `Enter` | 發送訊息 |
| `Shift+Enter` | 換行 |
| `Ctrl+L` | 清屏 |
| `Ctrl+N` | 新會話 |
| `Ctrl+S` | 儲存會話 |
| `Ctrl+B` | 切換側欄 |
| `Ctrl+T` | 循環模式 (build/plan/accept) |
| `F1 / ?` | 幫助 |
| `F11` | 全螢幕切換 |
| `PageUp / PageDown` | 上下翻頁 |
| `Ctrl+A` | 全選文字 |
| `Ctrl+E` | 游標到行尾 |
| `Ctrl+K` | 刪除到行尾 |
| `Ctrl+W` | 刪除詞 |
| `Ctrl+U` | 清空行 |
| `Esc` | 取消 |
| `Ctrl+C` | 僅在輸入框中退出;在聊天區不退出（留給複製） |
| `Ctrl+Q` | 退出 FoxCode |
| `Ctrl+Y` | 複製上一條 AI 回覆（靜默，不提示） |
| `C` | 複製選中的訊息（先點選訊息選中，靜默） |
| `D` | 刪除選中的訊息 |

#### TUI 斜線命令（本地指令，不發給 AI）

以 `/` 開頭的輸入會被當作本地指令執行，而不是發送給 AI 代理。即使 AI 正在輸出，命令也會立即執行。

**命令解析順序：**
1. 先在 TUI 內建命令中查詢（下表），命中即在 TUI 內執行;
2. 若 TUI 不認識，則把整條命令**原樣轉交給 CLI 的命令處理器**（`cli._handle_command`）執行——因此 README「互動式命令」裡那一長串 CLI 命令（`/init` `/features` `/index` `/search` `/kb` `/debug` `/test` `/doc` `/git` `/topic` 等）無需在 TUI 中重複實現，直接在 TUI 裡輸入即可;
3. 只有 TUI 與 CLI 都不認識時，才在聊天區報錯「未知命令」。

| TUI 內建命令 | 說明 |
|------|------|
| `/help` | 顯示 TUI 命令列表 |
| `/clear` | 清空聊天（會取消正在進行的輸出） |
| `/save` | 儲存當前會話 |
| `/mode [name]` | 設定執行模式：`build` / `plan` / `accept_edits` |
| `/new` | 開始新會話（會取消正在進行的輸出） |
| `/sidebar` | 切換側欄 |
| `/fullscreen` 或 `/fs` | 切換全螢幕 |
| `/theme [name]` | 切換主題（dark / light / dark-ansi / light-ansi / dark-daltonized / light-daltonized） |
| `/history` | 顯示輸入歷史 |
| `/quit` 或 `/exit` | 退出 FoxCode |
| `//text` | 發送一個以 `/` 開頭的字面訊息給 AI |

> 其餘所有 `/命令` 均轉發給 CLI 執行，CLI 輸出會被擷取並顯示在聊天區。TUI 透過臨時重定向 CLI 的 `console` 來避免破壞終端介面。

#### TUI 特性

- **多行輸入**: 支援 Shift+Enter 換行的 TextArea
- **命令歷史**: Up/Down 導航歷史命令
- **訊息操作欄**: 游標選中訊息後顯示 E=編輯/C=複製/D=刪除/J=跳轉
- **動畫 Spinner**: Linux 標準 `-/\\|` 旋轉動畫，帶停滯檢測和 Glimmer 掃光效果
- **Clawd 吉祥物**: ASCII 狐狸吉祥物，支援 4 種姿態動畫
- **全螢幕模式**: F11 切換全螢幕，隱藏側欄擴展主面板
- **會話持久化**: 自動儲存/恢復會話到 `~/.foxcode/sessions/`
- **6 套主題**: dark / light / dark-ansi / light-ansi / dark-daltonized / light-daltonized
- **品牌色**: `#ffd56b` 暖金色
- **對話框系統**: 幫助、確認、權限請求、Diff 檢視器、成本警告

### 命令列選項

| 選項 | 說明 |
|------|------|
| `--model, -m` | 指定 AI 模型（支援別名） |
| `--mode` | 執行模式 (default/build/plan/accept_edits) |
| `--build` | 快捷啟用 Build 模式 |
| `--plan` | 快捷啟用規劃模式 |
| `--resume, -r` | 恢復上次會話 |
| `--session` | 指定會話 ID |
| `--list-sessions` | 列出所有會話 |
| `--config` | 顯示配置 |
| `--debug` | 啟用除錯模式 |
| `--tui` | 啟用 TUI 圖形終端介面 |
| `--no-tui` | 禁用 TUI 介面 |
| `--version, -v` | 顯示版本 |
| `--help, -h` | 顯示幫助 |

### 互動式命令

在互動式會話中，可以使用以下命令：

#### 基本命令

| 命令 | 說明 |
|------|------|
| `/help` | 顯示幫助 |
| `/clear` | 清空對話 |
| `/save` | 儲存會話 |
| `/load <id>` | 載入會話 |
| `/mode <mode>` | 切換模式 |
| `/model <name>` | 切換模型 |
| `/token` | 顯示 Token 使用統計 |
| `/sessions` | 列出會話 |
| `/exit` 或 `/quit` | 退出 |

#### 長時間執行模式命令

| 命令 | 說明 |
|------|------|
| `/init` | 生成專案初始化腳本 |
| `/progress` | 顯示當前進度 |
| `/features [add/complete/list]` | 管理功能列表 |
| `/summary` | 生成會話摘要 |
| `/next` | 取得下一個建議任務 |
| `/long-running [on/off]` | 切換長時間執行模式 |
| `/index` | 構建語義程式碼索引 |
| `/index status` | 檢視索引狀態 |
| `/index update` | 增量更新索引 |
| `/search <query>` | 語義搜尋程式碼 |
| `/kb` | 顯示知識庫狀態 |
| `/kb add <content>` | 添加知識條目 |
| `/kb search <query>` | 搜尋知識庫 |
| `/kb tags` | 列出所有標籤 |
| `/analyze` | 分析當前專案 |
| `/analyze tech` | 分析技術棧 |
| `/analyze quality` | 分析程式碼品質（bug） |
| `/debug start` | 啟動除錯會話 |
| `/debug break <file:line>` | 設定中斷點 |
| `/debug continue` | 繼續執行 |
| `/debug step` | 單步執行 |
| `/debug vars` | 顯示變數 |
| `/profile` | 啟動效能分析 |
| `/profile report` | 檢視分析報告 |
| `/security` | 執行安全掃描（bug） |
| `/security deps` | 掃描依賴漏洞（bug） |
| `/topic` | 顯示當前輸出主題模式 |
| `/topic default` | 切換到預設模式（完整輸出） |
| `/topic debug` | 切換到除錯模式（詳細輸出） |
| `/topic minimalism` | 切換到極簡模式（精簡輸出） |
| `/format [files]` | 格式化程式碼 |
| `/refactor` | 取得重構建議 |
| `/test gen <file>` | 生成測試用例 |
| `/doc gen <file>` | 生成文件 |
| `/git smart-commit` | 智慧提交 |
| `/git conflicts` | 分析衝突 |
| `/diagram <type>` | 生成圖表 (mermaid/plantuml) |

### 配置

配置檔案位置（按優先順序排序）：
1. 專案級: `.foxcode.toml` 或 `foxcode.toml`
2. 使用者級: `~/.foxcode/config.toml`


### 工作流程

FoxCode 提供了標準化的開發工作流程：


設計規劃 → 編碼實現 → 品質評估 → 本地測試 → 合併主分支 → 整合測試 → 推送分支

每個階段都有狀態追蹤：
- 待處理 (pending)
- 進行中 (in_progress)
- 已完成 (completed)
- 失敗 (failed)
- 已跳過 (skipped)
- 已阻塞 (blocked)

### 安全特性

- **沙箱模式**: 支援黑名單/白名單模式限制命令執行
- **命令驗證**: 防止危險的命令注入攻擊
- **敏感資訊過濾**: 自動過濾 API Key 等敏感資訊
- **會話加密**: 支援會話資料加密儲存
- **安全稽核**: 記錄安全事件日誌

### 開發


# 安裝開發依賴
pip install -e ".[dev]"

# 執行測試
foxcode

### 專案結構


src/foxcode/
├── __init__.py              # 套件入口
├── cli.py                   # CLI 入口
│
├── core/                    # 核心模組
│   ├── __init__.py
│   ├── agent.py             # AI 代理
│   ├── config.py            # 配置管理
│   ├── config_validator.py  # 配置驗證
│   ├── providers.py         # 模型提供者
│   ├── session.py           # 會話管理
│   ├── session_encryption.py # 會話加密
│   ├── tasks.py             # 任務管理
│   ├── workflow.py          # 工作流程
│   ├── skill.py             # 技能系統
│   ├── sandbox.py           # 安全沙箱
│   ├── sensitive_masker.py  # 敏感資訊遮蔽
│   ├── progress.py          # 進度管理
│   ├── feature_list.py      # 功能列表
│   ├── handoff.py           # 代理切換
│   ├── evaluator.py         # 評估器
│   ├── orchestrator.py      # 編排器
│   ├── command_manager.py   # 命令管理
│   ├── init_script.py       # 初始化腳本
│   ├── hooks.py             # 鉤子管理
│   ├── work_mode.py         # 工作模式
│   ├── work_mode_config.py  # 工作模式配置
│   ├── open_space.py        # 開放空間
│   ├── process_watchdog.py  # 程序監控
│   ├── updater.py           # 更新器
│   │
│   │── 高級功能模組 ──
│   ├── semantic_index.py    # 語義程式碼索引
│   ├── knowledge_base.py    # 知識庫管理
│   ├── task_planner.py      # 智慧任務規劃
│   ├── project_analyzer.py  # 專案結構分析
│   ├── error_analyzer.py    # 錯誤分析
│   ├── advanced_debugger.py # 高級除錯器
│   ├── performance_analyzer.py # 效能分析
│   ├── security_scanner.py  # 安全掃描
│   ├── code_formatter.py    # 程式碼格式化
│   ├── refactoring_suggester.py # 重構建議
│   ├── dependency_resolver.py # 依賴解析
│   ├── test_generator.py    # 測試生成
│   ├── doc_generator.py     # 文件生成
│   ├── git_advanced_ops.py  # Git 高級操作
│   ├── multimodal_processor.py # 多模態處理
│   ├── enhanced_tools.py    # 增強工具整合
│   │
│   └── hooks/               # 鉤子模組
│       ├── __init__.py
│       ├── base.py          # 鉤子基類
│       ├── app_hooks.py     # 應用鉤子
│       ├── command_hooks.py # 命令鉤子
│       ├── config_hooks.py  # 配置鉤子
│       ├── service_hooks.py # 服務鉤子
│       ├── session_hooks.py # 會話鉤子
│       ├── skill_hooks.py   # 技能鉤子
│       ├── tool_hooks.py    # 工具鉤子
│       └── work_mode_hooks.py # 工作模式鉤子
│
├── commands/                # 命令模組
│   ├── __init__.py
│   ├── command.py           # 命令基類
│   ├── help.py              # 幫助命令
│   ├── prompt.py            # 提示命令
│   └── tool.py              # 工具命令
│
├── tools/                   # 工具模組
│   ├── __init__.py
│   ├── base.py              # 工具基類
│   ├── ai_tools.py          # AI 工具
│   ├── file_tools.py        # 檔案操作
│   ├── shell_tools.py       # Shell 執行
│   ├── code_tools.py        # 程式碼分析
│   ├── mcp_tools.py         # MCP 工具
│   └── playwright_tools.py  # Playwright 工具
│
├── services/                # 服務模組
│   ├── __init__.py
│   ├── mcp.py               # MCP 協議
│   ├── mcp_installer.py     # MCP 安裝器
│   └── api/                 # API 客戶端
│       ├── client.py        # API 客戶端
│       └── unified_client.py # 統一客戶端
│
├── context/                 # 上下文模組
│   ├── __init__.py
│   ├── context_bridge.py    # 上下文橋接
│   ├── context_compressor.py # 上下文壓縮
│   └── context_reset.py     # 上下文重置
│
├── tui/                     # TUI 介面 (Textual)
│   ├── __init__.py
│   ├── app.py               # 主應用入口
│   ├── icons.py             # 公開圖示庫
│   ├── theme.py             # 6 套主題系統
│   ├── styles.tcss          # TCSS 樣式表
│   ├── screens/
│   │   ├── repl.py          # REPL 主屏
│   │   └── welcome.py       # 歡迎屏
│   ├── widgets/
│   │   ├── spinner.py       # Spinner 動畫系統
│   │   ├── logo.py          # Clawd 吉祥物 + Logo
│   │   ├── message.py       # 訊息渲染
│   │   ├── message_list.py  # 虛擬訊息列表
│   │   ├── prompt_input.py  # 多行輸入
│   │   ├── sidebar.py       # 側欄會話列表
│   │   ├── dialog.py        # 對話框系統
│   │   ├── diff_viewer.py   # Diff 檢視器
│   │   ├── permission.py    # 權限請求
│   │   └── cost_dialog.py   # 成本警告
│   └── design_system/
│       ├── divider.py       # 分割線
│       ├── tabs.py          # 選項卡
│       ├── progress.py      # 進度條
│       ├── status_icon.py   # 狀態圖示
│       └── themed_box.py    # 主題容器
│
├── types/                   # 型別定義
│   ├── __init__.py
│   └── message.py           # 訊息型別
│
├── utils/                   # 工具函式
│   ├── __init__.py
│   ├── encoding.py          # 編碼處理
│   └── statistics.py        # 統計資訊
│
├── hooks/                   # 全域鉤子
│   └── __init__.py
│
├── constants/               # 常量定義
│   └── __init__.py
│
├── components/              # 元件模組
│   └── __init__.py
│
└── screens/                 # 螢幕模組
    └── __init__.py

### 環境變數

| 變數名 | 說明 |
|--------|------|
| `OPENAI_API_KEY` | OpenAI API Key |
| `ANTHROPIC_API_KEY` | Anthropic API Key |
| `DEEPSEEK_API_KEY` | DeepSeek API Key |
| `STEP_API_KEY` | Step API Key |
| `FOXCODE_DEBUG` | 啟用除錯模式 |
| `FOXCODE_LOG_LEVEL` | 日誌級別 |

### QFA

Q: 如果你覺得終端內容太多了，怎麼啟用終端極簡模式：

/topic minimalism 

Q: 如何使用本地模型？


foxcode --model local --base-url http://localhost:8000/v1

Q: 如何檢視 Token 使用情況？

在互動式會話中使用 `/token` 命令。

Q: 如何啟用除錯模式？


foxcode --debug

Q: 配置檔案放在哪裡？

專案級配置放在專案根目錄的 `.foxcode.toml`，使用者級配置放在 `~/.foxcode/config.toml`。


### License

AGPLv3 License - 詳見 [LICENSE](LICENSE.txt) 檔案