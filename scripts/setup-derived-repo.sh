#!/usr/bin/env bash
# このファイルの役割: 派生テンプレートリポを AI 開発レディ化する bootstrap スクリプト
# (GEMINI_API_KEY 登録 + Actions Workflow permissions + ブランチ保護を 1 コマンドで実施)
set -euo pipefail

DRY_RUN=0

usage() {
  printf '%s\n' \
    "Usage: ./scripts/setup-derived-repo.sh [--dry-run] [-h|--help]" \
    "" \
    "Bootstrap a derived template repository for AI-assisted development." \
    "" \
    "Steps:" \
    "  [1/3] Register local GEMINI_API_KEY as a GitHub repository Secret" \
    "  [2/3] Enable Actions Workflow permissions (write + PR approval)" \
    "  [3/3] Apply main branch protection (chains setup-branch-protection.sh)" \
    "" \
    "Requirements:" \
    "  - Run from inside a git repository with a GitHub origin remote" \
    "  - gh CLI authenticated (gh auth status)" \
    "  - GEMINI_API_KEY env var set locally (temporary Free-plan bootstrap)" \
    "" \
    "Options:" \
    "  --dry-run    Print planned actions without making API calls" \
    "  -h, --help   Show this help and exit"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Error: unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

# ---- precondition checks ----

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Error: not inside a git repository" >&2
  exit 1
fi

ORIGIN_URL="$(git remote get-url origin 2>/dev/null || true)"
# Match: https://github.com/OWNER/REPO(.git)? OR git@github.com:OWNER/REPO(.git)?
# We capture REPO greedily then strip the optional .git suffix via parameter
# expansion. Bash ERE has no non-greedy modifier, so trying to express the
# .git as an optional regex group fails on dotted repo names like "my.config".
if [[ "$ORIGIN_URL" =~ github\.com[:/]([^/]+)/([^/]+)$ ]]; then
  OWNER="${BASH_REMATCH[1]}"
  REPO_NAME="${BASH_REMATCH[2]%.git}"
  REPO="$OWNER/$REPO_NAME"
else
  echo "Error: cannot parse owner/repo from git remote origin: '$ORIGIN_URL'" >&2
  echo "Expected: https://github.com/OWNER/REPO.git or git@github.com:OWNER/REPO.git" >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "Error: gh not authenticated. Run: gh auth login --scopes repo" >&2
  exit 1
fi

if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  if [[ -t 0 ]]; then
    read -rsp "GEMINI_API_KEY: " GEMINI_API_KEY
    echo
    export GEMINI_API_KEY
  fi
  if [[ -z "${GEMINI_API_KEY:-}" ]]; then
    echo "Error: GEMINI_API_KEY not set." >&2
    echo "Temporary Free-plan setup: set GEMINI_API_KEY in your shell before running this script." >&2
    echo 'Example: read -rsp "GEMINI_API_KEY: " GEMINI_API_KEY; export GEMINI_API_KEY; echo' >&2
    echo "Future GitHub Organization setup can replace this with an organization secret." >&2
    exit 1
  fi
fi

# ---- main steps ----

# Resolve SCRIPT_DIR without external `dirname`: try forward-slash strip first
# (POSIX paths), then fall back to backslash strip (Windows paths passed to bash).
SCRIPT_DIR="${BASH_SOURCE[0]%/*}"
if [[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]]; then
  # No forward slash found — Windows-style path (e.g. C:\scripts\foo.sh)
  SCRIPT_DIR="${BASH_SOURCE[0]%\\*}"
fi
if [[ "$SCRIPT_DIR" == "${BASH_SOURCE[0]}" ]]; then
  # No separator at all — script is in current directory
  SCRIPT_DIR="."
fi

_starterkit_installed() {
  local f="$HOME/.claude/CLAUDE.md"
  [[ -f "$f" ]] && grep -q "BEGIN STARTER-KIT-MANAGED" "$f"
}

if [[ -t 0 && $DRY_RUN -eq 0 ]]; then
  if ! _starterkit_installed; then
    echo ""
    echo "claude-code-starter-kit が未インストールです。"
    read -rp "Standard プロファイルで自動インストールしますか？ [Y/n]: " _SK_CONFIRM
    case "${_SK_CONFIRM:-Y}" in
      [Nn]*) echo "スキップしました。後から手動でインストールできます: https://github.com/cloudnative-co/claude-code-starter-kit" ;;
      *)
        echo "インストール中..."
        curl -fsSL "https://raw.githubusercontent.com/cloudnative-co/claude-code-starter-kit/main/install.sh" \
          | bash -s -- --non-interactive --language=ja
        ;;
    esac
  fi
fi

if [[ -t 0 && $DRY_RUN -eq 0 ]]; then
  echo ""
  echo "以下を $REPO に設定します:"
  echo "  [1/3] GEMINI_API_KEY → Repository Secret に登録"
  echo "  [2/3] Actions Workflow permissions → write + PR 承認許可"
  echo "  [3/3] main ブランチ保護 (setup-branch-protection.sh に委譲)"
  echo ""
  read -rp "実行しますか？ [Y/n]: " _CONFIRM
  case "${_CONFIRM:-Y}" in
    [Nn]*) echo "中断しました。"; exit 0 ;;
  esac
  echo ""
fi

if [[ $DRY_RUN -eq 1 ]]; then
  echo "[DRY-RUN] [1/3] Would: printf '%s' \"\$GEMINI_API_KEY\" | gh secret set GEMINI_API_KEY --repo $REPO"
  echo "[DRY-RUN] [2/3] Would: gh api -X PUT repos/$REPO/actions/permissions/workflow -f default_workflow_permissions=write -F can_approve_pull_request_reviews=true"
  echo "[DRY-RUN] [3/3] Delegating to: $SCRIPT_DIR/setup-branch-protection.sh --dry-run"
  "$SCRIPT_DIR/setup-branch-protection.sh" --dry-run
  if grep -q "TEMPLATE:title" README.md 2>/dev/null; then
    echo ""
    echo "[DRY-RUN] [init] Would prompt for: project name, overview, author, GitHub handle, Slack channel"
    echo "[DRY-RUN] [init] Would fill TEMPLATE markers in: README.md, LICENSE, CODEOWNERS, docs/ARCHITECTURE.md, CLAUDE.md"
    echo "[DRY-RUN] [init] Would delete: docs/superpowers/, PROJECT_BRIEF.md"
    echo "[DRY-RUN] [init] Would run: uv sync --group dev && uv run pre-commit install"
    echo "[DRY-RUN] [init] Would commit and push: chore: initialize project from template"
  fi
  exit 0
fi

echo "[1/3] Registering local GEMINI_API_KEY as GitHub Secret on $REPO"
printf '%s' "$GEMINI_API_KEY" \
  | gh secret set GEMINI_API_KEY --repo "$REPO"

echo "[2/3] Enabling Actions Workflow permissions (write + PR approval) on $REPO"
gh api -X PUT "repos/$REPO/actions/permissions/workflow" \
  -f default_workflow_permissions=write \
  -F can_approve_pull_request_reviews=true \
  --silent

echo "[3/3] Applying branch protection"
if ! "$SCRIPT_DIR/setup-branch-protection.sh"; then
  echo "[WARN] ブランチ保護の設定に失敗しました。GitHub Free プランの場合は想定内です。" >&2
  echo "       Step 1/2 は完了済みのため、AI 開発フローは使えます。" >&2
fi

echo ""
echo "GitHub 設定が完了しました。"

# ---- project init (steps 4-7): run only on first setup when TEMPLATE markers remain ----
if [[ -t 0 ]] && grep -q "TEMPLATE:title" README.md 2>/dev/null; then
  echo ""
  echo "────────────────────────────────────────"
  echo "プロジェクト情報を入力してください"
  echo "────────────────────────────────────────"
  # _strip_escapes: remove VT100 cursor-key sequences captured by `read`
  # when bash is launched from PowerShell without a proper PTY.
  _strip_escapes() { printf '%s' "$1" | sed 's/\x1b\[[0-9;]*[A-Za-z]//g; s/\[[0-9;]*[A-Za-z]//g'; }

  read -rp "プロジェクト名: " _PROJ_NAME;      _PROJ_NAME="$(_strip_escapes "$_PROJ_NAME")"
  read -rp "概要（1行）: " _PROJ_OVERVIEW;      _PROJ_OVERVIEW="$(_strip_escapes "$_PROJ_OVERVIEW")"
  read -rp "著者名（LICENSE の著作権者）: " _PROJ_AUTHOR;  _PROJ_AUTHOR="$(_strip_escapes "$_PROJ_AUTHOR")"
  read -rp "GitHub ハンドル（@ なし）: " _PROJ_HANDLE;    _PROJ_HANDLE="$(_strip_escapes "$_PROJ_HANDLE")"
  read -rp "Slack チャンネル（使わない場合は空 Enter）: " _PROJ_SLACK; _PROJ_SLACK="$(_strip_escapes "$_PROJ_SLACK")"

  echo ""
  echo "ファイルを書き換えています..."
  uv run python -m scripts.init_project \
    --name "$_PROJ_NAME" \
    --overview "$_PROJ_OVERVIEW" \
    --author "$_PROJ_AUTHOR" \
    --handle "$_PROJ_HANDLE" \
    --slack "$_PROJ_SLACK"

  echo "不要なファイルを削除しています..."
  rm -rf docs/superpowers/ PROJECT_BRIEF.md

  echo "開発環境をセットアップしています..."
  uv sync --group dev
  uv run pre-commit install || echo "[WARN] pre-commit install failed. Run manually: uv run pre-commit install"

  echo ""
  read -rp "変更を git コミットしてプッシュしますか？ [Y/n]: " _COMMIT_CONFIRM
  case "${_COMMIT_CONFIRM:-Y}" in
    [Nn]*) echo "スキップしました。準備できたら git add / commit / push してください。" ;;
    *)
      git add -A
      git commit -m "chore: initialize project from template"
      git push
      echo ""
      echo "完了しました！Claude Code を起動して開発を始めましょう。"
      ;;
  esac
fi
