from __future__ import annotations

from pathlib import Path

from markdown_utils import normalize_markdown_text, write_markdown_file


def test_normalize_recovers_stray_newline_escapes() -> None:
    raw = "### Heading\\n- Item 1\\n- Item 2"
    assert normalize_markdown_text(raw) == "### Heading\n- Item 1\n- Item 2"


def test_normalize_recovers_stray_crlf_escapes() -> None:
    raw = "line1\\r\\nline2\\r\\nline3"
    assert normalize_markdown_text(raw) == "line1\nline2\nline3"


def test_normalize_recovers_stray_tab_escapes() -> None:
    assert normalize_markdown_text("col1\\tcol2") == "col1\tcol2"


def test_normalize_collapses_crlf_to_lf() -> None:
    assert normalize_markdown_text("a\r\nb\r\nc") == "a\nb\nc"


def test_normalize_strips_outer_whitespace() -> None:
    assert normalize_markdown_text("\n\n  # Title\n\n") == "# Title"


def test_normalize_leaves_legitimate_double_backslash_alone() -> None:
    # "\\n" (double backslash + n) in the source means the user wanted a
    # literal backslash-n. We should not turn it into a newline.
    assert normalize_markdown_text("path\\\\name") == "path\\\\name"


def test_normalize_is_idempotent() -> None:
    once = normalize_markdown_text("# Title\n\nBody\n")
    twice = normalize_markdown_text(once)
    assert once == twice


def test_normalize_handles_empty() -> None:
    assert normalize_markdown_text("") == ""


def test_write_markdown_file_uses_lf_endings(tmp_path: Path) -> None:
    target = tmp_path / "out.md"
    write_markdown_file(target, "# Title\r\nBody with \\n escape\r\n")
    raw = target.read_bytes()
    assert b"\r" not in raw
    assert raw.endswith(b"\n")
    assert raw.decode("utf-8") == "# Title\nBody with \n escape\n"


def test_write_markdown_file_creates_parents(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "dir" / "out.md"
    write_markdown_file(target, "hello")
    assert target.read_text(encoding="utf-8") == "hello\n"
