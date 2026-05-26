"""Initialize a derived repository from the template by filling TEMPLATE markers.

Usage:
    uv run python -m scripts.init_project \\
        --name "My Project" \\
        --overview "One-line description" \\
        --author "Author Name" \\
        --handle "github-username" \\
        [--slack "#channel"]
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Low-level marker helpers
# ---------------------------------------------------------------------------


def _replace_block(text: str, marker: str, replacement: str) -> str:
    """Replace <!-- TEMPLATE:marker -->...<!-- /TEMPLATE:marker --> with replacement."""
    pattern = rf"<!-- TEMPLATE:{re.escape(marker)} -->.*?<!-- /TEMPLATE:{re.escape(marker)} -->"
    return re.sub(pattern, replacement, text, flags=re.DOTALL)


def _strip_markers(text: str, marker: str) -> str:
    """Remove TEMPLATE marker tags but keep the content between them."""
    text = re.sub(rf"<!-- TEMPLATE:{re.escape(marker)} -->\n?", "", text)
    text = re.sub(rf"<!-- /TEMPLATE:{re.escape(marker)} -->\n?", "", text)
    return text


def _clear_block(text: str, marker: str) -> str:
    """Remove TEMPLATE marker tags AND the placeholder content between them."""
    pattern = rf"\n\n<!-- TEMPLATE:{re.escape(marker)} -->.*?<!-- /TEMPLATE:{re.escape(marker)} -->"
    return re.sub(pattern, "", text, flags=re.DOTALL)


# ---------------------------------------------------------------------------
# Per-file edit functions
# ---------------------------------------------------------------------------


def edit_readme(path: Path, name: str, overview: str, handle: str, slack: str) -> None:
    text = path.read_text(encoding="utf-8")
    text = _replace_block(text, "title", name)
    text = _replace_block(text, "overview", overview)
    text = _strip_markers(text, "setup")
    owners_lines = [f"- Primary: @{handle}", f"- Backup: @{handle}"]
    if slack:
        owners_lines.append(f"- Slack: {slack}")
    text = _replace_block(text, "owners", "\n".join(owners_lines))
    # Remove the onboarding "新しいプロジェクトを立ち上げる" section (up to next ## heading)
    text = re.sub(
        r"\n\n## 新しいプロジェクトを立ち上げる\n.*?(?=\n\n## )",
        "",
        text,
        flags=re.DOTALL,
    )
    path.write_text(text, encoding="utf-8")


def edit_license(path: Path, year: str, author: str) -> None:
    text = path.read_text(encoding="utf-8")
    text = _replace_block(text, "license-year", year)
    text = _replace_block(text, "license-holder", author)
    path.write_text(text, encoding="utf-8")


def edit_codeowners(path: Path, handle: str) -> None:
    text = path.read_text(encoding="utf-8")
    text = text.replace("@your-org/team-name", f"@{handle}")
    text = text.replace("@your-org/devops", f"@{handle}")
    path.write_text(text, encoding="utf-8")


def edit_architecture(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for marker in ("context", "components", "dataflow", "dependencies", "ops"):
        text = _clear_block(text, marker)
    path.write_text(text, encoding="utf-8")


def edit_claude_md(path: Path, handle: str, slack: str) -> None:
    text = path.read_text(encoding="utf-8")
    contacts_lines = [f"- Primary: @{handle}"]
    if slack:
        contacts_lines.append(f"- Slack: {slack}")
    text = _replace_block(text, "contacts", "\n".join(contacts_lines))
    for marker in ("data", "external", "constraints", "deploy", "gotchas"):
        text = _clear_block(text, marker)
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Initialize project from template markers")
    parser.add_argument("--name", required=True, help="Project name")
    parser.add_argument("--overview", required=True, help="One-line project overview")
    parser.add_argument("--author", required=True, help="Author / copyright holder name")
    parser.add_argument("--handle", required=True, help="GitHub handle (without @)")
    parser.add_argument("--slack", default="#general", help="Slack channel (default: #general)")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    year = str(datetime.now().year)

    edit_readme(REPO_ROOT / "README.md", args.name, args.overview, args.handle, args.slack)
    edit_license(REPO_ROOT / "LICENSE", year, args.author)
    edit_codeowners(REPO_ROOT / "CODEOWNERS", args.handle)
    edit_architecture(REPO_ROOT / "docs" / "ARCHITECTURE.md")
    edit_claude_md(REPO_ROOT / "CLAUDE.md", args.handle, args.slack)

    print(f"Initialized: {args.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
