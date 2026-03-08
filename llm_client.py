from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

OFFLINE_MODE_ENV = "ART_OFFLINE_MODE"
OFFLINE_FIXTURES_PATH_ENV = "ART_OFFLINE_FIXTURES_PATH"
DEFAULT_OFFLINE_FIXTURES_PATH = Path("knowledge/offline_responses.example.json")
LLM_MAX_429_ATTEMPTS_ENV = "ART_LLM_MAX_429_ATTEMPTS"
LLM_BACKOFF_BASE_SECONDS_ENV = "ART_LLM_BACKOFF_BASE_SECONDS"
DEFAULT_MAX_429_ATTEMPTS = 5
DEFAULT_BACKOFF_BASE_SECONDS = 2.0


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


def _status_code_from_exception(exc: Exception) -> int | None:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    response_json = getattr(exc, "response_json", None)
    if not isinstance(response_json, dict):
        return None
    error = response_json.get("error")
    if not isinstance(error, dict):
        return None
    code = error.get("code")
    return code if isinstance(code, int) else None


def _parse_seconds(raw_value: str) -> float | None:
    value = raw_value.strip().lower()
    if not value:
        return None
    if value.endswith("s"):
        value = value[:-1]
    try:
        parsed = float(value)
    except ValueError:
        return None
    if parsed < 0:
        return None
    return parsed


def _retry_delay_seconds_from_exception(exc: Exception) -> float | None:
    response_json = getattr(exc, "response_json", None)
    if isinstance(response_json, dict):
        error = response_json.get("error")
        if isinstance(error, dict):
            for item in error.get("details", []):
                if not isinstance(item, dict):
                    continue
                raw_retry_delay = item.get("retryDelay")
                if isinstance(raw_retry_delay, str):
                    parsed = _parse_seconds(raw_retry_delay)
                    if parsed is not None:
                        return parsed

            message = error.get("message")
            if isinstance(message, str):
                match = re.search(r"retry in\s+([0-9]+(?:\.[0-9]+)?)s", message.lower())
                if match:
                    return float(match.group(1))
    return None


def _is_retryable_quota_error(exc: Exception) -> bool:
    status_code = _status_code_from_exception(exc)
    if status_code == 429:
        return True
    detail = _extract_api_error_detail(exc).lower()
    return "resource_exhausted" in detail or "quota exceeded" in detail


def _max_429_attempts() -> int:
    raw_value = os.getenv(LLM_MAX_429_ATTEMPTS_ENV, "").strip()
    if not raw_value:
        return DEFAULT_MAX_429_ATTEMPTS
    try:
        parsed = int(raw_value)
    except ValueError:
        return DEFAULT_MAX_429_ATTEMPTS
    return max(1, min(parsed, 5))


def _backoff_base_seconds() -> float:
    raw_value = os.getenv(LLM_BACKOFF_BASE_SECONDS_ENV, "").strip()
    if not raw_value:
        return DEFAULT_BACKOFF_BASE_SECONDS
    try:
        parsed = float(raw_value)
    except ValueError:
        return DEFAULT_BACKOFF_BASE_SECONDS
    return max(0.1, parsed)


def _request_content_with_backoff(
    client: Any,
    *,
    prompt: str,
    model: str,
    include_schema: bool,
) -> Any:
    logger = logging.getLogger("ai_resume_tailor")
    max_attempts = _max_429_attempts()
    base_delay_seconds = _backoff_base_seconds()

    for attempt in range(1, max_attempts + 1):
        try:
            return _request_content(
                client,
                prompt=prompt,
                model=model,
                include_schema=include_schema,
            )
        except Exception as exc:
            status_code = _status_code_from_exception(exc)
            detail = _extract_api_error_detail(exc)
            logger.warning(
                "LLM request failed attempt=%s/%s status_code=%s detail=%s",
                attempt,
                max_attempts,
                status_code if status_code is not None else "-",
                detail,
            )
            if not _is_retryable_quota_error(exc) or attempt >= max_attempts:
                raise

            retry_hint_seconds = _retry_delay_seconds_from_exception(exc)
            backoff_seconds = base_delay_seconds * (2 ** (attempt - 1))
            wait_seconds = (
                max(backoff_seconds, retry_hint_seconds)
                if retry_hint_seconds is not None
                else backoff_seconds
            )
            logger.warning(
                "LLM retry scheduled attempt=%s/%s wait_s=%.2f status_code=%s detail=%s",
                attempt + 1,
                max_attempts,
                wait_seconds,
                status_code if status_code is not None else "-",
                detail,
            )
            time.sleep(wait_seconds)


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
        response = _request_content_with_backoff(
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
            response = _request_content_with_backoff(
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
