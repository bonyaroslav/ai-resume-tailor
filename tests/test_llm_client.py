from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from llm_client import (
    DEFAULT_MAX_429_ATTEMPTS,
    LlmClientError,
    QuotaExceededError,
    _generate_with_fallback,
    _response_config,
    _response_json_schema,
)


class FakeClientError(Exception):
    def __init__(self, message: str, response_json: dict[str, object] | None) -> None:
        super().__init__(message)
        self.response_json = response_json


class FakeModels:
    def __init__(self, responses: list[object]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def generate_content(
        self, *, model: str, contents: str, config: dict[str, object]
    ) -> object:
        self.calls.append(
            {
                "model": model,
                "contents": contents,
                "config": config,
            }
        )
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _schema_error() -> FakeClientError:
    return FakeClientError(
        'Unknown name "additional_properties" at "generation_config.response_schema"',
        {
            "error": {
                "message": 'Unknown name "additional_properties"',
                "details": [
                    {
                        "fieldViolations": [
                            {
                                "field": "generation_config.response_schema",
                                "description": 'Unknown name "additional_properties"',
                            }
                        ]
                    }
                ],
            }
        },
    )


def _quota_error(*, retry_delay_seconds: int) -> FakeClientError:
    return FakeClientError(
        "request failed",
        {
            "error": {
                "code": 429,
                "message": (
                    "Quota exceeded. " f"Please retry in {retry_delay_seconds}.0s."
                ),
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": f"{retry_delay_seconds}s",
                    }
                ],
            }
        },
    )


def _daily_quota_error(*, retry_delay_seconds: int) -> FakeClientError:
    return FakeClientError(
        "request failed",
        {
            "error": {
                "code": 429,
                "message": (
                    "Quota exceeded. " f"Please retry in {retry_delay_seconds}.0s."
                ),
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                        "violations": [
                            {
                                "quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_requests",
                                "quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
                                "quotaValue": "20",
                            }
                        ],
                    },
                    {
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": f"{retry_delay_seconds}s",
                    },
                ],
            }
        },
    )


def test_response_json_schema_omits_additional_properties() -> None:
    schema = _response_json_schema()
    assert "additionalProperties" not in schema
    item_schema = schema["properties"]["variations"]["items"]
    assert "additionalProperties" not in item_schema
    assert "$defs" not in schema
    assert "$ref" not in str(schema)


def test_response_json_schema_for_experience_sections_uses_bullets_shape() -> None:
    schema = _response_json_schema("section_experience_1")
    assert "additionalProperties" not in schema
    assert schema["required"] == ["bullets"]
    bullet_schema = schema["properties"]["bullets"]["items"]
    assert bullet_schema["required"] == ["bullet_id", "variations"]
    variation_schema = bullet_schema["properties"]["variations"]["items"]
    assert "text" in variation_schema["properties"]
    assert "artifact" in variation_schema["properties"]
    assert "violations" not in variation_schema["properties"]
    assert "content_for_template" not in variation_schema["properties"]


def test_response_json_schema_for_skills_uses_meta_and_categories_shape() -> None:
    schema = _response_json_schema("section_skills_alignment")
    assert "additionalProperties" not in schema
    assert schema["required"] == ["meta", "variations"]
    meta_schema = schema["properties"]["meta"]
    assert meta_schema["required"] == [
        "jd_top_keywords",
        "covered_keywords",
        "missing_keywords_not_in_matrix",
    ]
    variation_schema = schema["properties"]["variations"]["items"]
    assert "categories" in variation_schema["properties"]
    category_schema = variation_schema["properties"]["categories"]
    assert "text" not in variation_schema["properties"]
    assert category_schema["minItems"] == 4
    assert category_schema["maxItems"] == 4
    category_item_schema = category_schema["items"]
    assert "category_name" in category_item_schema["properties"]
    assert "category_text" in category_item_schema["properties"]
    assert "content_for_template" not in variation_schema["properties"]


def test_response_json_schema_for_triage_uses_triage_result_shape() -> None:
    schema = _response_json_schema("triage_job_fit_and_risks")
    assert "additionalProperties" not in schema
    assert schema["required"] == ["triage_result"]
    triage_schema = schema["properties"]["triage_result"]
    assert "variations" not in triage_schema["properties"]
    assert "verdict" in triage_schema["properties"]
    assert "report_markdown" in triage_schema["properties"]
    assert "raw_subscores" in triage_schema["properties"]


def test_generate_with_fallback_retries_without_schema() -> None:
    response = SimpleNamespace(
        parsed={
            "variations": [
                {
                    "id": "A",
                    "score_0_to_100": 5,
                    "ai_reasoning": "ok",
                    "content_for_template": "content",
                }
            ]
        }
    )
    models = FakeModels([_schema_error(), response])
    client = SimpleNamespace(models=models)

    result = _generate_with_fallback(
        client,
        prompt="prompt",
        model="gemini-test",
    )

    assert '"id": "A"' in result.text
    assert len(models.calls) == 2
    assert models.calls[0]["config"] == _response_config(include_schema=True)
    assert models.calls[1]["config"] == _response_config(include_schema=False)


def test_generate_with_fallback_uses_experience_schema_when_section_set() -> None:
    response = SimpleNamespace(
        parsed={
            "bullets": [
                {
                    "bullet_id": 1,
                    "variations": [
                        {
                            "id": "A",
                            "score_0_to_100": 90,
                            "ai_reasoning": "reason",
                            "artifact": "dashboard",
                            "text": "text",
                        }
                    ],
                }
            ]
        }
    )
    models = FakeModels([response])
    client = SimpleNamespace(models=models)

    _generate_with_fallback(
        client,
        prompt="prompt",
        model="gemini-test",
        section_id="section_experience_2",
    )

    assert len(models.calls) == 1
    assert models.calls[0]["config"] == _response_config(
        include_schema=True,
        section_id="section_experience_2",
    )


def test_generate_with_fallback_passes_cached_content_name() -> None:
    response = SimpleNamespace(
        parsed={
            "variations": [
                {
                    "id": "A",
                    "score_0_to_100": 5,
                    "ai_reasoning": "ok",
                    "content_for_template": "content",
                }
            ]
        }
    )
    models = FakeModels([response])
    client = SimpleNamespace(models=models)

    _generate_with_fallback(
        client,
        prompt="prompt",
        model="gemini-test",
        cached_content_name="cachedContents/123",
    )

    assert models.calls[0]["config"] == _response_config(
        include_schema=True,
        cached_content_name="cachedContents/123",
    )


def test_generate_with_fallback_extracts_usage_metadata() -> None:
    response = SimpleNamespace(
        parsed={
            "variations": [
                {
                    "id": "A",
                    "score_0_to_100": 5,
                    "ai_reasoning": "ok",
                    "content_for_template": "content",
                }
            ]
        },
        usage_metadata=SimpleNamespace(
            prompt_token_count=12,
            cached_content_token_count=9,
            candidates_token_count=7,
            thoughts_token_count=3,
            total_token_count=28,
        ),
    )
    models = FakeModels([response])
    client = SimpleNamespace(models=models)

    result = _generate_with_fallback(client, prompt="prompt", model="gemini-test")

    assert result.usage_metadata.prompt_token_count == 12
    assert result.usage_metadata.cached_content_token_count == 9
    assert result.usage_metadata.total_token_count == 28


def test_generate_with_fallback_raises_readable_error_when_fallback_fails() -> None:
    models = FakeModels(
        [
            _schema_error(),
            FakeClientError(
                "request failed",
                {
                    "error": {
                        "message": "quota exhausted",
                        "details": [],
                    }
                },
            ),
        ]
    )
    client = SimpleNamespace(models=models)

    with pytest.raises(LlmClientError) as exc_info:
        _generate_with_fallback(client, prompt="prompt", model="gemini-test")

    assert "schema fallback" in str(exc_info.value)
    assert "quota exhausted" in str(exc_info.value)


def test_generate_with_fallback_retries_429_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = SimpleNamespace(
        parsed={
            "variations": [
                {
                    "id": "A",
                    "score_0_to_100": 5,
                    "ai_reasoning": "ok",
                    "content_for_template": "content",
                }
            ]
        }
    )
    models = FakeModels([_quota_error(retry_delay_seconds=1), response])
    client = SimpleNamespace(models=models)
    waits: list[float] = []

    monkeypatch.setenv("ART_LLM_MAX_429_ATTEMPTS", "5")
    monkeypatch.setenv("ART_LLM_BACKOFF_BASE_SECONDS", "0.1")
    monkeypatch.setattr("llm_client.time.sleep", lambda seconds: waits.append(seconds))

    result = _generate_with_fallback(
        client,
        prompt="prompt",
        model="gemini-test",
    )

    assert json.loads(result.text)["variations"][0]["id"] == "A"
    assert len(models.calls) == 2
    assert waits == [1.0]


def test_generate_with_fallback_raises_after_max_429_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quota_errors = [
        _quota_error(retry_delay_seconds=1) for _ in range(DEFAULT_MAX_429_ATTEMPTS)
    ]
    models = FakeModels(quota_errors)
    client = SimpleNamespace(models=models)
    waits: list[float] = []

    monkeypatch.setenv("ART_LLM_MAX_429_ATTEMPTS", "5")
    monkeypatch.setenv("ART_LLM_BACKOFF_BASE_SECONDS", "0.1")
    monkeypatch.setattr("llm_client.time.sleep", lambda seconds: waits.append(seconds))

    with pytest.raises(QuotaExceededError) as exc_info:
        _generate_with_fallback(client, prompt="prompt", model="gemini-test")

    assert exc_info.value.info.quota_scope == "unknown"
    assert len(models.calls) == DEFAULT_MAX_429_ATTEMPTS
    assert waits == [1.0, 1.0, 1.0, 1.0]


def test_generate_with_fallback_daily_quota_fails_fast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    models = FakeModels([_daily_quota_error(retry_delay_seconds=30)])
    client = SimpleNamespace(models=models)
    waits: list[float] = []

    monkeypatch.setenv("ART_LLM_MAX_429_ATTEMPTS", "5")
    monkeypatch.setenv("ART_LLM_BACKOFF_BASE_SECONDS", "0.1")
    monkeypatch.setattr("llm_client.time.sleep", lambda seconds: waits.append(seconds))

    with pytest.raises(QuotaExceededError) as exc_info:
        _generate_with_fallback(client, prompt="prompt", model="gemini-test")

    assert exc_info.value.info.quota_scope == "daily"
    assert exc_info.value.info.quota_id is not None
    assert len(models.calls) == 1
    assert waits == []
