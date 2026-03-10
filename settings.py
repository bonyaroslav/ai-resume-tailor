from __future__ import annotations

import os

GEMINI_MODEL_ENV = "GEMINI_MODEL"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


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
