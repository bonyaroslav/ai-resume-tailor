from __future__ import annotations

from pathlib import Path

import pytest

from job_description_loader import (
    parse_company_and_title_from_filename,
    read_job_description,
    resolve_company_and_title,
)
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


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("JD_Xebia_SeniorNetAzureDeveloper.md", ("Xebia", "SeniorNetAzureDeveloper")),
        ("Xebia_Developer.txt", ("Xebia", "Developer")),
        ("Corp_JD_Xebia_Dev.md", ("Xebia", "Dev")),
        ("Developer.md", (None, "Developer")),
    ],
)
def test_parse_company_and_title_from_filename(
    filename: str, expected: tuple[str | None, str | None]
) -> None:
    assert parse_company_and_title_from_filename(Path(filename)) == expected


def test_resolve_keeps_both_when_provided() -> None:
    company, title = resolve_company_and_title(
        company="Acme",
        job_title="Staff Engineer",
        jd_path=Path("JD_Xebia_SeniorDeveloper.md"),
    )

    assert (company, title) == ("Acme", "Staff Engineer")


def test_resolve_derives_missing_company() -> None:
    company, title = resolve_company_and_title(
        company="",
        job_title="Staff Engineer",
        jd_path=Path("JD_Xebia_SeniorDeveloper.md"),
    )

    assert (company, title) == ("Xebia", "Staff Engineer")


def test_resolve_derives_missing_title() -> None:
    company, title = resolve_company_and_title(
        company="Acme",
        job_title=None,
        jd_path=Path("JD_Xebia_SeniorDeveloper.md"),
    )

    assert (company, title) == ("Acme", "SeniorDeveloper")


def test_resolve_derives_both_when_absent() -> None:
    company, title = resolve_company_and_title(
        company=None,
        job_title=None,
        jd_path=Path("JD_Xebia_SeniorNetAzureDeveloper.md"),
    )

    assert (company, title) == ("Xebia", "SeniorNetAzureDeveloper")


def test_resolve_raises_when_company_unresolvable() -> None:
    with pytest.raises(ValueError, match="CompanyName is missing"):
        resolve_company_and_title(
            company=None,
            job_title=None,
            jd_path=Path("Developer.md"),
        )
