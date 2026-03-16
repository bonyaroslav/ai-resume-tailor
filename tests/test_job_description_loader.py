from __future__ import annotations

from pathlib import Path

import pytest

from job_description_loader import read_job_description
from tests.test_support import make_workspace_temp_dir


def test_read_job_description_from_txt() -> None:
    tmp_path = make_workspace_temp_dir("jd-loader-txt")
    jd_path = tmp_path / "jd.txt"
    jd_path.write_text("Backend Python role", encoding="utf-8")

    result = read_job_description(jd_path)

    assert result == "Backend Python role"


def test_read_job_description_from_md() -> None:
    tmp_path = make_workspace_temp_dir("jd-loader-md")
    jd_path = tmp_path / "jd.md"
    jd_path.write_text(
        "# Senior Python Engineer\nMust have: API design", encoding="utf-8"
    )

    result = read_job_description(jd_path)

    assert "Senior Python Engineer" in result
    assert "Must have: API design" in result


def test_read_job_description_rejects_unsupported_extension() -> None:
    tmp_path = make_workspace_temp_dir("jd-loader-extension")
    jd_path = tmp_path / "jd.docx"
    jd_path.write_text("not-a-real-docx", encoding="utf-8")

    with pytest.raises(ValueError, match=r"\.txt or \.md"):
        read_job_description(jd_path)


def test_read_job_description_rejects_missing_file() -> None:
    tmp_path = make_workspace_temp_dir("jd-loader-missing")
    missing_path = Path(tmp_path / "missing.md")

    with pytest.raises(FileNotFoundError):
        read_job_description(missing_path)
