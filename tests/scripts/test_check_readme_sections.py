"""TDD tests for scripts.check_readme_sections."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check_readme_sections import main

# ---------------------------------------------------------------------------
# Helper to write a README file and call main()
# ---------------------------------------------------------------------------


def _write_readme(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def test_all_sections_present_exits_0(tmp_path: Path) -> None:
    """Case 1: README with all 4 required sections → exit 0."""
    readme = tmp_path / "README.md"
    _write_readme(
        readme,
        "# My Project\n\n## Setup\n\nRun it.\n\n## Usage\n\nDo it.\n\n## Owners\n\nMe.\n",
    )
    assert main(["--readme", str(readme)]) == 0


def test_missing_owners_exits_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Case 2: README missing ## Owners → exit 1, stderr lists 'Owners'."""
    readme = tmp_path / "README.md"
    _write_readme(readme, "# My Project\n\n## Setup\n\nRun it.\n\n## Usage\n\nDo it.\n")
    result = main(["--readme", str(readme)])
    captured = capsys.readouterr()
    assert result == 1
    assert "Owners" in captured.err


def test_wrong_heading_level_exits_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Case 3: README with ### Setup (wrong level) → exit 1."""
    readme = tmp_path / "README.md"
    _write_readme(
        readme,
        "# My Project\n\n### Setup\n\nRun it.\n\n## Usage\n\nDo it.\n\n## Owners\n\nMe.\n",
    )
    result = main(["--readme", str(readme)])
    captured = capsys.readouterr()
    assert result == 1
    assert "Setup" in captured.err


def test_no_title_line_exits_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Case 4: README with no H1 title line → exit 1."""
    readme = tmp_path / "README.md"
    _write_readme(readme, "## Setup\n\nRun it.\n\n## Usage\n\nDo it.\n\n## Owners\n\nMe.\n")
    result = main(["--readme", str(readme)])
    captured = capsys.readouterr()
    assert result == 1
    # The missing thing should be mentioned in stderr
    assert captured.err.strip() != ""


def test_extra_sections_exits_0(tmp_path: Path) -> None:
    """Case 5: README with extra sections beyond required 4 → exit 0."""
    readme = tmp_path / "README.md"
    _write_readme(
        readme,
        (
            "# My Project\n\n"
            "## Setup\n\nRun it.\n\n"
            "## Usage\n\nDo it.\n\n"
            "## Owners\n\nMe.\n\n"
            "## Contributing\n\nPRs welcome.\n\n"
            "## License\n\nMIT\n"
        ),
    )
    assert main(["--readme", str(readme)]) == 0


def test_custom_readme_path_via_flag(tmp_path: Path) -> None:
    """Case 6: different README path via --readme flag → works."""
    custom = tmp_path / "CUSTOM_README.md"
    _write_readme(
        custom,
        "# Custom\n\n## Setup\n\nOK.\n\n## Usage\n\nOK.\n\n## Owners\n\nOK.\n",
    )
    assert main(["--readme", str(custom)]) == 0


def test_title_with_leading_whitespace_not_detected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Case 7: title with leading whitespace '  # Title' → NOT detected (strict ATX only).

    Design decision: we require the '#' to be at the start of the line (ATX strict).
    Indented headings are not valid CommonMark ATX headings.
    """
    readme = tmp_path / "README.md"
    _write_readme(
        readme,
        "  # Indented Title\n\n## Setup\n\nRun.\n\n## Usage\n\nDo.\n\n## Owners\n\nMe.\n",
    )
    result = main(["--readme", str(readme)])
    captured = capsys.readouterr()
    # The indented title is NOT a valid H1 → still missing title → exit 1
    assert result == 1
    assert captured.err.strip() != ""


def test_setup_with_extra_words_does_not_satisfy(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Case 8: '## Setup Info' must NOT satisfy '## Setup' (exact heading match)."""
    readme = tmp_path / "README.md"
    _write_readme(
        readme,
        "# My Project\n\n## Setup Info\n\nNo good.\n\n## Usage\n\nDo.\n\n## Owners\n\nMe.\n",
    )
    result = main(["--readme", str(readme)])
    captured = capsys.readouterr()
    assert result == 1
    assert "Setup" in captured.err


def test_setup_with_hyphen_suffix_does_not_satisfy(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Case 9: '## Setup-Info' must NOT satisfy '## Setup' (exact heading match)."""
    readme = tmp_path / "README.md"
    _write_readme(
        readme,
        "# My Project\n\n## Setup-Info\n\nNo good.\n\n## Usage\n\nDo.\n\n## Owners\n\nMe.\n",
    )
    result = main(["--readme", str(readme)])
    captured = capsys.readouterr()
    assert result == 1
    assert "Setup" in captured.err


def test_setup_with_trailing_whitespace_still_satisfies(tmp_path: Path) -> None:
    """Case 10: '## Setup   ' (trailing whitespace) MUST still satisfy '## Setup'."""
    readme = tmp_path / "README.md"
    _write_readme(
        readme,
        "# My Project\n\n## Setup   \n\nRun.\n\n## Usage\n\nDo.\n\n## Owners\n\nMe.\n",
    )
    assert main(["--readme", str(readme)]) == 0
