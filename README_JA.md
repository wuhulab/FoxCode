# FoxCode | 日本語

[简体中文](README.md) | [English](README_EN.md) | [日本語](README_JA.md)

**次世代AIターミナルコーディングアシスタント**

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19433875.svg)](https://zenodo.org/records/19433875)

### スポンサー

[便利で安いAPI集約サイト](https://ai-api2.shunx.top/)

### コントリビューション

#### FoxCodeへのコントリビューションを歓迎します！以下の方法で貢献できます：

1. **コードの貢献**: 新機能の提案、バグの修正、コードの最適化

2. **ドキュメントの貢献**: ユーザーマニュアル、開発ガイド、APIドキュメントなどの作成

3. **Issue管理**: GitHub Issueの管理、バグ修正、パフォーマンス最適化、新機能追加など

#### コントリビューションの方法

**ローカルにクローン**: フォークしたリポジトリをローカルにクローン

**新しいブランチを作成**: ローカルに新しいブランチを作成し、コントリビューション用に準備

**コントリビューションを提出**: ブランチで作業を行い、フォークしたリポジトリにプッシュ

**プルリクエストを作成**: FoxCodeリポジトリにプルリクエストを作成し、変更内容を説明

#### できること

1. コードの貢献（新機能、バグ修正、コード最適化）— 長期計画
2. 多言語ドキュメントの作成 — 長期計画
3. Issue管理（GitHub Issueの管理、バグ修正、パフォーマンス最適化）— 長期計画

#### コントリビューター報酬プログラム

5月にスポンサーAPIサイトを配布する予定です。有用なコントリビューションを行った方にはポイントを付与し、報酬を提供します。

### 開発ノート

1. `pyproject.toml` のバージョン番号を更新
2. `__init__.py` のバージョン番号を更新
3. Actionsのタグ付け

### ニュース

#### 2026年

- **4.8** shunian: FoxCode起動時の自動更新チェック機能を実装 ✅
- **4.8** shunian: プロジェクト完了後に反省点を記録し、次回のコンテキストに追加することで効率向上とエラー削減 ✅
- **4.6** shunian: `/mcp url` でMCPを直接インストール可能に。MCPの発展を促進 ✅

### 注意事項

FoxCodeはAGPLv3に準拠していますが、本ソフトウェアのコードを変更しない限りAGPLv3は適用されません。

### はじめに

FoxCodeはPythonで書かれたターミナルCLIのAIコーディングアシスタントです。複数のAIモデルをサポートし、インテリジェントなコード生成、ファイル操作、タスク計画、ワークフロー管理などの機能を提供し、開発者のコーディング効率を向上させます。

### 特徴

#### コア機能

- **マルチモデル対応**: OpenAI、Anthropic Claude、DeepSeek、Step、ローカルモデル
- **ファイル操作**: ファイルの読み取り、書き込み、編集、検索
- **シェル実行**: ターミナルでの安全なコマンド実行
- **タスク計画**: 複雑なタスクの実行フロー管理
- **ワークフロー管理**: 標準化された開発ワークフロー（設計→コーディング→テスト→マージ→プッシュ）
- **スキルシステム**: 動的ロードに対応した拡張可能なスキルフレームワーク
- **MCPプロトコル**: Model Context Protocolに対応し、外部ツールと連携
- **セキュリティサンドボックス**: 設定可能なコマンド実行セキュリティポリシー
- **対話型インターフェース**: モダンなTUIターミナルインターフェース
- **セッション管理**: 暗号化対応の会話履歴の保存・復元
- **複数の実行モード**: デフォルト、Build、計画モード、自動編集承認モード
- **セマンティックコードインデックス**: ベクトル埋め込みに基づくコードセマンティック検索、インクリメンタル更新と依存関係グラフ生成
- **知識ベース管理**: セッションをまたいだ知識保存、カテゴリ分類、タグ付け、セマンティック検索
- **コンテキスト圧縮**: インテリジェントな会話圧縮と知識蒸留、長い会話の最適化
- **インテリジェントタスク計画**: 自動タスク分解、依存関係分析、トポロジカルソート
- **プロジェクト構造分析**: 自動技術スタック検出、コード品質スコアリング、アーキテクチャパターン認識
- **エラー分析**: インテリジェントなエラー解析、根本原因分析、修正提案
- **高度なデバッグ**: 条件付きブレークポイント、ログブレークポイント、変数ウォッチ、コールスタック分析
- **パフォーマンス分析**: 実行時間分析、メモリ追跡、ボトルネック特定
- **セキュリティスキャン**: 脆弱性検出、機密情報スキャン、依存関係セキュリティチェック
- **コードフォーマッティング**: 多言語コードフォーマット（Python、JavaScript、TypeScriptなど）
- **リファクタリング提案**: コードの悪臭検出、デザインパターン提案、リファクタリング計画
- **依存関係解決**: Python/Node.jsの依存関係分析と競合検出
- **テスト生成**: pytestスタイルのテスト生成、境界ケース、TDD対応
- **ドキュメント生成**: APIドキュメント、docstring、READMEの自動生成
- **Git高度な操作**: スマートコミット、競合解決、ブランチ管理
- **マルチモーダル処理**: 画像分析、Mermaid/PlantUML図表生成

### インストール

```bash
pip install foxcode
```

### クイックスタート

```bash
# 対話型セッションを開始 (CLIモード)
foxcode

# TUIターミナルインターフェースを起動
foxcode --tui

# Pythonから直接TUIを起動
python -c "from foxcode.tui import run_tui; run_tui()"

# 直接質問
foxcode "プロジェクトの構造を分析してください"

# Buildモード（自動実行）
foxcode --build "Flaskアプリケーションを作成してください"

# 計画モード（読み取り専用）
foxcode --plan "コードベースのセキュリティ問題を分析してください"

# モデルを指定
foxcode -m claude "このコードをリファクタリングしてください"

# 前回のセッションを復元
foxcode -r
```

### TUIターミナルインターフェース

FoxCodeはTextualベースのフル機能TUI（ターミナルユーザーインターフェース）を提供し、Claude Codeの対話体験を1:1で再現します。

#### TUIキーボードショートカット

| ショートカット | 動作 |
|---------------|------|
| `Enter` | メッセージ送信 |
| `Shift+Enter` | 改行 |
| `Ctrl+L` | 画面クリア |
| `Ctrl+N` | 新規セッション |
| `Ctrl+S` | セッション保存 |
| `Ctrl+B` | サイドバー切替 |
| `Ctrl+T` | モード切替 (build/plan/accept) |
| `F1 / ?` | ヘルプ |
| `F11` | 全画面切替 |
| `PageUp / PageDown` | 上下スクロール |
| `Ctrl+A` | 全選択 |
| `Ctrl+E` | カーソルを行末へ |
| `Ctrl+K` | 行末まで削除 |
| `Ctrl+W` | 単語削除 |
| `Ctrl+U` | 行クリア |
| `Esc` | キャンセル |
| `Ctrl+C` | 入力ボックスのみ終了（チャットエリアでは終了しない、コピー用） |
| `Ctrl+Q` | FoxCode終了 |
| `Ctrl+Y` | 最後のAI応答をコピー（通知なし） |
| `C` | 選択中のメッセージをコピー（メッセージをクリックして選択） |
| `D` | 選択中のメッセージを削除 |

#### TUIスラッシュコマンド（ローカルコマンド、AIには送信されない）

`/` で始まる入力は、AIエージェントに送信されず、ローカルコマンドとして実行されます。AIが出力中でも即座に実行されます。

**コマンド解決順序：**
1. まずTUI内蔵コマンドを検索（下表参照）
2. TUIで認識できない場合、コマンドをそのままCLIコマンドハンドラ（`cli._handle_command`）に転送
3. TUIとCLIの両方で認識できない場合のみ、チャットエリアに「不明なコマンド」と表示

| TUI内蔵コマンド | 説明 |
|----------------|------|
| `/help` | TUIコマンド一覧を表示 |
| `/clear` | チャットをクリア（出力中の場合はキャンセル） |
| `/save` | 現在のセッションを保存 |
| `/mode [name]` | 実行モードを設定：`build` / `plan` / `accept_edits` |
| `/new` | 新規セッションを開始（出力中の場合はキャンセル） |
| `/sidebar` | サイドバー切替 |
| `/fullscreen` または `/fs` | 全画面切替 |
| `/theme [name]` | テーマ切替（dark / light / dark-ansi / light-ansi / dark-daltonized / light-daltonized） |
| `/history` | 入力履歴を表示 |
| `/quit` または `/exit` | FoxCodeを終了 |
| `//text` | `/` で始まるリテラルメッセージをAIに送信 |

> その他すべての `/コマンド` はCLIに転送されます。CLIの出力はキャプチャされチャットエリアに表示されます（TUIはCLIの `console` を一時的にリダイレクトし、ターミナルUIを破損しません）。

#### TUIの特徴

- **複数行入力**: Shift+Enterで改行可能なTextArea
- **コマンド履歴**: Up/Downキーで履歴ナビゲーション
- **メッセージ操作バー**: メッセージ選択後にE=編集/C=コピー/D=削除/J=ジャンプ
- **アニメーションSpinner**: Linux標準の `-/\\|` 回転アニメーション、停止検出とGlimmerスイープエフェクト
- **Clawdマスコット**: ASCIIアートのキツネマスコット、4種類のポーズアニメーション
- **全画面モード**: F11で切替、サイドバーを非表示にしてメインパネルを拡張
- **セッション永続化**: `~/.foxcode/sessions/` に自動保存・復元
- **6つのテーマ**: dark / light / dark-ansi / light-ansi / dark-daltonized / light-daltonized
- **ブランドカラー**: `#ffd56b` ウォームゴールド
- **ダイアログシステム**: ヘルプ、確認、権限リクエスト、Diffビューア、コスト警告

### コマンドラインオプション

| オプション | 説明 |
|-----------|------|
| `--model, -m` | AIモデルを指定（エイリアス対応） |
| `--mode` | 実行モード (default/build/plan/accept_edits) |
| `--build` | Buildモードをクイック有効化 |
| `--plan` | 計画モードをクイック有効化 |
| `--resume, -r` | 前回のセッションを復元 |
| `--session` | セッションIDを指定 |
| `--list-sessions` | 全セッションを一覧表示 |
| `--config` | 設定を表示 |
| `--debug` | デバッグモードを有効化 |
| `--tui` | TUIターミナルインターフェースを有効化 |
| `--no-tui` | TUIインターフェースを無効化 |
| `--version, -v` | バージョンを表示 |
| `--help, -h` | ヘルプを表示 |

### 対話型コマンド

対話型セッションでは、以下のコマンドを使用できます：

#### 基本コマンド

| コマンド | 説明 |
|---------|------|
| `/help` | ヘルプを表示 |
| `/clear` | 会話をクリア |
| `/save` | セッションを保存 |
| `/load <id>` | セッションをロード |
| `/mode <mode>` | モードを切替 |
| `/model <name>` | モデルを切替 |
| `/token` | トークン使用統計を表示 |
| `/sessions` | セッション一覧 |
| `/exit` または `/quit` | 終了 |

#### 長時間実行モードコマンド

| コマンド | 説明 |
|---------|------|
| `/init` | プロジェクト初期化スクリプトを生成 |
| `/progress` | 現在の進捗を表示 |
| `/features [add/complete/list]` | 機能リストを管理 |
| `/summary` | セッションサマリーを生成 |
| `/next` | 次の推奨タスクを取得 |
| `/long-running [on/off]` | 長時間実行モードを切替 |
| `/index` | セマンティックコードインデックスを構築 |
| `/index status` | インデックス状態を確認 |
| `/index update` | インデックスをインクリメンタル更新 |
| `/search <query>` | コードをセマンティック検索 |
| `/kb` | 知識ベースの状態を表示 |
| `/kb add <content>` | 知識エントリを追加 |
| `/kb search <query>` | 知識ベースを検索 |
| `/kb tags` | 全タグを一覧表示 |
| `/analyze` | 現在のプロジェクトを分析 |
| `/analyze tech` | 技術スタックを分析 |
| `/analyze quality` | コード品質を分析 |
| `/debug start` | デバッグセッションを開始 |
| `/debug break <file:line>` | ブレークポイントを設定 |
| `/debug continue` | 実行を継続 |
| `/debug step` | ステップ実行 |
| `/debug vars` | 変数を表示 |
| `/profile` | パフォーマンス分析を開始 |
| `/profile report` | 分析レポートを表示 |
| `/security` | セキュリティスキャンを実行 |
| `/security deps` | 依存関係の脆弱性をスキャン |
| `/topic` | 現在の出力トピックモードを表示 |
| `/topic default` | デフォルトモードに切替（完全出力） |
| `/topic debug` | デバッグモードに切替（詳細出力） |
| `/topic minimalism` | ミニマルモードに切替（簡潔出力） |
| `/format [files]` | コードをフォーマット |
| `/refactor` | リファクタリング提案を取得 |
| `/test gen <file>` | テストケースを生成 |
| `/doc gen <file>` | ドキュメントを生成 |
| `/git smart-commit` | スマートコミット |
| `/git conflicts` | 競合を分析 |
| `/diagram <type>` | 図表を生成 (mermaid/plantuml) |

### 設定

設定ファイルの場所（優先順位順）：
1. プロジェクトレベル: `.foxcode.toml` または `foxcode.toml`
2. ユーザーレベル: `~/.foxcode/config.toml`

### ワークフロー

FoxCodeは標準化された開発ワークフローを提供します：

```
設計計画 → コーディング実装 → 品質評価 → ローカルテスト → メインブランチにマージ → 統合テスト → ブランチプッシュ
```

各ステージにはステータストラッキングがあります：
- 未処理 (pending)
- 進行中 (in_progress)
- 完了 (completed)
- 失敗 (failed)
- スキップ (skipped)
- ブロック (blocked)

### セキュリティ機能

- **サンドボックスモード**: ブラックリスト/ホワイトリストモードでコマンド実行を制限
- **コマンド検証**: 危険なコマンドインジェクション攻撃を防止
- **機密情報フィルタリング**: APIキーなどの機密情報を自動フィルタリング
- **セッション暗号化**: セッションデータの暗号化保存をサポート
- **セキュリティ監査**: セキュリティイベントログを記録

### 開発

```bash
# 開発依存関係をインストール
pip install -e ".[dev]"

# テストを実行
foxcode
```

### プロジェクト構造

```
src/foxcode/
├── __init__.py              # パッケージエントリ
├── cli.py                   # CLIエントリ
│
├── core/                    # コアモジュール
│   ├── __init__.py
│   ├── agent.py             # AIエージェント
│   ├── config.py            # 設定管理
│   ├── config_validator.py  # 設定検証
│   ├── providers.py         # モデルプロバイダー
│   ├── session.py           # セッション管理
│   ├── session_encryption.py # セッション暗号化
│   ├── tasks.py             # タスク管理
│   ├── workflow.py          # ワークフロー
│   ├── skill.py             # スキルシステム
│   ├── sandbox.py           # セキュリティサンドボックス
│   ├── sensitive_masker.py  # 機密情報マスキング
│   ├── progress.py          # 進捗管理
│   ├── feature_list.py      # 機能リスト
│   ├── handoff.py           # エージェントハンドオフ
│   ├── evaluator.py         # 評価器
│   ├── orchestrator.py      # オーケストレーター
│   ├── command_manager.py   # コマンド管理
│   ├── init_script.py       # 初期化スクリプト
│   ├── hooks.py             # フック管理
│   ├── work_mode.py         # ワークモード
│   ├── work_mode_config.py  # ワークモード設定
│   ├── open_space.py        # オープンスペース
│   ├── process_watchdog.py  # プロセス監視
│   ├── updater.py           # アップデーター
│   │
│   │── 高度な機能モジュール ──
│   ├── semantic_index.py    # セマンティックコードインデックス
│   ├── knowledge_base.py    # 知識ベース管理
│   ├── task_planner.py      # インテリジェントタスク計画
│   ├── project_analyzer.py  # プロジェクト構造分析
│   ├── error_analyzer.py    # エラー分析
│   ├── advanced_debugger.py # 高度なデバッガー
│   ├── performance_analyzer.py # パフォーマンス分析
│   ├── security_scanner.py  # セキュリティスキャン
│   ├── code_formatter.py    # コードフォーマッター
│   ├── refactoring_suggester.py # リファクタリング提案
│   ├── dependency_resolver.py # 依存関係解決
│   ├── test_generator.py    # テスト生成
│   ├── doc_generator.py     # ドキュメント生成
│   ├── git_advanced_ops.py  # Git高度な操作
│   ├── multimodal_processor.py # マルチモーダル処理
│   ├── enhanced_tools.py    # 拡張ツール統合
│   │
│   └── hooks/               # フックモジュール
│       ├── __init__.py
│       ├── base.py          # フック基底クラス
│       ├── app_hooks.py     # アプリフック
│       ├── command_hooks.py # コマンドフック
│       ├── config_hooks.py  # 設定フック
│       ├── service_hooks.py # サービスフック
│       ├── session_hooks.py # セッションフック
│       ├── skill_hooks.py   # スキルフック
│       ├── tool_hooks.py    # ツールフック
│       └── work_mode_hooks.py # ワークモードフック
│
├── commands/                # コマンドモジュール
│   ├── __init__.py
│   ├── command.py           # コマンド基底クラス
│   ├── help.py              # ヘルプコマンド
│   ├── prompt.py            # プロンプトコマンド
│   └── tool.py              # ツールコマンド
│
├── tools/                   # ツールモジュール
│   ├── __init__.py
│   ├── base.py              # ツール基底クラス
│   ├── ai_tools.py          # AIツール
│   ├── file_tools.py        # ファイル操作
│   ├── shell_tools.py       # シェル実行
│   ├── code_tools.py        # コード分析
│   ├── mcp_tools.py         # MCPツール
│   └── playwright_tools.py  # Playwrightツール
│
├── services/                # サービスモジュール
│   ├── __init__.py
│   ├── mcp.py               # MCPプロトコル
│   ├── mcp_installer.py     # MCPインストーラー
│   └── api/                 # APIクライアント
│       ├── client.py        # APIクライアント
│       └── unified_client.py # 統一クライアント
│
├── context/                 # コンテキストモジュール
│   ├── __init__.py
│   ├── context_bridge.py    # コンテキストブリッジ
│   ├── context_compressor.py # コンテキスト圧縮
│   └── context_reset.py     # コンテキストリセット
│
├── tui/                     # TUIインターフェース (Textual)
│   ├── __init__.py
│   ├── app.py               # メインアプリエントリ
│   ├── icons.py             # 公開アイコンライブラリ
│   ├── theme.py             # 6テーマシステム
│   ├── styles.tcss          # TCSSスタイルシート
│   ├── screens/
│   │   ├── repl.py          # REPLメイン画面
│   │   └── welcome.py       # ウェルカム画面
│   ├── widgets/
│   │   ├── spinner.py       # スピナーアニメーションシステム
│   │   ├── logo.py          # Clawdマスコット + ロゴ
│   │   ├── message.py       # メッセージレンダリング
│   │   ├── message_list.py  # 仮想メッセージリスト
│   │   ├── prompt_input.py  # 複数行入力
│   │   ├── sidebar.py       # サイドバーセッションリスト
│   │   ├── dialog.py        # ダイアログシステム
│   │   ├── diff_viewer.py   # Diffビューア
│   │   ├── permission.py    # 権限リクエスト
│   │   └── cost_dialog.py   # コスト警告
│   └── design_system/
│       ├── divider.py       # 区切り線
│       ├── tabs.py          # タブ
│       ├── progress.py      # プログレスバー
│       ├── status_icon.py   # ステータスアイコン
│       └── themed_box.py    # テーマコンテナ
│
├── types/                   # 型定義
│   ├── __init__.py
│   └── message.py           # メッセージ型
│
├── utils/                   # ユーティリティ関数
│   ├── __init__.py
│   ├── encoding.py          # エンコーディング処理
│   └── statistics.py        # 統計情報
│
├── hooks/                   # グローバルフック
│   └── __init__.py
│
├── constants/               # 定数定義
│   └── __init__.py
│
├── components/              # コンポーネントモジュール
│   └── __init__.py
│
└── screens/                 # 画面モジュール
    └── __init__.py
```

### 環境変数

| 変数名 | 説明 |
|--------|------|
| `OPENAI_API_KEY` | OpenAI API Key |
| `ANTHROPIC_API_KEY` | Anthropic API Key |
| `DEEPSEEK_API_KEY` | DeepSeek API Key |
| `STEP_API_KEY` | Step API Key |
| `FOXCODE_DEBUG` | デバッグモードを有効化 |
| `FOXCODE_LOG_LEVEL` | ログレベル |

### FAQ

Q: ターミナルの出力が多すぎる場合、ミニマルモードを有効にするには？

`/topic minimalism`

Q: ローカルモデルを使用するには？

```bash
foxcode --model local --base-url http://localhost:8000/v1
```

Q: トークン使用状況を確認するには？

対話型セッションで `/token` コマンドを使用します。

Q: デバッグモードを有効にするには？

```bash
foxcode --debug
```

Q: 設定ファイルはどこに置くべきですか？

プロジェクトレベルの設定はプロジェクトルートの `.foxcode.toml`、ユーザーレベルの設定は `~/.foxcode/config.toml` に配置します。

### ライセンス

AGPLv3 License - 詳細は [LICENSE](LICENSE.txt) ファイルを参照してください