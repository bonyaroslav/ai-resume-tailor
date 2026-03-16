from __future__ import annotations

import os
from pathlib import Path

GEMINI_MODEL_ENV = "GEMINI_MODEL"
DEFAULT_GEMINI_MODEL = "gemini-3-flash-preview"
OUTPUT_CV_FILENAME_ENV = "ART_OUTPUT_CV_FILENAME"
DEFAULT_OUTPUT_CV_FILENAME = "tailored_cv.docx"
ROLE_NAME_ENV = "ART_ROLE"
DEFAULT_ROLE_NAME = "role_senior_dotnet_engineer"
DEFAULT_TEMPLATE_FILENAME = "Default Template - Senior Software Engineer.docx"
DEFAULT_OFFLINE_FIXTURES_FILENAME = "offline_responses.example.json"


def resolve_gemini_model_name(
    explicit_model: str | None,
    *,
    metadata_model: str | None = None,
) -> str:
    if explicit_model:
        return explicit_model
    if metadata_model:
        return metadata_model
    return os.getenv(GEMINI_MODEL_ENV, DEFAULT_GEMINI_MODEL)


def resolve_role_name(
    explicit_role: str | None,
    *,
    metadata_role: str | None = None,
) -> str:
    if explicit_role and explicit_role.strip():
        return explicit_role.strip()
    if metadata_role and metadata_role.strip():
        return metadata_role.strip()
    configured = os.getenv(ROLE_NAME_ENV, DEFAULT_ROLE_NAME).strip()
    return configured or DEFAULT_ROLE_NAME


def _normalize_output_cv_filename(value: str | None) -> str | None:
    if value is None:
        return None

    candidate = value.strip()
    if not candidate:
        return None

    path = Path(candidate)
    if path.name != candidate or candidate in {".", ".."}:
        raise ValueError("Output CV filename must be a filename, not a path.")

    if not path.suffix:
        candidate = f"{candidate}.docx"
        path = Path(candidate)

    if path.suffix.lower() != ".docx":
        raise ValueError("Output CV filename must use the .docx extension.")

    return path.name


def resolve_output_cv_filename(
    explicit_filename: str | None = None,
    *,
    metadata_filename: str | None = None,
) -> str:
    if explicit_filename is not None:
        normalized = _normalize_output_cv_filename(explicit_filename)
        if normalized:
            return normalized

    if metadata_filename is not None:
        normalized = _normalize_output_cv_filename(metadata_filename)
        if normalized:
            return normalized

    configured = _normalize_output_cv_filename(os.getenv(OUTPUT_CV_FILENAME_ENV))
    if configured:
        return configured

    return DEFAULT_OUTPUT_CV_FILENAME


def role_prompts_dir(role_name: str) -> Path:
    return Path("prompts") / role_name


def role_knowledge_dir(role_name: str) -> Path:
    return Path("knowledge") / role_name


def role_offline_fixtures_dir(role_name: str) -> Path:
    return Path("offline_fixtures") / role_name


def default_template_path_for_role(role_name: str) -> Path:
    return role_knowledge_dir(role_name) / DEFAULT_TEMPLATE_FILENAME


def default_offline_fixtures_path_for_role(role_name: str) -> Path:
    return role_offline_fixtures_dir(role_name) / DEFAULT_OFFLINE_FIXTURES_FILENAME
