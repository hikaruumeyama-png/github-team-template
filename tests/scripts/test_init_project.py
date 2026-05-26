"""Tests for scripts/init_project.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.init_project import (
    _clear_block,
    _replace_block,
    _strip_markers,
    edit_architecture,
    edit_claude_md,
    edit_codeowners,
    edit_license,
    edit_readme,
    main,
)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Unit: marker helpers
# ---------------------------------------------------------------------------


def test_replace_block_inline() -> None:
    text = "# <!-- TEMPLATE:title -->Old Title<!-- /TEMPLATE:title -->"
    assert _replace_block(text, "title", "New Title") == "# New Title"


def test_replace_block_multiline() -> None:
    text = "<!-- TEMPLATE:overview -->\nold\n<!-- /TEMPLATE:overview -->"
    assert _replace_block(text, "overview", "new") == "new"


def test_strip_markers_keeps_content() -> None:
    text = "<!-- TEMPLATE:setup -->\ncontent\n<!-- /TEMPLATE:setup -->"
    result = _strip_markers(text, "setup")
    assert "TEMPLATE" not in result
    assert "content" in result


def test_clear_block_removes_content() -> None:
    text = "## Heading\n\n<!-- TEMPLATE:ctx -->\nplaceholder\n<!-- /TEMPLATE:ctx -->\n\n## Next"
    result = _clear_block(text, "ctx")
    assert "TEMPLATE" not in result
    assert "placeholder" not in result
    assert "## Heading" in result
    assert "## Next" in result


# ---------------------------------------------------------------------------
# Unit: edit_readme
# ---------------------------------------------------------------------------

_README_TEMPLATE = """\
# <!-- TEMPLATE:title -->プロジェクト名<!-- /TEMPLATE:title -->

<!-- TEMPLATE:overview -->
1〜3 行でこのプロジェクトが解決する課題を書く。
<!-- /TEMPLATE:overview -->

## 新しいプロジェクトを立ち上げる

> このセクションは削除してください。

### 1. ステップ

内容

---

## Setup

<!-- TEMPLATE:setup -->
### まずこれだけ

セットアップ手順
<!-- /TEMPLATE:setup -->

## Usage

<!-- USAGE:START -->
自動更新
<!-- USAGE:END -->

## Owners

<!-- TEMPLATE:owners -->
- Primary: @your-github-handle
- Backup: @another-github-handle
- Slack: #your-channel
<!-- /TEMPLATE:owners -->
"""


def test_edit_readme_replaces_title(tmp_path: Path) -> None:
    f = _write(tmp_path / "README.md", _README_TEMPLATE)
    edit_readme(f, "My Tool", "概要", "myhandle", "#dev")
    text = f.read_text(encoding="utf-8")
    assert text.startswith("# My Tool")
    assert "TEMPLATE:title" not in text


def test_edit_readme_replaces_overview(tmp_path: Path) -> None:
    f = _write(tmp_path / "README.md", _README_TEMPLATE)
    edit_readme(f, "My Tool", "これは概要です", "myhandle", "#dev")
    text = f.read_text(encoding="utf-8")
    assert "これは概要です" in text
    assert "TEMPLATE:overview" not in text


def test_edit_readme_strips_setup_keeps_content(tmp_path: Path) -> None:
    f = _write(tmp_path / "README.md", _README_TEMPLATE)
    edit_readme(f, "My Tool", "概要", "myhandle", "#dev")
    text = f.read_text(encoding="utf-8")
    assert "まずこれだけ" in text
    assert "TEMPLATE:setup" not in text


def test_edit_readme_replaces_owners(tmp_path: Path) -> None:
    f = _write(tmp_path / "README.md", _README_TEMPLATE)
    edit_readme(f, "My Tool", "概要", "myhandle", "#dev")
    text = f.read_text(encoding="utf-8")
    assert "@myhandle" in text
    assert "@your-github-handle" not in text
    assert "#dev" in text
    assert "TEMPLATE:owners" not in text


def test_edit_readme_omits_slack_when_empty(tmp_path: Path) -> None:
    f = _write(tmp_path / "README.md", _README_TEMPLATE)
    edit_readme(f, "My Tool", "概要", "myhandle", "")
    text = f.read_text(encoding="utf-8")
    assert "@myhandle" in text
    assert "Slack:" not in text
    assert "TEMPLATE:owners" not in text


def test_edit_readme_removes_onboarding_section(tmp_path: Path) -> None:
    f = _write(tmp_path / "README.md", _README_TEMPLATE)
    edit_readme(f, "My Tool", "概要", "myhandle", "#dev")
    text = f.read_text(encoding="utf-8")
    assert "新しいプロジェクトを立ち上げる" not in text
    assert "## Setup" in text


def test_edit_readme_preserves_usage_section(tmp_path: Path) -> None:
    f = _write(tmp_path / "README.md", _README_TEMPLATE)
    edit_readme(f, "My Tool", "概要", "myhandle", "#dev")
    text = f.read_text(encoding="utf-8")
    assert "USAGE:START" in text


# ---------------------------------------------------------------------------
# Unit: edit_license
# ---------------------------------------------------------------------------

_LICENSE_TEMPLATE = (
    "Copyright (c) <!-- TEMPLATE:license-year -->YYYY<!-- /TEMPLATE:license-year --> "
    "<!-- TEMPLATE:license-holder -->Your Org<!-- /TEMPLATE:license-holder -->\n"
)


def test_edit_license(tmp_path: Path) -> None:
    f = _write(tmp_path / "LICENSE", _LICENSE_TEMPLATE)
    edit_license(f, "2026", "Hikaru Umeyama")
    text = f.read_text(encoding="utf-8")
    assert "2026" in text
    assert "Hikaru Umeyama" in text
    assert "TEMPLATE" not in text
    assert "YYYY" not in text


# ---------------------------------------------------------------------------
# Unit: edit_codeowners
# ---------------------------------------------------------------------------

_CODEOWNERS_TEMPLATE = """\
* @your-org/team-name
/.github/ @your-org/devops
"""


def test_edit_codeowners(tmp_path: Path) -> None:
    f = _write(tmp_path / "CODEOWNERS", _CODEOWNERS_TEMPLATE)
    edit_codeowners(f, "myhandle")
    text = f.read_text(encoding="utf-8")
    assert "@myhandle" in text
    assert "@your-org/team-name" not in text
    assert "@your-org/devops" not in text


# ---------------------------------------------------------------------------
# Unit: edit_architecture
# ---------------------------------------------------------------------------

_ARCH_TEMPLATE = """\
# Architecture

## Context Diagram

<!-- TEMPLATE:context -->
外部アクター
<!-- /TEMPLATE:context -->

## Components

<!-- TEMPLATE:components -->
| 名前 | 責務 |
<!-- /TEMPLATE:components -->

## Data Flow

<!-- TEMPLATE:dataflow -->
1.
<!-- /TEMPLATE:dataflow -->

## External Dependencies

<!-- TEMPLATE:dependencies -->
- API:
<!-- /TEMPLATE:dependencies -->

## Operations

<!-- TEMPLATE:ops -->
- ログ:
<!-- /TEMPLATE:ops -->
"""


def test_edit_architecture_removes_all_markers(tmp_path: Path) -> None:
    f = _write(tmp_path / "ARCHITECTURE.md", _ARCH_TEMPLATE)
    edit_architecture(f)
    text = f.read_text(encoding="utf-8")
    assert "TEMPLATE" not in text
    assert "外部アクター" not in text


def test_edit_architecture_keeps_section_headings(tmp_path: Path) -> None:
    f = _write(tmp_path / "ARCHITECTURE.md", _ARCH_TEMPLATE)
    edit_architecture(f)
    text = f.read_text(encoding="utf-8")
    for heading in ("Context Diagram", "Components", "Data Flow", "External Dependencies"):
        assert heading in text
    assert "Operations" in text


# ---------------------------------------------------------------------------
# Unit: edit_claude_md
# ---------------------------------------------------------------------------

_CLAUDE_TEMPLATE = """\
# このリポジトリ固有の規約

## 扱うデータ

<!-- TEMPLATE:data -->
- 例: 顧客マスタ
<!-- /TEMPLATE:data -->

## 連携する外部システム / API

<!-- TEMPLATE:external -->
- 例: GitHub API
<!-- /TEMPLATE:external -->

## 特殊な依存・制約

<!-- TEMPLATE:constraints -->
- 例: VPN 必須
<!-- /TEMPLATE:constraints -->

## デプロイ手順

<!-- TEMPLATE:deploy -->
- 例: Jenkins
<!-- /TEMPLATE:deploy -->

## オーナー連絡先

<!-- TEMPLATE:contacts -->
- Primary: name <email>
- Slack: #channel
<!-- /TEMPLATE:contacts -->

## このリポでだけ守るべき注意点

<!-- TEMPLATE:gotchas -->
- 例: VPN
<!-- /TEMPLATE:gotchas -->

## 運用上の知見

既存の知見
"""


def test_edit_claude_md_fills_contacts(tmp_path: Path) -> None:
    f = _write(tmp_path / "CLAUDE.md", _CLAUDE_TEMPLATE)
    edit_claude_md(f, "myhandle", "#dev")
    text = f.read_text(encoding="utf-8")
    assert "@myhandle" in text
    assert "#dev" in text
    assert "TEMPLATE:contacts" not in text


def test_edit_claude_md_omits_slack_when_empty(tmp_path: Path) -> None:
    f = _write(tmp_path / "CLAUDE.md", _CLAUDE_TEMPLATE)
    edit_claude_md(f, "myhandle", "")
    text = f.read_text(encoding="utf-8")
    assert "@myhandle" in text
    assert "Slack:" not in text
    assert "TEMPLATE:contacts" not in text


def test_edit_claude_md_clears_other_sections(tmp_path: Path) -> None:
    f = _write(tmp_path / "CLAUDE.md", _CLAUDE_TEMPLATE)
    edit_claude_md(f, "myhandle", "#dev")
    text = f.read_text(encoding="utf-8")
    for marker in ("data", "external", "constraints", "deploy", "gotchas"):
        assert f"TEMPLATE:{marker}" not in text
    assert "顧客マスタ" not in text


def test_edit_claude_md_preserves_knowledge_section(tmp_path: Path) -> None:
    f = _write(tmp_path / "CLAUDE.md", _CLAUDE_TEMPLATE)
    edit_claude_md(f, "myhandle", "#dev")
    text = f.read_text(encoding="utf-8")
    assert "既存の知見" in text


# ---------------------------------------------------------------------------
# Integration: main()
# ---------------------------------------------------------------------------


@pytest.fixture
def project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up a minimal temp project mimicking the template structure."""
    (tmp_path / "docs").mkdir()
    _write(tmp_path / "README.md", _README_TEMPLATE)
    _write(tmp_path / "LICENSE", _LICENSE_TEMPLATE)
    _write(tmp_path / "CODEOWNERS", _CODEOWNERS_TEMPLATE)
    _write(tmp_path / "docs" / "ARCHITECTURE.md", _ARCH_TEMPLATE)
    _write(tmp_path / "CLAUDE.md", _CLAUDE_TEMPLATE)
    # Patch REPO_ROOT so the script edits files in tmp_path
    monkeypatch.setattr("scripts.init_project.REPO_ROOT", tmp_path)
    return tmp_path


def test_main_runs_and_exits_0(project_dir: Path) -> None:
    result = main(
        ["--name", "TestProj", "--overview", "概要", "--author", "Author", "--handle", "myhandle"]
    )
    assert result == 0


def test_main_no_template_markers_remain(project_dir: Path) -> None:
    main(["--name", "TestProj", "--overview", "概要", "--author", "Author", "--handle", "myhandle"])
    for path in [
        project_dir / "README.md",
        project_dir / "LICENSE",
        project_dir / "docs" / "ARCHITECTURE.md",
    ]:
        text = path.read_text(encoding="utf-8")
        assert "TEMPLATE:" not in text, f"TEMPLATE marker remains in {path.name}"
