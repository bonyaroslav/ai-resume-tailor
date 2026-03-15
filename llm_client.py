from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from settings import default_offline_fixtures_path_for_role, resolve_role_name
from section_ids import is_experience_section
from workflow_definition import TRIAGE_SECTION_ID

SKILLS_SECTION_ID = "section_skills_alignment"
DEFAULT_SKILLS_CATEGORY_COUNT = 4

OFFLINE_MODE_ENV = "ART_OFFLINE_MODE"
OFFLINE_FIXTURES_PATH_ENV = "ART_OFFLINE_FIXTURES_PATH"
LLM_MAX_429_ATTEMPTS_ENV = "ART_LLM_MAX_429_ATTEMPTS"
LLM_BACKOFF_BASE_SECONDS_ENV = "ART_LLM_BACKOFF_BASE_SECONDS"
LLM_MAX_TOTAL_WAIT_SECONDS_ENV = "ART_LLM_MAX_TOTAL_WAIT_SECONDS"
DEFAULT_MAX_429_ATTEMPTS = 5
DEFAULT_BACKOFF_BASE_SECONDS = 2.0
DEFAULT_MAX_TOTAL_WAIT_SECONDS = 300.0


class LlmClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class QuotaErrorInfo:
    status_code: int | None
    detail: str
    retry_delay_seconds: float | None
    quota_id: str | None
    quota_metric: str | None
    quota_value: str | None
    quota_scope: str
    section_id: str | None = None


class QuotaExceededError(LlmClientError):
    def __init__(self, info: QuotaErrorInfo) -> None:
        super().__init__(info.detail)
        self.info = info

    @property
    def section_id(self) -> str | None:
        return self.info.section_id

    def with_section_id(self, section_id: str) -> QuotaExceededError:
        if self.info.section_id:
            return self
        updated = QuotaErrorInfo(
            status_code=self.info.status_code,
            detail=self.info.detail,
            retry_delay_seconds=self.info.retry_delay_seconds,
            quota_id=self.info.quota_id,
            quota_metric=self.info.quota_metric,
            quota_value=self.info.quota_value,
            quota_scope=self.info.quota_scope,
            section_id=section_id,
        )
        return QuotaExceededError(updated)


@dataclass(frozen=True)
class UsageMetadata:
    prompt_token_count: int | None = None
    cached_content_token_count: int | None = None
    candidates_token_count: int | None = None
    thoughts_token_count: int | None = None
    total_token_count: int | None = None


@dataclass(frozen=True)
class LlmGenerationResult:
    text: str
    usage_metadata: UsageMetadata


def _is_truthy_env(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _offline_mode_enabled() -> bool:
    return _is_truthy_env(os.getenv(OFFLINE_MODE_ENV))


def _load_offline_fixtures() -> dict[str, dict[str, Any]]:
    configured = os.getenv(OFFLINE_FIXTURES_PATH_ENV, "").strip()
    path = Path(configured) if configured else _default_offline_fixtures_path()
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


def _default_offline_fixtures_path() -> Path:
    role_name = resolve_role_name(explicit_role=None)
    return default_offline_fixtures_path_for_role(role_name)


def _generate_offline(section_id: str | None) -> LlmGenerationResult:
    if not section_id:
        raise LlmClientError("Offline mode requires a section_id for fixture lookup.")
    fixtures = _load_offline_fixtures()
    payload = fixtures.get(section_id)
    if payload is None:
        raise LlmClientError(
            f"Missing offline fixture payload for section_id '{section_id}'."
        )
    return LlmGenerationResult(text=json.dumps(payload), usage_metadata=UsageMetadata())


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


def _extract_usage_metadata(response: Any) -> UsageMetadata:
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return UsageMetadata()
    return UsageMetadata(
        prompt_token_count=getattr(usage, "prompt_token_count", None),
        cached_content_token_count=getattr(usage, "cached_content_token_count", None),
        candidates_token_count=getattr(usage, "candidates_token_count", None),
        thoughts_token_count=getattr(usage, "thoughts_token_count", None),
        total_token_count=getattr(usage, "total_token_count", None),
    )


def _response_json_schema(
    section_id: str | None = None,
    skills_category_count: int = DEFAULT_SKILLS_CATEGORY_COUNT,
) -> dict[str, Any]:
    if section_id == TRIAGE_SECTION_ID:
        return {
            "type": "object",
            "properties": {
                "triage_result": {
                    "type": "object",
                    "properties": {
                        "verdict": {"type": "string"},
                        "decision_score_0_to_100": {"type": "integer"},
                        "confidence_0_to_100": {"type": "integer"},
                        "summary": {"type": "string"},
                        "raw_subscores": {
                            "type": "object",
                            "properties": {
                                "technical_fit_0_to_35": {"type": "integer"},
                                "company_risk_0_to_20": {"type": "integer"},
                                "role_quality_0_to_15": {"type": "integer"},
                                "spain_entity_compat_0_to_20": {"type": "integer"},
                                "evidence_quality_0_to_10": {"type": "integer"},
                            },
                            "required": [
                                "technical_fit_0_to_35",
                                "company_risk_0_to_20",
                                "role_quality_0_to_15",
                                "spain_entity_compat_0_to_20",
                                "evidence_quality_0_to_10",
                            ],
                        },
                        "top_reasons": {"type": "array", "items": {"type": "string"}},
                        "key_risks": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "risk": {"type": "string"},
                                    "severity": {"type": "string"},
                                    "type": {"type": "string"},
                                    "mitigation": {"type": "string"},
                                },
                                "required": ["risk", "severity", "type", "mitigation"],
                            },
                        },
                        "spain_entity_risk": {
                            "type": "object",
                            "properties": {
                                "status": {"type": "string"},
                                "confidence_0_to_100": {"type": "integer"},
                                "explanation": {"type": "string"},
                                "recruiter_questions": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": [
                                "status",
                                "confidence_0_to_100",
                                "explanation",
                                "recruiter_questions",
                            ],
                        },
                        "sources": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "label": {"type": "string"},
                                    "url": {"type": "string"},
                                    "evidence_grade": {"type": "string"},
                                    "used_for": {"type": "string"},
                                },
                                "required": [
                                    "label",
                                    "url",
                                    "evidence_grade",
                                    "used_for",
                                ],
                            },
                        },
                        "report_markdown": {"type": "string"},
                    },
                    "required": [
                        "verdict",
                        "decision_score_0_to_100",
                        "confidence_0_to_100",
                        "summary",
                        "raw_subscores",
                        "top_reasons",
                        "key_risks",
                        "spain_entity_risk",
                        "sources",
                        "report_markdown",
                    ],
                }
            },
            "required": ["triage_result"],
        }

    if section_id is not None and is_experience_section(section_id):
        return {
            "type": "object",
            "properties": {
                "bullets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "bullet_id": {"type": "integer"},
                            "variations": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "string"},
                                        "score_0_to_100": {"type": "integer"},
                                        "ai_reasoning": {"type": "string"},
                                        "artifact": {"type": "string"},
                                        "text": {"type": "string"},
                                    },
                                    "required": [
                                        "id",
                                        "score_0_to_100",
                                        "ai_reasoning",
                                        "artifact",
                                        "text",
                                    ],
                                },
                            },
                        },
                        "required": ["bullet_id", "variations"],
                    },
                }
            },
            "required": ["bullets"],
        }

    if section_id == SKILLS_SECTION_ID:
        return {
            "type": "object",
            "properties": {
                "meta": {
                    "type": "object",
                    "properties": {
                        "jd_top_keywords": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "covered_keywords": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "missing_keywords_not_in_matrix": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": [
                        "jd_top_keywords",
                        "covered_keywords",
                        "missing_keywords_not_in_matrix",
                    ],
                },
                "variations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "score_0_to_100": {"type": "integer"},
                            "ai_reasoning": {"type": "string"},
                            "categories": {
                                "type": "array",
                                "minItems": skills_category_count,
                                "maxItems": skills_category_count,
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "category_name": {"type": "string"},
                                        "category_text": {"type": "string"},
                                    },
                                    "required": [
                                        "category_name",
                                        "category_text",
                                    ],
                                },
                            },
                        },
                        "required": [
                            "id",
                            "score_0_to_100",
                            "ai_reasoning",
                            "categories",
                        ],
                    },
                },
            },
            "required": ["meta", "variations"],
        }

    return {
        "type": "object",
        "properties": {
            "variations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "score_0_to_100": {"type": "integer"},
                        "ai_reasoning": {"type": "string"},
                        "content_for_template": {"type": "string"},
                    },
                    "required": [
                        "id",
                        "score_0_to_100",
                        "ai_reasoning",
                        "content_for_template",
                    ],
                },
            }
        },
        "required": ["variations"],
    }


def _response_config(
    *,
    include_schema: bool,
    section_id: str | None = None,
    cached_content_name: str | None = None,
    skills_category_count: int = DEFAULT_SKILLS_CATEGORY_COUNT,
) -> dict[str, Any]:
    config: dict[str, Any] = {"response_mime_type": "application/json"}
    if include_schema:
        config["response_json_schema"] = _response_json_schema(
            section_id,
            skills_category_count=skills_category_count,
        )
    if cached_content_name:
        config["cached_content"] = cached_content_name
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


def _quota_violation_from_exception(exc: Exception) -> dict[str, str] | None:
    response_json = getattr(exc, "response_json", None)
    if not isinstance(response_json, dict):
        return None
    error = response_json.get("error")
    if not isinstance(error, dict):
        return None
    for item in error.get("details", []):
        if not isinstance(item, dict):
            continue
        violations = item.get("violations")
        if not isinstance(violations, list):
            continue
        for violation in violations:
            if isinstance(violation, dict):
                return {
                    "quota_id": str(violation.get("quotaId", "")).strip(),
                    "quota_metric": str(violation.get("quotaMetric", "")).strip(),
                    "quota_value": str(violation.get("quotaValue", "")).strip(),
                }
    return None


def _quota_scope_from_quota_id(quota_id: str | None) -> str:
    if not quota_id:
        return "unknown"
    lowered = quota_id.lower()
    if "perday" in lowered:
        return "daily"
    if "perminute" in lowered:
        return "minute"
    return "unknown"


def _build_quota_error_info(exc: Exception) -> QuotaErrorInfo:
    violation = _quota_violation_from_exception(exc) or {}
    quota_id = violation.get("quota_id") or None
    return QuotaErrorInfo(
        status_code=_status_code_from_exception(exc),
        detail=_extract_api_error_detail(exc),
        retry_delay_seconds=_retry_delay_seconds_from_exception(exc),
        quota_id=quota_id,
        quota_metric=violation.get("quota_metric") or None,
        quota_value=violation.get("quota_value") or None,
        quota_scope=_quota_scope_from_quota_id(quota_id),
    )


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


def _max_total_wait_seconds() -> float:
    raw_value = os.getenv(LLM_MAX_TOTAL_WAIT_SECONDS_ENV, "").strip()
    if not raw_value:
        return DEFAULT_MAX_TOTAL_WAIT_SECONDS
    try:
        parsed = float(raw_value)
    except ValueError:
        return DEFAULT_MAX_TOTAL_WAIT_SECONDS
    return max(0.0, parsed)


def _request_content_with_backoff(
    client: Any,
    *,
    prompt: str,
    model: str,
    include_schema: bool,
    section_id: str | None = None,
    cached_content_name: str | None = None,
    skills_category_count: int = DEFAULT_SKILLS_CATEGORY_COUNT,
) -> Any:
    logger = logging.getLogger("ai_resume_tailor")
    max_attempts = _max_429_attempts()
    base_delay_seconds = _backoff_base_seconds()
    max_total_wait_seconds = _max_total_wait_seconds()
    waited_seconds_total = 0.0

    for attempt in range(1, max_attempts + 1):
        try:
            return _request_content(
                client,
                prompt=prompt,
                model=model,
                include_schema=include_schema,
                section_id=section_id,
                cached_content_name=cached_content_name,
                skills_category_count=skills_category_count,
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
            if not _is_retryable_quota_error(exc):
                raise

            quota_info = _build_quota_error_info(exc)
            if quota_info.quota_scope == "daily":
                logger.error(
                    "LLM quota exhausted scope=%s quota_id=%s metric=%s value=%s",
                    quota_info.quota_scope,
                    quota_info.quota_id or "-",
                    quota_info.quota_metric or "-",
                    quota_info.quota_value or "-",
                )
                raise QuotaExceededError(quota_info) from exc

            if attempt >= max_attempts:
                raise QuotaExceededError(quota_info) from exc

            retry_hint_seconds = quota_info.retry_delay_seconds
            backoff_seconds = base_delay_seconds * (2 ** (attempt - 1))
            wait_seconds = (
                max(backoff_seconds, retry_hint_seconds)
                if retry_hint_seconds is not None
                else backoff_seconds
            )
            remaining_wait_budget = max_total_wait_seconds - waited_seconds_total
            if remaining_wait_budget <= 0:
                raise QuotaExceededError(quota_info) from exc
            if wait_seconds > remaining_wait_budget:
                wait_seconds = remaining_wait_budget
            if wait_seconds <= 0:
                raise QuotaExceededError(quota_info) from exc

            logger.warning(
                "LLM retry scheduled attempt=%s/%s wait_s=%.2f status_code=%s detail=%s",
                attempt + 1,
                max_attempts,
                wait_seconds,
                status_code if status_code is not None else "-",
                detail,
            )
            time.sleep(wait_seconds)
            waited_seconds_total += wait_seconds

    raise LlmClientError("LLM request failed after retry loop.")


def _request_content(
    client: Any,
    *,
    prompt: str,
    model: str,
    include_schema: bool,
    section_id: str | None = None,
    cached_content_name: str | None = None,
    skills_category_count: int = DEFAULT_SKILLS_CATEGORY_COUNT,
) -> Any:
    from google.genai import types

    return client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            **_response_config(
                include_schema=include_schema,
                section_id=section_id,
                cached_content_name=cached_content_name,
                skills_category_count=skills_category_count,
            )
        ),
    )


def _response_to_text(response: Any) -> LlmGenerationResult:
    parsed = getattr(response, "parsed", None)
    if parsed is not None:
        if hasattr(parsed, "model_dump"):
            parsed = parsed.model_dump()
        try:
            return LlmGenerationResult(
                text=json.dumps(parsed, ensure_ascii=False),
                usage_metadata=_extract_usage_metadata(response),
            )
        except TypeError:
            pass

    text = _extract_text(response)
    if not text:
        raise LlmClientError("Gemini response did not include text output.")
    return LlmGenerationResult(
        text=text, usage_metadata=_extract_usage_metadata(response)
    )


def _generate_with_fallback(
    client: Any,
    *,
    prompt: str,
    model: str,
    section_id: str | None = None,
    cached_content_name: str | None = None,
    skills_category_count: int = DEFAULT_SKILLS_CATEGORY_COUNT,
) -> LlmGenerationResult:
    try:
        response = _request_content_with_backoff(
            client,
            prompt=prompt,
            model=model,
            include_schema=True,
            section_id=section_id,
            cached_content_name=cached_content_name,
            skills_category_count=skills_category_count,
        )
    except Exception as exc:
        if isinstance(exc, QuotaExceededError):
            raise
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
                section_id=section_id,
                cached_content_name=cached_content_name,
                skills_category_count=skills_category_count,
            )
        except Exception as fallback_exc:
            if isinstance(fallback_exc, QuotaExceededError):
                raise
            raise LlmClientError(
                "Gemini request failed after schema fallback: "
                f"{_extract_api_error_detail(fallback_exc)}"
            ) from fallback_exc
    return _response_to_text(response)


def _generate_sync(
    prompt: str,
    api_key: str,
    model: str,
    section_id: str | None = None,
    cached_content_name: str | None = None,
    skills_category_count: int = DEFAULT_SKILLS_CATEGORY_COUNT,
) -> LlmGenerationResult:
    try:
        from google import genai
    except ImportError as exc:
        raise LlmClientError("google-genai is not installed.") from exc

    client = genai.Client(api_key=api_key)
    return _generate_with_fallback(
        client,
        prompt=prompt,
        model=model,
        section_id=section_id,
        cached_content_name=cached_content_name,
        skills_category_count=skills_category_count,
    )


async def generate_with_gemini(
    prompt: str,
    api_key: str,
    model: str,
    section_id: str | None = None,
    cached_content_name: str | None = None,
    skills_category_count: int = DEFAULT_SKILLS_CATEGORY_COUNT,
) -> LlmGenerationResult:
    if _offline_mode_enabled():
        return _generate_offline(section_id)
    return await asyncio.to_thread(
        _generate_sync,
        prompt,
        api_key,
        model,
        section_id,
        cached_content_name,
        skills_category_count,
    )
