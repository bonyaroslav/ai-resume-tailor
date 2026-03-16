from __future__ import annotations

from pathlib import Path


def read_job_description(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"JD file not found: {path}")

    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8")

    raise ValueError("Job Description input must be .txt or .md.")
