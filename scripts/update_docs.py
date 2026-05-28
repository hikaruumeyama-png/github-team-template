"""Auto-update the USAGE section of README.md using the Gemini API.

Usage:
    python -m scripts.update_docs [--readme PATH] [--dry-run]

Behavior:
  1. Read the README file (default README.md).
  2. Find the region between ``<!-- USAGE:START -->`` and ``<!-- USAGE:END -->``.
     If markers are missing or mis-ordered, exit 1 with an explicit error.
  3. Build context for Gemini: pyproject.toml + all scripts/*.py source.
  4. Call Gemini API (gemini-2.5-flash by default; override with GEMINI_MODEL).
     - API key is read from GEMINI_API_KEY (falls back to GOOGLE_API_KEY for compatibility).
     - Explicit context caching is NOT used — for weekly runs the overhead of
       Gemini's named-cache lifecycle outweighs the benefit. Add it later if needed.
  5. Silent-failure prevention:
     - GEMINI_API_KEY (or GOOGLE_API_KEY) unset → exit 1 with explicit message to stderr.
     - Empty API response → exit 1.
     - Non-text response → exit 1.
  6. Replace ONLY the content between USAGE:START/END (markers stay).
  7. Idempotent: if new content equals existing content (trailing-whitespace
     normalized), do NOT write the file.  Print "No changes" and exit 0.
  8. --dry-run: print unified diff to stdout, do NOT write file, exit 0.
"""

from __future__ import annotations

import argparse
import difflib
import glob
import os
import sys
from pathlib import Path

from google import genai

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USAGE_START = "<!-- USAGE:START -->"
USAGE_END = "<!-- USAGE:END -->"
DEFAULT_MODEL = "gemini-2.5-flash"
MAX_TOKENS = 4096

_SYSTEM_TEXT = (
    "You are a documentation expert. "
    "Generate a concise, accurate Usage section in Markdown "
    "for the project described in the provided context. "
    "Output only the Markdown content for the Usage section body "
    "(no heading, no surrounding code fences)."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_usage_region(text: str) -> tuple[int, int]:
    """Return (start_idx, end_idx) of the USAGE region (exclusive of markers).

    start_idx points to the character immediately after USAGE:START marker + newline.
    end_idx points to the character at the start of USAGE:END marker.

    Raises SystemExit(1) if markers missing or mis-ordered.
    """
    start_marker_pos = text.find(USAGE_START)
    end_marker_pos = text.find(USAGE_END)

    if start_marker_pos == -1 or end_marker_pos == -1:
        print(
            f"Error: README is missing USAGE markers ({USAGE_START} and/or {USAGE_END})",
            file=sys.stderr,
        )
        sys.exit(1)

    if end_marker_pos <= start_marker_pos:
        print(
            f"Error: USAGE markers are mis-ordered ({USAGE_END} appears before {USAGE_START})",
            file=sys.stderr,
        )
        sys.exit(1)

    # Content region starts right after the start marker + newline
    content_start = start_marker_pos + len(USAGE_START)
    # Include the newline immediately after USAGE:START
    if content_start < len(text) and text[content_start] == "\n":
        content_start += 1

    content_end = end_marker_pos
    return content_start, content_end


def _build_static_context(readme_path: Path) -> str:
    """Build the static context string (pyproject.toml + scripts source)."""
    parts: list[str] = []

    pyproject = readme_path.parent / "pyproject.toml"
    if pyproject.exists():
        parts.append("=== pyproject.toml ===")
        parts.append(pyproject.read_text(encoding="utf-8"))

    # Glob scripts/*.py relative to README parent
    scripts_dir = readme_path.parent / "scripts"
    py_files = sorted(glob.glob(str(scripts_dir / "*.py")))
    for py_file in py_files:
        rel = Path(py_file).name
        parts.append(f"=== scripts/{rel} ===")
        parts.append(Path(py_file).read_text(encoding="utf-8"))

    return "\n".join(parts)


def _call_api(
    client: genai.Client,
    model: str,
    system: str,
    context: str,
    user_msg: str,
) -> str:
    """Call the Gemini API and return the generated text.

    Exits 1 on empty response or non-text response.
    """
    full_user_content = f"{context}\n\n{user_msg}"

    response = client.models.generate_content(
        model=model,
        contents=full_user_content,
        config=genai.types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=MAX_TOKENS,
            # gemini-2.5-flash は thinking モデルで、思考トークンが
            # max_output_tokens から差し引かれる。doc 生成は全コンテキストを
            # 渡す決定的タスクなので thinking を無効化し、出力枠を確保する。
            thinking_config=genai.types.ThinkingConfig(thinking_budget=0),
        ),
    )

    try:
        text = response.text
    except (ValueError, AttributeError):
        text = None
    if not text:
        print("Error: Gemini API returned empty content", file=sys.stderr)
        sys.exit(1)

    return text


def _normalize(text: str) -> str:
    """Normalize trailing whitespace for idempotency comparison."""
    return "\n".join(line.rstrip() for line in text.splitlines())


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------


def run(readme_path: Path, dry_run: bool = False) -> int:
    """Execute the docs update.

    Returns
    -------
    int
        0 on success (written or no-change or dry-run), 1 on error.
    """
    # 1. Read README
    try:
        original = readme_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Error reading {readme_path}: {exc}", file=sys.stderr)
        return 1

    # 2. Find USAGE region (exits 1 internally on error)
    content_start, content_end = _find_usage_region(original)
    current_content = original[content_start:content_end]

    # 3. Resolve API key (GEMINI_API_KEY preferred; GOOGLE_API_KEY as fallback)
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print(
            "Error: GEMINI_API_KEY not set (also checked GOOGLE_API_KEY as fallback)",
            file=sys.stderr,
        )
        sys.exit(1)

    # 4. Build static context
    static_context = _build_static_context(readme_path)

    # 5. Call API (exits 1 internally on error)
    model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
    client = genai.Client(api_key=api_key)
    generated = _call_api(
        client,
        model,
        _SYSTEM_TEXT,
        static_context,
        "Generate a Usage section in Markdown for this project.",
    )

    # Ensure generated content ends with a newline before USAGE:END
    if not generated.endswith("\n"):
        generated = generated + "\n"

    # 6. Idempotency check
    if _normalize(generated) == _normalize(current_content):
        print("No changes")
        return 0

    # 7. Reconstruct README with replaced region
    new_readme = original[:content_start] + generated + original[content_end:]

    # 8. --dry-run: print diff and exit 0
    if dry_run:
        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            new_readme.splitlines(keepends=True),
            fromfile=str(readme_path),
            tofile=str(readme_path) + " (updated)",
        )
        sys.stdout.writelines(diff)
        return 0

    # 9. Write file
    readme_path.write_text(new_readme, encoding="utf-8")
    print(f"Updated {readme_path}")
    return 0


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Parse CLI args and run docs update.

    Parameters
    ----------
    argv:
        Argument list. Defaults to sys.argv[1:] when None.

    Returns
    -------
    int
        0 on success, 1 on error.
    """
    parser = argparse.ArgumentParser(
        description="Auto-update README USAGE section using Gemini API."
    )
    parser.add_argument(
        "--readme",
        default="README.md",
        help="Path to the README file (default: README.md)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print unified diff instead of writing file. Exit 0.",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    return run(Path(args.readme), dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
