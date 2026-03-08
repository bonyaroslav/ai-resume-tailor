from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from graph_state import ResponseEnvelope

OFFLINE_MODE_ENV = "ART_OFFLINE_MODE"
OFFLINE_FIXTURES_PATH_ENV = "ART_OFFLINE_FIXTURES_PATH"
DEFAULT_OFFLINE_FIXTURES_PATH = Path("knowledge/offline_responses.example.json")


class LlmClientError(RuntimeError):
    pass


def _is_truthy_env(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _offline_mode_enabled() -> bool:
    return _is_truthy_env(os.getenv(OFFLINE_MODE_ENV))


def _load_offline_fixtures() -> dict[str, dict[str, Any]]:
    configured = os.getenv(OFFLINE_FIXTURES_PATH_ENV, "").strip()
    path = Path(configured) if configured else DEFAULT_OFFLINE_FIXTURES_PATH
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LlmClientError(f"Offline fixture file not found: {path}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LlmClientError(f"Offline fixture file is invalid JSON: {path}") from exc

    if not isinstance(data, dict):
        raise LlmClientError(
            "Offline fixture JSON must be an object keyed by section_id."
        )
    return data


def _generate_offline(section_id: str | None) -> str:
    if not section_id:
        raise LlmClientError("Offline mode requires a section_id for fixture lookup.")
    fixtures = _load_offline_fixtures()
    payload = fixtures.get(section_id)
    if payload is None:
        raise LlmClientError(
            f"Missing offline fixture payload for section_id '{section_id}'."
        )
    return json.dumps(payload)


def _extract_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text

    candidates = getattr(response, "candidates", None)
    if not candidates:
        return ""

    parts: list[str] = []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        if content is None:
            continue
        candidate_parts = getattr(content, "parts", None)
        if not candidate_parts:
            continue
        for part in candidate_parts:
            piece = getattr(part, "text", None)
            if isinstance(piece, str):
                parts.append(piece)
    return "\n".join(parts).strip()


def _response_config() -> dict[str, Any]:
    return {
        "response_mime_type": "application/json",
        "response_schema": ResponseEnvelope,
    }


def _generate_sync(prompt: str, api_key: str, model: str) -> str:
    try:
        from google import genai
    except ImportError as exc:
        raise LlmClientError("google-genai is not installed.") from exc

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model, contents=prompt, config=_response_config()
    )
    parsed = getattr(response, "parsed", None)
    if parsed is not None:
        if hasattr(parsed, "model_dump"):
            parsed = parsed.model_dump()
        try:
            return json.dumps(parsed, ensure_ascii=False)
        except TypeError:
            pass
    text = _extract_text(response)
    if not text:
        raise LlmClientError("Gemini response did not include text output.")
    return text


async def generate_with_gemini(
    prompt: str, api_key: str, model: str, section_id: str | None = None
) -> str:
    if _offline_mode_enabled():
        return _generate_offline(section_id)
    return await asyncio.to_thread(_generate_sync, prompt, api_key, model)
