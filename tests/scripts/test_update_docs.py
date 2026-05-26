"""TDD tests for scripts.update_docs."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import google.genai.models
import pytest

from scripts.update_docs import USAGE_END, USAGE_START, main, run


def test_genai_mock_path_stable() -> None:
    """Guard: 他のテストが patch する import path が SDK 側に実在することを確認する。

    google-genai SDK が `Models.generate_content` をリファクタリングすると、monkeypatch.setattr が
    silent に効かなくなり、テストが本物の API を叩いてしまう可能性がある。
    この sanity check で先に fail させる。
    """
    assert hasattr(google.genai.models.Models, "generate_content"), (
        "google-genai SDK の Models.generate_content が見つからない。"
        "他のテストの monkeypatch 対象 path を更新する必要がある。"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MARKER_CONTENT = "Current usage content.\n"

_FULL_README = (
    "# My Project\n\n"
    "## Setup\n\nRun `uv sync`.\n\n"
    "## Usage\n\n"
    f"{USAGE_START}\n"
    f"{_MARKER_CONTENT}"
    f"{USAGE_END}\n\n"
    "## Owners\n\n@owner\n"
)

_BEFORE_MARKER = f"# My Project\n\n## Setup\n\nRun `uv sync`.\n\n## Usage\n\n{USAGE_START}\n"

_AFTER_MARKER = f"{USAGE_END}\n\n## Owners\n\n@owner\n"


def _make_readme(tmp_path: Path, content: str = _FULL_README) -> Path:
    readme = tmp_path / "README.md"
    readme.write_text(content, encoding="utf-8")
    # Also create a minimal pyproject.toml so context-building doesn't fail
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n', encoding="utf-8")
    return readme


def _mock_response(text: str = "Generated usage content.\n") -> MagicMock:
    """Return a MagicMock that simulates a successful Gemini API response."""
    response = MagicMock()
    response.text = text
    return response


def _mock_generate(text: str = "Generated usage content.\n") -> MagicMock:
    """Return a MagicMock callable that returns a Gemini-style response."""
    return MagicMock(return_value=_mock_response(text))


# ---------------------------------------------------------------------------
# Case 1: README without USAGE markers → exit 1, error to stderr
# ---------------------------------------------------------------------------


def test_no_markers_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Case 1: README missing USAGE markers → exit 1 with explicit error to stderr."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    readme = tmp_path / "README.md"
    readme.write_text("# Title\n\n## Usage\n\nNo markers here.\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        run(readme)
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "USAGE" in captured.err
    assert "marker" in captured.err.lower() or "missing" in captured.err.lower()


# ---------------------------------------------------------------------------
# Case 2: Markers in wrong order (END before START) → exit 1
# ---------------------------------------------------------------------------


def test_markers_wrong_order_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Case 2: USAGE:END appears before USAGE:START → exit 1."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    readme = tmp_path / "README.md"
    readme.write_text(
        f"# Title\n\n{USAGE_END}\nsome text\n{USAGE_START}\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        run(readme)
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "mis-ordered" in captured.err or "order" in captured.err.lower()


# ---------------------------------------------------------------------------
# Case 3: GEMINI_API_KEY unset (no GOOGLE_API_KEY fallback) → exit 1
# ---------------------------------------------------------------------------


def test_missing_api_key_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Case 3: GEMINI_API_KEY not set (no GOOGLE_API_KEY either) → exit 1, key name in stderr."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    readme = _make_readme(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        run(readme)
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "GEMINI_API_KEY" in captured.err


# ---------------------------------------------------------------------------
# Case 4: Successful API response → README updated, file written
# ---------------------------------------------------------------------------


def test_api_returns_text_updates_readme(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 4: Mock API returns text → USAGE region replaced, file written."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    fake_generate = _mock_generate("Generated usage content.\n")
    monkeypatch.setattr("google.genai.models.Models.generate_content", fake_generate)

    readme = _make_readme(tmp_path)
    result = run(readme)
    assert result == 0

    updated = readme.read_text(encoding="utf-8")
    assert "Generated usage content." in updated
    assert USAGE_START in updated
    assert USAGE_END in updated


# ---------------------------------------------------------------------------
# Case 5: API returns empty text → exit 1
# ---------------------------------------------------------------------------


def test_api_empty_content_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Case 5: Mock API returns response with empty text → exit 1."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    response = MagicMock()
    response.text = ""
    fake_generate = MagicMock(return_value=response)
    monkeypatch.setattr("google.genai.models.Models.generate_content", fake_generate)

    readme = _make_readme(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        run(readme)
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "empty" in captured.err.lower()


# ---------------------------------------------------------------------------
# Case 6: API returns identical content → no write, exit 0 (idempotent)
# ---------------------------------------------------------------------------


def test_identical_content_no_write(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Case 6: Generated content matches current README → no write, exit 0."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    # Return the same content that is currently in the README
    fake_generate = _mock_generate(_MARKER_CONTENT)
    monkeypatch.setattr("google.genai.models.Models.generate_content", fake_generate)

    readme = _make_readme(tmp_path)
    mtime_before = readme.stat().st_mtime

    result = run(readme)
    assert result == 0
    captured = capsys.readouterr()
    assert "No changes" in captured.out

    # File should NOT have been rewritten (mtime unchanged)
    assert readme.stat().st_mtime == mtime_before


# ---------------------------------------------------------------------------
# Case 7: --dry-run flag → no write, diff printed to stdout
# ---------------------------------------------------------------------------


def test_dry_run_no_write(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Case 7: --dry-run → no file written, diff to stdout, exit 0."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    fake_generate = _mock_generate("Brand new usage text.\n")
    monkeypatch.setattr("google.genai.models.Models.generate_content", fake_generate)

    readme = _make_readme(tmp_path)
    original_text = readme.read_text(encoding="utf-8")

    result = run(readme, dry_run=True)
    assert result == 0

    # File must NOT be written
    assert readme.read_text(encoding="utf-8") == original_text

    # Diff must appear in stdout
    captured = capsys.readouterr()
    assert "Brand new usage text." in captured.out


# ---------------------------------------------------------------------------
# Case 8: --readme flag uses custom path
# ---------------------------------------------------------------------------


def test_custom_readme_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 8: --readme flag passes custom path, file is updated there."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    fake_generate = _mock_generate("Custom path usage.\n")
    monkeypatch.setattr("google.genai.models.Models.generate_content", fake_generate)

    custom_readme = tmp_path / "DOCS.md"
    custom_readme.write_text(_FULL_README, encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n', encoding="utf-8")

    result = main(["--readme", str(custom_readme)])
    assert result == 0

    updated = custom_readme.read_text(encoding="utf-8")
    assert "Custom path usage." in updated


# ---------------------------------------------------------------------------
# Case 9: system_instruction is passed correctly in the API config
# ---------------------------------------------------------------------------


def test_system_instruction_passed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 9: API call includes system_instruction in the GenerateContentConfig."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    fake_generate = _mock_generate("System instruction test.\n")
    monkeypatch.setattr("google.genai.models.Models.generate_content", fake_generate)

    readme = _make_readme(tmp_path)
    run(readme)

    assert fake_generate.called
    _, kwargs = fake_generate.call_args
    config = kwargs.get("config")
    assert config is not None, "generate_content was called without config"
    # system_instruction must be set in the config
    assert config.system_instruction, "system_instruction was not set in the API config"
    assert "documentation" in str(config.system_instruction).lower(), (
        "system_instruction does not mention 'documentation'"
    )


# ---------------------------------------------------------------------------
# Case 10: Default model is gemini-2.5-flash; GEMINI_MODEL overrides
# ---------------------------------------------------------------------------


def test_default_model_used(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 10a: Default model is gemini-2.5-flash."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    fake_generate = _mock_generate("Model test.\n")
    monkeypatch.setattr("google.genai.models.Models.generate_content", fake_generate)

    readme = _make_readme(tmp_path)
    run(readme)

    _, kwargs = fake_generate.call_args
    assert kwargs["model"] == "gemini-2.5-flash"


def test_env_model_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 10b: GEMINI_MODEL env var overrides the default model."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-custom-model")
    fake_generate = _mock_generate("Override model test.\n")
    monkeypatch.setattr("google.genai.models.Models.generate_content", fake_generate)

    readme = _make_readme(tmp_path)
    run(readme)

    _, kwargs = fake_generate.call_args
    assert kwargs["model"] == "gemini-custom-model"


# ---------------------------------------------------------------------------
# Case 11: Content OUTSIDE USAGE markers preserved bit-for-bit
# ---------------------------------------------------------------------------


def test_content_outside_markers_preserved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 11: Text before and after USAGE markers must be preserved exactly."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    fake_generate = _mock_generate("New usage content.\n")
    monkeypatch.setattr("google.genai.models.Models.generate_content", fake_generate)

    readme = _make_readme(tmp_path)
    run(readme)

    updated = readme.read_text(encoding="utf-8")

    # Extract the before/after portions
    start_pos = updated.find(USAGE_START)
    end_pos = updated.find(USAGE_END)
    assert start_pos != -1
    assert end_pos != -1

    before_updated = updated[:start_pos]
    after_updated = updated[end_pos + len(USAGE_END) :]

    before_original = _FULL_README[: _FULL_README.find(USAGE_START)]
    after_original = _FULL_README[_FULL_README.find(USAGE_END) + len(USAGE_END) :]

    assert before_updated == before_original, "Content before USAGE:START was modified"
    assert after_updated == after_original, "Content after USAGE:END was modified"


# ---------------------------------------------------------------------------
# Case 12: GOOGLE_API_KEY fallback is accepted when GEMINI_API_KEY unset
# ---------------------------------------------------------------------------


def test_google_api_key_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Case 12: GOOGLE_API_KEY is accepted as fallback when GEMINI_API_KEY is not set."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "google-fallback-key")
    fake_generate = _mock_generate("Fallback key usage.\n")
    monkeypatch.setattr("google.genai.models.Models.generate_content", fake_generate)

    readme = _make_readme(tmp_path)
    result = run(readme)
    assert result == 0

    updated = readme.read_text(encoding="utf-8")
    assert "Fallback key usage." in updated
