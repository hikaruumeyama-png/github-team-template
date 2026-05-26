"""PATH-mock based tests for scripts/setup-derived-repo.sh."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_SRC = REPO_ROOT / "scripts" / "setup-derived-repo.sh"

# Resolve bash/git at import time, before any monkeypatching restricts PATH.
_GIT_PATH: str = shutil.which("git") or shutil.which("git.exe") or ""


def _resolve_bash_path() -> str:
    """Prefer Git Bash over Windows' WSL relay bash.exe."""
    if _GIT_PATH:
        git_root = Path(_GIT_PATH).resolve().parent.parent
        for relative in ("bin/bash.exe", "usr/bin/bash.exe"):
            candidate = git_root / relative
            if candidate.exists():
                return str(candidate)

    for executable in ("bash", "bash.exe"):
        resolved = shutil.which(executable)
        if resolved is None:
            continue
        lowered = resolved.lower()
        if "windows\\system32\\bash.exe" in lowered or "windowsapps\\bash.exe" in lowered:
            continue
        return resolved

    return shutil.which("bash") or shutil.which("bash.exe") or ""


_BASH_PATH: str = _resolve_bash_path()
# Parent directory of the real git binary — added to PATH so the bash stub can
# invoke git without relying on shebang tricks (which break on Windows).
_GIT_DIR: str = str(Path(_GIT_PATH).parent) if _GIT_PATH else ""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_stub(bindir: Path, name: str, body: str) -> Path:
    """Write an executable bash stub to bindir/name.

    Uses ``#!/bin/bash`` (absolute MSYS/POSIX path) instead of
    ``#!/usr/bin/env bash`` so that the shebang resolves even when the test
    PATH is restricted to bindir (where ``env`` is not present).
    """
    path = bindir / name
    path.write_text(f"#!/bin/bash\n{body}\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _bash() -> str:
    """Absolute path to bash on the host (needed because the test PATH is
    limited to bindir and bash itself must be findable for subprocess.run).

    Reads the pre-resolved _BASH_PATH constant; cannot re-search PATH at
    call time because monkeypatch has already restricted it to bindir.
    """
    if not _BASH_PATH:
        raise RuntimeError("bash not found on host PATH")
    return _BASH_PATH


@pytest.fixture
def stage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Stage a sandbox with: a fake git repo + a copied setup-derived-repo.sh
    + a stub setup-branch-protection.sh + a stub bin dir on PATH.

    Returns a dict of paths the test can use to set up stubs and assert calls.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir()

    # Copy the real setup-derived-repo.sh into the sandbox so $(dirname) works.
    target_script = scripts_dir / "setup-derived-repo.sh"
    target_script.write_bytes(SCRIPT_SRC.read_bytes())
    target_script.chmod(0o755)

    # Default stub for sibling — overridable per test by re-writing the file.
    sibling_stub = scripts_dir / "setup-branch-protection.sh"
    sibling_stub.write_text(
        '#!/bin/bash\necho "setup-branch-protection.sh $*" >> "$STUB_LOG"\nexit 0\n',
        encoding="utf-8",
    )
    sibling_stub.chmod(0o755)

    # Init a fake git repo with a GitHub origin.
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/test-owner/test-repo.git"],
        cwd=repo,
        check=True,
    )

    # Stub bin dir for PATH. bindir is first so stubs take precedence; the
    # real git directory is appended so git commands work without shebang
    # tricks (which are unreliable on Windows).
    #
    # CAVEAT: on ubuntu-latest, _GIT_DIR is /usr/bin, which also contains
    # gh. Every test that reaches the gh auth check MUST place a gh stub
    # in bindir first — bindir's precedence shadows the host gh. Tests
    # that do not stub gh would see the host gh on Ubuntu CI.
    bindir = tmp_path / "bin"
    bindir.mkdir()

    # Call log shared by all stubs.
    log = tmp_path / "calls.log"
    log.write_text("", encoding="utf-8")

    monkeypatch.chdir(repo)
    # PATH = bindir (stubs first) + real git dir (so `git` is found by script)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + _GIT_DIR)
    monkeypatch.setenv("STUB_LOG", str(log))

    return {
        "repo": repo,
        "script": target_script,
        "sibling": sibling_stub,
        "bin": bindir,
        "log": log,
    }


def _run(
    stage: dict[str, Path],
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the staged setup-derived-repo.sh with the given args/env.

    Uses absolute path to bash because the test PATH only has bindir.
    """
    args = args or []
    full_env = {**os.environ, **(env or {})}
    return subprocess.run(
        [_bash(), str(stage["script"]), *args],
        cwd=stage["repo"],
        env=full_env,
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def test_help_prints_usage(stage: dict[str, Path]) -> None:
    """`--help` exits 0 and prints usage."""
    result = _run(stage, ["--help"])
    assert result.returncode == 0, result.stderr
    assert "setup-derived-repo.sh" in result.stdout
    assert "Usage:" in result.stdout


def test_fail_if_not_git_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """git リポじゃないディレクトリで実行すると exit 1。"""
    # Copy script to a non-git directory.
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "scripts").mkdir()
    target = outside / "scripts" / "setup-derived-repo.sh"
    target.write_bytes(SCRIPT_SRC.read_bytes())
    target.chmod(0o755)
    monkeypatch.chdir(outside)

    result = subprocess.run(
        [_bash(), str(target)],
        cwd=outside,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "not inside a git repository" in result.stderr


def test_fail_if_origin_url_unparseable(stage: dict[str, Path]) -> None:
    """origin が GitHub URL でないとき exit 1。"""
    # Replace the origin URL with something unparseable.
    # Use absolute path to git because monkeypatch has already limited PATH to bindir.
    subprocess.run(
        [_GIT_PATH, "remote", "set-url", "origin", "ssh://gitlab.example.com/foo/bar.git"],
        cwd=stage["repo"],
        check=True,
    )
    result = _run(stage)
    assert result.returncode == 1
    assert "cannot parse owner/repo" in result.stderr


def test_origin_url_parses_https_format(stage: dict[str, Path]) -> None:
    """https://github.com/owner/repo.git を正しく扱える(precondition で落ちない)。

    後段の precondition で落ちる可能性はあるが、URL パース起因の
    exit ではないことを確認する。
    """
    _write_stub(
        stage["bin"],
        "gh",
        'if [[ "$*" == "auth status" ]]; then exit 1; fi\nexit 0',
    )
    result = _run(stage)
    assert result.returncode == 1
    assert "cannot parse owner/repo" not in result.stderr
    assert "gh auth login --scopes repo" in result.stderr


def test_fail_if_gh_unauthenticated(stage: dict[str, Path]) -> None:
    """gh auth status が non-zero を返したら exit 1 で誘導メッセージ。"""
    _write_stub(
        stage["bin"],
        "gh",
        'echo "gh $*" >> "$STUB_LOG"\nif [[ "$*" == "auth status" ]]; then exit 1; fi\nexit 0',
    )
    result = _run(stage)
    assert result.returncode == 1
    assert "gh auth login --scopes repo" in result.stderr


def test_gh_auth_ok_proceeds(stage: dict[str, Path]) -> None:
    """gh auth status が成功すれば gh の precondition で落ちない。"""
    _write_stub(stage["bin"], "gh", 'echo "gh $*" >> "$STUB_LOG"\nexit 0')
    result = _run(stage, env={"GEMINI_API_KEY": ""})
    # gh auth を通過した後は、次の precondition である GEMINI_API_KEY の確認に進む。
    assert result.returncode == 1
    assert "gh auth login" not in result.stderr
    assert "GEMINI_API_KEY not set" in result.stderr


def test_fail_if_gemini_api_key_unset(stage: dict[str, Path]) -> None:
    """$GEMINI_API_KEY が空だと exit 1 で暫定セットアップ案内。"""
    _write_stub(stage["bin"], "gh", "exit 0")
    env = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
    result = subprocess.run(
        [_bash(), str(stage["script"])],
        cwd=stage["repo"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "export GEMINI_API_KEY" in result.stderr
    assert "Organization" in result.stderr


def test_no_external_secret_cli_required(stage: dict[str, Path]) -> None:
    """外部 Secret 管理 CLI が無くても GEMINI_API_KEY があれば進める。"""
    _write_stub(stage["bin"], "gh", "exit 0")
    result = _run(stage, env={"GEMINI_API_KEY": "test-key"})
    assert result.returncode == 0, result.stderr


def _ok_stubs(stage: dict[str, Path]) -> None:
    """Place stubs that succeed and log invocations to $STUB_LOG.

    - gh:      logs args, exits 0, drains stdin on `secret set` and `api` calls
    """
    _write_stub(
        stage["bin"],
        "gh",
        (
            'echo "gh $*" >> "$STUB_LOG"\n'
            'if [[ "$1" == "secret" && "$2" == "set" ]]; then cat >/dev/null; fi\n'
            'if [[ "$1" == "api" ]]; then cat >/dev/null 2>/dev/null || true; fi\n'
            "exit 0"
        ),
    )


def test_step1_pipes_gemini_api_key_to_gh_secret_set(stage: dict[str, Path]) -> None:
    """正常系: GEMINI_API_KEY が gh secret set に pipe される。"""
    _ok_stubs(stage)
    result = _run(stage, env={"GEMINI_API_KEY": "test-key"})
    assert result.returncode == 0, result.stderr
    log = stage["log"].read_text(encoding="utf-8")
    assert "gh secret set GEMINI_API_KEY --repo test-owner/test-repo" in log


def test_step1_gh_secret_set_failure_exits_1(stage: dict[str, Path]) -> None:
    """gh secret set が non-zero を返したら全体が exit 1。"""
    _write_stub(
        stage["bin"],
        "gh",
        (
            'if [[ "$1" == "secret" && "$2" == "set" ]]; then\n'
            '  cat >/dev/null; echo "gh error" >&2; exit 2\n'
            "fi\n"
            "exit 0"
        ),
    )
    result = _run(stage, env={"GEMINI_API_KEY": "test-key"})
    assert result.returncode != 0
    assert "gh error" in result.stderr


def test_dry_run_step1_prints_plan_and_skips_calls(stage: dict[str, Path]) -> None:
    """`--dry-run` で [DRY-RUN] [1/3] が出て gh secret set は呼ばれない。"""
    _ok_stubs(stage)
    result = _run(stage, ["--dry-run"], env={"GEMINI_API_KEY": "test-key"})
    assert "[DRY-RUN] [1/3]" in result.stdout
    log = stage["log"].read_text(encoding="utf-8")
    assert "gh secret set" not in log


def test_step2_calls_gh_api_put_permissions(stage: dict[str, Path]) -> None:
    """gh api PUT で Actions Workflow permissions を write + 承認許可に設定する。"""
    _ok_stubs(stage)
    result = _run(stage, env={"GEMINI_API_KEY": "test-key"})
    assert result.returncode == 0, result.stderr
    log = stage["log"].read_text(encoding="utf-8")
    assert "api -X PUT repos/test-owner/test-repo/actions/permissions/workflow" in log
    assert "default_workflow_permissions=write" in log
    assert "can_approve_pull_request_reviews=true" in log


def test_dry_run_step2_prints_plan_and_skips_call(stage: dict[str, Path]) -> None:
    _ok_stubs(stage)
    result = _run(stage, ["--dry-run"], env={"GEMINI_API_KEY": "test-key"})
    assert "[DRY-RUN] [2/3]" in result.stdout
    log = stage["log"].read_text(encoding="utf-8")
    assert "actions/permissions/workflow" not in log


def test_step3_calls_branch_protection_without_dry_run(stage: dict[str, Path]) -> None:
    _ok_stubs(stage)
    result = _run(stage, env={"GEMINI_API_KEY": "test-key"})
    assert result.returncode == 0, result.stderr
    log = stage["log"].read_text(encoding="utf-8")
    assert "setup-branch-protection.sh " in log  # called once
    assert "setup-branch-protection.sh --dry-run" not in log


def test_dry_run_step3_propagates_dry_run_to_sibling(stage: dict[str, Path]) -> None:
    _ok_stubs(stage)
    result = _run(stage, ["--dry-run"], env={"GEMINI_API_KEY": "test-key"})
    assert "[DRY-RUN] [3/3]" in result.stdout
    log = stage["log"].read_text(encoding="utf-8")
    assert "setup-branch-protection.sh --dry-run" in log


def test_step3_failure_prints_warning_and_continues(stage: dict[str, Path]) -> None:
    _ok_stubs(stage)
    # Overwrite the sibling stub to fail.
    stage["sibling"].write_text(
        "#!/bin/bash\n"
        'echo "setup-branch-protection.sh $*" >> "$STUB_LOG"\n'
        'echo "boom" >&2\n'
        "exit 7\n",
        encoding="utf-8",
    )
    stage["sibling"].chmod(0o755)
    result = _run(stage, env={"GEMINI_API_KEY": "test-key"})
    # Step 3 failure is non-fatal: overall exit 0, warning on stderr.
    assert result.returncode == 0
    assert "WARN" in result.stderr
