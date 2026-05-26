"""TDD tests for scripts.check_template_markers."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check_template_markers import main

# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def test_empty_directory_exits_0(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 1: empty directory → exit 0."""
    monkeypatch.chdir(tmp_path)
    assert main([str(tmp_path)]) == 0


def test_file_with_no_markers_exits_0(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 2: file with no markers → exit 0."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("# Hello\nNo markers here.\n")
    assert main([str(tmp_path)]) == 0


def test_file_with_html_open_marker_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Case 3: file with HTML open marker only → exit 1, stderr has file path."""
    monkeypatch.chdir(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text("# Title\n<!-- TEMPLATE:section -->\nSome content\n")
    result = main([str(tmp_path)])
    captured = capsys.readouterr()
    assert result == 1
    assert "README.md" in captured.err


def test_file_with_html_close_marker_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Case 4: file with HTML close marker only → exit 1."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("Content\n<!-- /TEMPLATE:section -->\n")
    result = main([str(tmp_path)])
    captured = capsys.readouterr()
    assert result == 1
    assert "README.md" in captured.err


def test_file_with_paired_html_markers_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Case 5: file with paired HTML markers → exit 1."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text(
        "# Title\n<!-- TEMPLATE:data -->\nfill me\n<!-- /TEMPLATE:data -->\n"
    )
    result = main([str(tmp_path)])
    captured = capsys.readouterr()
    assert result == 1
    assert "README.md" in captured.err


def test_codeowners_with_team_name_placeholder_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Case 6: CODEOWNERS with @your-org/team-name → exit 1."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CODEOWNERS").write_text("* @your-org/team-name\n")
    result = main([str(tmp_path)])
    captured = capsys.readouterr()
    assert result == 1
    assert "CODEOWNERS" in captured.err


def test_codeowners_with_devops_placeholder_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Case 7: CODEOWNERS with @your-org/devops → exit 1."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CODEOWNERS").write_text("docs/ @your-org/devops\n")
    result = main([str(tmp_path)])
    captured = capsys.readouterr()
    assert result == 1
    assert "CODEOWNERS" in captured.err


def test_codeowners_without_placeholders_exits_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Case 8: CODEOWNERS with neither placeholder → exit 0."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CODEOWNERS").write_text("* @real-org/real-team\n")
    assert main([str(tmp_path)]) == 0


def test_markers_inside_venv_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 9: markers inside .venv/ → ignored (exit 0)."""
    monkeypatch.chdir(tmp_path)
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    (venv_dir / "README.md").write_text("<!-- TEMPLATE:foo -->\n")
    assert main([str(tmp_path)]) == 0


def test_markers_inside_plans_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 10: markers inside docs/superpowers/plans/ → ignored (exit 0)."""
    monkeypatch.chdir(tmp_path)
    plans_dir = tmp_path / "docs" / "superpowers" / "plans"
    plans_dir.mkdir(parents=True)
    (plans_dir / "plan.md").write_text("<!-- TEMPLATE:something -->\n")
    assert main([str(tmp_path)]) == 0


def test_markers_inside_claude_md_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 11: markers inside CLAUDE.md → ignored (exit 0)."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CLAUDE.md").write_text("# Claude\nWe use <!-- TEMPLATE:data --> markers here.\n")
    assert main([str(tmp_path)]) == 0


def test_multiple_paths_all_scanned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Case 12: multiple paths via CLI args → all scanned."""
    monkeypatch.chdir(tmp_path)
    dir_a = tmp_path / "dir_a"
    dir_b = tmp_path / "dir_b"
    dir_a.mkdir()
    dir_b.mkdir()
    (dir_a / "file_a.md").write_text("<!-- TEMPLATE:x -->\n")
    (dir_b / "file_b.md").write_text("<!-- TEMPLATE:y -->\n")
    result = main([str(dir_a), str(dir_b)])
    captured = capsys.readouterr()
    assert result == 1
    assert "file_a.md" in captured.err
    assert "file_b.md" in captured.err


def test_cli_defaults_to_dot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 13: CLI defaults to '.' when no args."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("# Clean file, no markers.\n")
    # No args → defaults to ".", scans current dir
    assert main([]) == 0
