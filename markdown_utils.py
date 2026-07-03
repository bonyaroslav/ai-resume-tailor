from __future__ import annotations

import re
from pathlib import Path

_STRAY_ESCAPE_PATTERN = re.compile(r"(?<!\\)\\(r\\n|r|n|t)")

_STRAY_ESCAPE_REPLACEMENTS = {
    "r\\n": "\n",
    "r": "\n",
    "n": "\n",
    "t": "\t",
}


def _replace_stray_escape(match: re.Match[str]) -> str:
    return _STRAY_ESCAPE_REPLACEMENTS[match.group(1)]


def normalize_markdown_text(text: str) -> str:
    """Recover real whitespace from stray escape sequences and normalize newlines.

    Models occasionally double-escape their own JSON strings, so a decoded
    ``report_markdown`` can carry literal ``\\n`` / ``\\t`` two-char sequences
    instead of real whitespace. This helper repairs that, collapses CRLF/CR to
    LF, strips outer whitespace, and enforces a single trailing newline.
    """
    if not text:
        return ""
    repaired = _STRAY_ESCAPE_PATTERN.sub(_replace_stray_escape, text)
    repaired = repaired.replace("\r\n", "\n").replace("\r", "\n")
    return repaired.strip()


def write_markdown_file(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` as normalized UTF-8 markdown with LF endings."""
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_markdown_text(text)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(normalized)
        handle.write("\n")
