"""Check for unfilled TEMPLATE markers in repository files.

Usage:
    python -m scripts.check_template_markers [PATH ...]

Scans the given paths (default: '.') recursively for:
  1. HTML-style TEMPLATE markers in *.md and LICENSE files:
       <!-- TEMPLATE:name --> or <!-- /TEMPLATE:name -->
  2. CODEOWNERS placeholder strings:
       @your-org/team-name  or  @your-org/devops

Exits 0 if no markers remain, exits 1 if any are found.
Prints "path:line: marker_text" to stderr for each finding.

Excluded paths (never scanned):
  - .git/
  - node_modules/
  - .venv/
  - docs/superpowers/plans/
  - CLAUDE.md  (legitimately mentions marker names in its knowledge section)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Matches <!-- TEMPLATE:xxx --> and <!-- /TEMPLATE:xxx -->
_HTML_MARKER_RE = re.compile(r"<!--\s*/?TEMPLATE:[^>]+-->")

# Placeholder strings used in CODEOWNERS (HTML comments not supported there)
_CODEOWNERS_PLACEHOLDERS = ("@your-org/team-name", "@your-org/devops")

# ---------------------------------------------------------------------------
# Excluded directory/file fragments (checked as path component substrings)
# ---------------------------------------------------------------------------

_EXCLUDED_DIRS = frozenset([".git", "node_modules", ".venv"])
_EXCLUDED_PATH_SEGMENTS = ("docs/superpowers/plans",)
_EXCLUDED_FILENAMES = frozenset(["CLAUDE.md"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_excluded(path: Path) -> bool:
    """Return True if *path* should be skipped entirely."""
    # Check every part of the path for excluded directory names
    parts = path.parts
    for part in parts:
        if part in _EXCLUDED_DIRS:
            return True

    # Check for excluded path segments (slash-joined)
    joined = path.as_posix()
    for segment in _EXCLUDED_PATH_SEGMENTS:
        if segment in joined:
            return True

    # Check exact filename exclusions
    return path.name in _EXCLUDED_FILENAMES


def _scan_html_markers(path: Path, findings: list[str]) -> None:
    """Scan *path* for HTML TEMPLATE markers; append findings."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in _HTML_MARKER_RE.finditer(line):
            findings.append(f"{path}:{lineno}: {match.group()}")


def _scan_codeowners(path: Path, findings: list[str]) -> None:
    """Scan a CODEOWNERS file for placeholder strings; append findings."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    for lineno, line in enumerate(text.splitlines(), start=1):
        for placeholder in _CODEOWNERS_PLACEHOLDERS:
            if placeholder in line:
                findings.append(f"{path}:{lineno}: {placeholder}")


def _should_scan_for_html(path: Path) -> bool:
    """Return True if this file should be scanned for HTML markers."""
    return path.suffix in {".md"} or path.name == "LICENSE"


def _walk(root: Path) -> list[str]:
    """Walk *root* recursively and return all findings."""
    findings: list[str] = []
    for item in root.rglob("*"):
        if not item.is_file():
            continue
        if _is_excluded(item):
            continue
        if item.name == "CODEOWNERS":
            _scan_codeowners(item, findings)
        elif _should_scan_for_html(item):
            _scan_html_markers(item, findings)
    return findings


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Run the marker checker.

    Parameters
    ----------
    argv:
        List of path arguments. Defaults to sys.argv[1:] when None;
        defaults to ["."] when an empty list is passed.

    Returns
    -------
    int
        0 if no markers found, 1 otherwise.
    """
    if argv is None:
        argv = sys.argv[1:]
    paths = argv if argv else ["."]

    all_findings: list[str] = []
    for path_str in paths:
        root = Path(path_str)
        if root.is_file():
            # Single-file mode: determine type and scan
            if not _is_excluded(root):
                if root.name == "CODEOWNERS":
                    _scan_codeowners(root, all_findings)
                elif _should_scan_for_html(root):
                    _scan_html_markers(root, all_findings)
        elif root.is_dir():
            all_findings.extend(_walk(root))

    for finding in all_findings:
        print(finding, file=sys.stderr)

    return 1 if all_findings else 0


if __name__ == "__main__":
    sys.exit(main())
