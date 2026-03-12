from __future__ import annotations

import os
from pathlib import Path

GEMINI_MODEL_ENV = "GEMINI_MODEL"
DEFAULT_GEMINI_MODEL = "gemini-3-flash-preview"
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


def role_prompts_dir(role_name: str) -> Path:
    return Path("prompts") / role_name


def role_knowledge_dir(role_name: str) -> Path:
    return Path("knowledge") / role_name


def default_template_path_for_role(role_name: str) -> Path:
    return role_knowledge_dir(role_name) / DEFAULT_TEMPLATE_FILENAME


def default_offline_fixtures_path_for_role(role_name: str) -> Path:
    return role_knowledge_dir(role_name) / DEFAULT_OFFLINE_FIXTURES_FILENAME
