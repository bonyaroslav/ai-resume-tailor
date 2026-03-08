from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

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


def _response_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "variations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "score_0_to_5": {"type": "integer"},
                        "ai_reasoning": {"type": "string"},
                        "content_for_template": {"type": "string"},
                    },
                    "required": [
                        "id",
                        "score_0_to_5",
                        "ai_reasoning",
                        "content_for_template",
                    ],
                },
            }
        },
        "required": ["variations"],
    }


def _response_config(*, include_schema: bool) -> dict[str, Any]:
    config: dict[str, Any] = {"response_mime_type": "application/json"}
    if include_schema:
        config["response_json_schema"] = _response_json_schema()
    return config


def _is_schema_config_error(exc: Exception) -> bool:
    message = str(exc).lower()
    markers = (
        "response_schema",
        "response_json_schema",
        "additional_properties",
        "additionalproperties",
    )
    return any(marker in message for marker in markers)


def _extract_api_error_detail(exc: Exception) -> str:
    response_json = getattr(exc, "response_json", None)
    if not isinstance(response_json, dict):
        return str(exc)

    error = response_json.get("error")
    if not isinstance(error, dict):
        return str(exc)

    details: list[str] = []
    message = error.get("message")
    if isinstance(message, str) and message.strip():
        details.append(message.strip())

    for item in error.get("details", []):
        if not isinstance(item, dict):
            continue
        for violation in item.get("fieldViolations", []):
            if not isinstance(violation, dict):
                continue
            field = violation.get("field", "?")
            description = str(violation.get("description", "")).strip()
            details.append(f"{field}: {description}")

    return " | ".join(details) if details else str(exc)


def _request_content(
    client: Any,
    *,
    prompt: str,
    model: str,
    include_schema: bool,
) -> Any:
    return client.models.generate_content(
        model=model,
        contents=prompt,
        config=_response_config(include_schema=include_schema),
    )


def _response_to_text(response: Any) -> str:
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


def _generate_with_fallback(client: Any, *, prompt: str, model: str) -> str:
    try:
        response = _request_content(
            client,
            prompt=prompt,
            model=model,
            include_schema=True,
        )
    except Exception as exc:
        if not _is_schema_config_error(exc):
            raise LlmClientError(
                f"Gemini request failed: {_extract_api_error_detail(exc)}"
            ) from exc
        try:
            response = _request_content(
                client,
                prompt=prompt,
                model=model,
                include_schema=False,
            )
        except Exception as fallback_exc:
            raise LlmClientError(
                "Gemini request failed after schema fallback: "
                f"{_extract_api_error_detail(fallback_exc)}"
            ) from fallback_exc
    return _response_to_text(response)


def _generate_sync(prompt: str, api_key: str, model: str) -> str:
    try:
        from google import genai
    except ImportError as exc:
        raise LlmClientError("google-genai is not installed.") from exc

    client = genai.Client(api_key=api_key)
    return _generate_with_fallback(client, prompt=prompt, model=model)


async def generate_with_gemini(
    prompt: str, api_key: str, model: str, section_id: str | None = None
) -> str:
    if _offline_mode_enabled():
        return _generate_offline(section_id)
    return await asyncio.to_thread(_generate_sync, prompt, api_key, model)
