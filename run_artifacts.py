from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "company"


def create_run_directory(runs_dir: Path, company_name: str) -> Path:
    runs_dir.mkdir(parents=True, exist_ok=True)
    date_prefix = datetime.now(UTC).strftime("%y.%m.%d")
    slug = _slugify(company_name)
    base_name = f"{date_prefix}-{slug}"

    suffix = 1
    candidate = runs_dir / f"{base_name}-{suffix}"
    while candidate.exists():
        suffix += 1
        candidate = runs_dir / f"{base_name}-{suffix}"

    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def write_run_metadata(run_dir: Path, metadata: dict[str, str]) -> None:
    path = run_dir / "run_metadata.json"
    path.write_text(json.dumps(metadata, indent=2, ensure_ascii=True), encoding="utf-8")


def load_run_metadata(run_dir: Path) -> dict[str, str]:
    path = run_dir / "run_metadata.json"
    return json.loads(path.read_text(encoding="utf-8"))
