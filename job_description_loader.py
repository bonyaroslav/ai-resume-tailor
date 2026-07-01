from __future__ import annotations

from pathlib import Path


def read_job_description(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"JD file not found: {path}")

    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8")

    raise ValueError("Job Description input must be .txt or .md.")


def parse_company_and_title_from_filename(
    path: Path,
) -> tuple[str | None, str | None]:
    """Extract (company, job_title) from a `<prefix>_<Company>_<JobTitle>` filename.

    The filename (without extension) is split on "_". The last token is the job
    title and the second-to-last is the company; any leading tokens (a prefix
    such as "JD") are ignored. Missing tokens are returned as None.
    """
    tokens = [token for token in path.stem.split("_") if token.strip()]
    if len(tokens) >= 2:
        return tokens[-2], tokens[-1]
    if len(tokens) == 1:
        return None, tokens[-1]
    return None, None


def resolve_company_and_title(
    *,
    company: str | None,
    job_title: str | None,
    jd_path: Path,
) -> tuple[str, str | None]:
    """Fill in a missing company and/or job title from the JD filename.

    Values passed explicitly are kept as-is; only the blank ones are derived
    from ``jd_path``. Raises ``ValueError`` if the company cannot be resolved.
    """
    resolved_company = (company or "").strip()
    resolved_title = (job_title or "").strip()
    if resolved_company and resolved_title:
        return resolved_company, resolved_title

    parsed_company, parsed_title = parse_company_and_title_from_filename(jd_path)
    if not resolved_company:
        resolved_company = (parsed_company or "").strip()
    if not resolved_title:
        resolved_title = (parsed_title or "").strip()

    if not resolved_company:
        raise ValueError(
            "CompanyName is missing and could not be derived from filename "
            f"'{jd_path.name}'. Expected '<prefix>_<Company>_<JobTitle>' or set "
            "CompanyName explicitly."
        )
    return resolved_company, (resolved_title or None)
