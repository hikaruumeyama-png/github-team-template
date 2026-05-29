# <!-- TEMPLATE:title -->プロジェクト名<!-- /TEMPLATE:title -->

<!-- TEMPLATE:overview -->
1〜3 行でこのプロジェクトが解決する課題を書く。
<!-- /TEMPLATE:overview -->

## 新しいプロジェクトを立ち上げる

> このセクションはテンプレートから派生リポジトリを作るときの手順です。セットアップが完了したら削除してください。

### このテンプレートが提供するもの

| 機能 | 内容 |
|------|------|
| AI 開発環境 | claude-code-starter-kit を自動インストールして Claude Code をすぐ使える状態に |
| Gemini 連携 | `GEMINI_API_KEY` を Repository Secret に登録。README の `Usage` セクションを Gemini で定期更新 |
| Actions 権限 | GitHub Actions が PR を作成・承認できる権限を付与 |
| ブランチ保護 | `main` への直接 push を禁止（GitHub Pro/Team 以上） |
| CI チェック | TEMPLATE 未記入検出・秘密情報スキャン・脆弱性チェック・シェルスクリプト品質チェック |

### 0. 事前準備（PC に何もない状態から始める場合）

すでにツールが入っている場合はスキップしてよい。

#### 必要なアカウント

| アカウント | 用途 | 取得先 |
|-----------|------|--------|
| GitHub アカウント | リポジトリ作成・コード管理 | https://github.com/signup |
| Gemini API キー | README 自動更新（AI） | https://aistudio.google.com/app/apikey |

#### ツールのインストール（Windows）

PowerShell（管理者権限不要）で順番に実行する:

```powershell
# 1. Git for Windows（Git Bash が同梱される）
winget install Git.Git

# 2. GitHub CLI
winget install GitHub.cli

# 3. uv（Python パッケージマネージャ）
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

> インストール後は **PowerShell を再起動**してから続ける（PATH が更新される）。

#### ツールのインストール（macOS / Linux）

```bash
# macOS: Homebrew が未導入の場合
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install git gh
curl -LsSf https://astral.sh/uv/install.sh | sh

# Linux（apt 系）
sudo apt-get update && sudo apt-get install -y git
sudo apt-get install -y gh   # または https://cli.github.com/ からインストール
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### GitHub 認証（初回のみ）

**Windows Terminal の Git Bash タブ**（または macOS/Linux Terminal）で実行する:

```bash
gh auth login --scopes repo
```

ブラウザが開くので GitHub アカウントでログインし、表示された認証コードを確認して承認する。

---

準備が整ったら **手順 1** に進む。

### 1. リポジトリを作成する

GitHub の **"Use this template"** → **"Create a new repository"** からリポジトリを作成する。

または `gh` CLI を使う場合:

```bash
gh repo create <リポジトリ名> --template <このテンプレートのリポジトリ名> --private
```

### 2. ローカルにクローンする

```bash
gh repo clone <owner>/<リポジトリ名>
cd <リポジトリ名>
```

### 3. セットアップスクリプトを実行する

> **Windows ユーザーへ:** 必ず **Windows Terminal で「Git Bash」タブを開いた中** で実行すること(タブバーの「+」右隣の「∨」→ Git Bash を選択)。PowerShell や cmd、エクスプローラのダブルクリックから `./scripts/setup-derived-repo.sh` を起動すると、Windows のファイル関連付け経由で Git Bash が **別ウィンドウとして起動 → スクリプト終了で即閉じる**ため、エラーも進捗も見えなくなる。
>
> **対話プロンプトの注意:** 著者名・GitHub ハンドル等を空 Enter してもエラーにはならず、対応する TEMPLATE マーカーが**温存**される(CI の `template-check` Job が後で検出する設計)。後から `uv run python -m scripts.init_project --author "..." --handle "..."` で埋め直すこともできる。

```bash
gh auth login --scopes repo   # gh CLI 未認証の場合のみ
./scripts/setup-derived-repo.sh
```

Gemini API キーを入力し、対話形式の質問に答えるだけで以下がすべて完了する:

- claude-code-starter-kit のインストール（未導入の場合）
- `GEMINI_API_KEY` を GitHub Repository Secret に登録
- GitHub Actions の Workflow permissions を設定（write + PR 承認許可）
- `main` ブランチ保護を設定（GitHub Pro/Team 以上で有効）
- プロジェクト名・概要・著者などを入力し、各ファイルのプレースホルダを一括記入
- 開発環境のセットアップ（`uv sync --group dev` + `pre-commit install`）
- 初回コミット & プッシュ

> **GitHub Free プランのプライベートリポジトリ**ではブランチ保護のみ失敗することがある。Gemini Secret と Actions 権限の設定は完了するため AI 開発フローはすぐ使える。

### 4. Claude Code で開発を開始する

以下のプロンプトを Claude Code に貼り付ける（`[ ]` 部分を書き換えること）:

```
このリポジトリは [プロジェクト名] のためのものです。

背景と目的:
[このプロジェクトが解決する課題と、なぜ今作るのかを 3〜5 行で書く]

まず以下のファイルを読んで全体像を把握してください:
- CLAUDE.md（このリポジトリ固有の規約・制約）
- README.md（プロジェクト概要）
- docs/ARCHITECTURE.md（技術スタック・構成）

最初にやってほしいこと:
[具体的な最初のタスク。例: 「ユーザー一覧を取得する API エンドポイントを実装してほしい」]

わからないことは確認してください。
```

---

## Setup

<!-- TEMPLATE:setup -->
### まずこれだけ

事前に必要なもの:

- [uv](https://docs.astral.sh/uv/) — Python パッケージマネージャ（[インストール方法](https://docs.astral.sh/uv/getting-started/installation/)）
- bash が使えるターミナル（Git Bash、macOS Terminal、WSL 等）

```bash
uv sync --group dev
uv run pre-commit install
```
<!-- /TEMPLATE:setup -->

## Usage

<!-- USAGE:START -->
このセクションは `scripts/update_docs.py` で自動更新される。手動編集しないこと。
<!-- USAGE:END -->

## Owners

<!-- TEMPLATE:owners -->
- Primary: @your-github-handle
- Backup: @another-github-handle
- Slack: #your-channel
<!-- /TEMPLATE:owners -->
