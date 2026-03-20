from __future__ import annotations

import os
from pathlib import Path

GEMINI_MODEL_ENV = "GEMINI_MODEL"
DEFAULT_GEMINI_MODEL = "gemini-3-flash-preview"
OUTPUT_CV_FILENAME_ENV = "ART_OUTPUT_CV_FILENAME"
DEFAULT_OUTPUT_CV_FILENAME = "tailored_cv.docx"
INPUT_PROFILE_ENV = "ART_INPUT_PROFILE"
LEGACY_ROLE_NAME_ENV = "ART_ROLE"
DEFAULT_INPUT_PROFILE = "role_engineer"
DEFAULT_TEMPLATE_FILENAME = "Template - YB Senior Software Engineer.docx"
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


def resolve_input_profile(
    explicit_input_profile: str | None,
    *,
    metadata_input_profile: str | None = None,
) -> str:
    if explicit_input_profile and explicit_input_profile.strip():
        return explicit_input_profile.strip()
    if metadata_input_profile and metadata_input_profile.strip():
        return metadata_input_profile.strip()
    configured = os.getenv(INPUT_PROFILE_ENV, "").strip()
    if configured:
        return configured
    legacy_configured = os.getenv(LEGACY_ROLE_NAME_ENV, "").strip()
    if legacy_configured:
        return legacy_configured
    return DEFAULT_INPUT_PROFILE


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


def input_profile_prompts_dir(input_profile: str) -> Path:
    return Path("prompts") / input_profile


def input_profile_knowledge_dir(input_profile: str) -> Path:
    return Path("knowledge") / input_profile


def input_profile_offline_fixtures_dir(input_profile: str) -> Path:
    return Path("offline_fixtures") / input_profile


def default_template_path_for_input_profile(input_profile: str) -> Path:
    return input_profile_knowledge_dir(input_profile) / DEFAULT_TEMPLATE_FILENAME


def default_offline_fixtures_path_for_input_profile(input_profile: str) -> Path:
    return (
        input_profile_offline_fixtures_dir(input_profile)
        / DEFAULT_OFFLINE_FIXTURES_FILENAME
    )
