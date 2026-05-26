"""Check that README.md contains all required sections.

Usage:
    python -m scripts.check_readme_sections [--readme PATH]

Required sections (ATX headings, exact level):
  - A title: any line starting with '# ' (H1)
  - ## Setup
  - ## Usage
  - ## Owners

Heading level is matched strictly: '### Setup' does NOT satisfy '## Setup'.
Title detection uses ATX-only ('# ' at line start); Setext style is ignored.
Leading whitespace before '#' makes a heading invalid (not standard ATX).

Exits 0 if all sections present, exits 1 if any missing.
Prints missing section names to stderr.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Required sections spec
# ---------------------------------------------------------------------------

# Each entry: (display_name, exact_heading_prefix_to_match)
# For the title we match any "# " (one '#' followed by space) at line start.
_REQUIRED: list[tuple[str, str]] = [
    ("Title (H1)", "# "),
    ("## Setup", "## Setup"),
    ("## Usage", "## Usage"),
    ("## Owners", "## Owners"),
]


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _check_readme(readme_path: Path) -> list[str]:
    """Return a list of missing section display names."""
    try:
        text = readme_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"Error reading {readme_path}: {exc}", file=sys.stderr)
        return [name for name, _ in _REQUIRED]

    lines = text.splitlines()
    missing: list[str] = []

    for display_name, prefix in _REQUIRED:
        if prefix == "# ":
            # H1 title: any "# <anything>" line counts as a title
            found = any(line.startswith(prefix) for line in lines)
        else:
            # H2 sections: exact match (allow trailing whitespace only).
            # `## Setup Info` must NOT satisfy `## Setup`.
            found = any(line.rstrip() == prefix for line in lines)
        if not found:
            missing.append(display_name)

    return missing


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Run the README section checker.

    Parameters
    ----------
    argv:
        Argument list. Defaults to sys.argv[1:] when None.

    Returns
    -------
    int
        0 if all required sections present, 1 otherwise.
    """
    parser = argparse.ArgumentParser(description="Check README for required sections.")
    parser.add_argument(
        "--readme",
        default="README.md",
        help="Path to the README file (default: README.md)",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    readme_path = Path(args.readme)
    missing = _check_readme(readme_path)

    if missing:
        for section in missing:
            print(f"Missing required section: {section}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
