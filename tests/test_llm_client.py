from __future__ import annotations

from types import SimpleNamespace

import pytest

from llm_client import (
    LlmClientError,
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


def test_response_json_schema_omits_additional_properties() -> None:
    schema = _response_json_schema()
    assert "additionalProperties" not in schema
    item_schema = schema["properties"]["variations"]["items"]
    assert "additionalProperties" not in item_schema
    assert "$defs" not in schema
    assert "$ref" not in str(schema)


def test_generate_with_fallback_retries_without_schema() -> None:
    response = SimpleNamespace(
        parsed={
            "variations": [
                {
                    "id": "A",
                    "score_0_to_5": 5,
                    "ai_reasoning": "ok",
                    "content_for_template": "content",
                }
            ]
        }
    )
    models = FakeModels([_schema_error(), response])
    client = SimpleNamespace(models=models)

    result = _generate_with_fallback(client, prompt="prompt", model="gemini-test")

    assert '"id": "A"' in result
    assert len(models.calls) == 2
    assert models.calls[0]["config"] == _response_config(include_schema=True)
    assert models.calls[1]["config"] == _response_config(include_schema=False)


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
