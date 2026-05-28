#!/usr/bin/env bash
# このファイルの役割: GitHub API でブランチ保護ルールを一括設定するスクリプト
set -euo pipefail

# ---- argument parsing ----
DRY_RUN=false
REPO=""
BRANCH="main"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --repo)
      REPO="$2"
      shift 2
      ;;
    --branch)
      BRANCH="$2"
      shift 2
      ;;
    -h|--help)
      cat <<EOF
Usage: $0 [--dry-run] [--repo OWNER/NAME] [--branch BRANCH]

Options:
  --dry-run          Print the target URL and JSON payload without applying
  --repo OWNER/NAME  Target repository (default: auto-detected via gh repo view)
  --branch BRANCH    Branch to protect (default: main)
  -h, --help         Show this help message

Examples:
  $0 --dry-run
  $0 --repo my-org/my-repo
  $0 --repo my-org/my-repo --branch develop
EOF
      exit 0
      ;;
    *)
      echo "[ERROR] unknown arg: $1" >&2
      exit 1
      ;;
  esac
done

# ---- preflight ----
command -v gh >/dev/null 2>&1 || {
  echo "[ERROR] gh CLI not found. Install from https://cli.github.com" >&2
  exit 1
}

gh auth status >/dev/null 2>&1 || {
  echo "[ERROR] gh not authenticated. Run: gh auth login --scopes repo" >&2
  exit 1
}

if [[ -z "$REPO" ]]; then
  REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
fi

URL="repos/${REPO}/branches/${BRANCH}/protection"

# ---- payload ----
read -r -d '' PAYLOAD <<'ENDJSON' || true
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["lint", "type-check", "test", "secret-scan", "dep-scan", "shellcheck"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
ENDJSON

# ---- dry-run ----
if $DRY_RUN; then
  echo "[DRY-RUN] PUT ${URL}"
  echo "$PAYLOAD"
  exit 0
fi

# ---- apply ----
echo "[INFO] Applying branch protection to ${REPO}@${BRANCH}..."

GH_ERROR_FILE=$(mktemp)
trap 'rm -f "$GH_ERROR_FILE"' EXIT

if ! echo "$PAYLOAD" | gh api -X PUT "$URL" \
  -H "Accept: application/vnd.github+json" \
  --input - \
  >/dev/null 2>"$GH_ERROR_FILE"; then
  ERROR_BODY=$(cat "$GH_ERROR_FILE")
  if echo "$ERROR_BODY" | grep -qiE "Upgrade to GitHub Pro|private repositories.*Free"; then
    echo "[ERROR] Branch protection on private repos requires GitHub Pro/Team/Enterprise." >&2
    echo "        Options:" >&2
    echo "          1. Upgrade the account plan" >&2
    echo "          2. Make the repository public (Settings → Danger Zone)" >&2
    echo "          3. Use repository rulesets instead (Settings → Rules → Rulesets)" >&2
    exit 1
  elif echo "$ERROR_BODY" | grep -qiE "403|Must have admin|Resource not accessible"; then
    echo "[ERROR] Permission denied. Need 'repo' scope on token AND admin access to repo." >&2
    echo "        If this is a private repo on the Free plan, see GitHub docs:" >&2
    echo "        https://docs.github.com/en/get-started/learning-about-github/githubs-plans" >&2
    exit 1
  elif echo "$ERROR_BODY" | grep -qiE "404|Not Found"; then
    echo "[ERROR] Repo or branch not found. Have you pushed at least one commit to ${BRANCH}?" >&2
    exit 1
  else
    echo "[ERROR] API call failed:" >&2
    echo "$ERROR_BODY" >&2
    exit 1
  fi
fi

echo "[OK] Branch protection applied. Verifying..."
gh api "$URL" -q \
  '"Required checks: " + (.required_status_checks.contexts | join(", "))'
