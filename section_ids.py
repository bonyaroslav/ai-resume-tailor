from __future__ import annotations

import re
from pathlib import Path

EXPERIENCE_SECTION_PATTERN = re.compile(r"^section_experience_(\d+)(?:_.+)?$")


def normalize_section_id(raw_section_id: str) -> str:
    section_id = raw_section_id.strip()
    match = EXPERIENCE_SECTION_PATTERN.match(section_id)
    if not match:
        return section_id
    return f"section_experience_{match.group(1)}"


def canonical_section_id_from_prompt_path(prompt_path: Path) -> str:
    stem = prompt_path.name
    if stem.endswith(".example.md"):
        stem = stem[: -len(".example.md")]
    elif stem.endswith(".md"):
        stem = stem[: -len(".md")]
    return normalize_section_id(stem)


def is_experience_section(section_id: str) -> bool:
    return EXPERIENCE_SECTION_PATTERN.match(section_id) is not None
