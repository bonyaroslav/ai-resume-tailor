from __future__ import annotations

import pytest

from json_parser import ResponseSchemaError, clean_llm_json, parse_response_envelope


def test_clean_llm_json_strips_markdown_fence_and_label() -> None:
    raw = """
```json
{
  "variations": [
    {
      "id": "A",
      "score_0_to_5": 5,
      "ai_reasoning": "ok",
      "content_for_template": "hello"
    }
  ]
}
```
"""
    cleaned = clean_llm_json(raw)
    assert cleaned.startswith("{")
    assert cleaned.endswith("}")


def test_parse_response_envelope_accepts_trailing_comma() -> None:
    raw = """
{
  "variations": [
    {
      "id": "A",
      "score_0_to_5": 4,
      "ai_reasoning": "reason",
      "content_for_template": "content",
    }
  ],
}
"""
    envelope = parse_response_envelope(raw)
    assert envelope.variations[0].id == "A"
    assert envelope.variations[0].score_0_to_5 == 4


def test_parse_response_envelope_rejects_schema_mismatch() -> None:
    with pytest.raises(ResponseSchemaError):
        parse_response_envelope('{"variations":[{"id":"A"}]}')
