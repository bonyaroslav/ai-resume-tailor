from __future__ import annotations

import pytest

from json_parser import (
    ResponseParseError,
    ResponseSchemaError,
    clean_llm_json,
    parse_response_envelope,
)


def test_clean_llm_json_strips_markdown_fence_and_label() -> None:
    raw = """
```json
{
  "variations": [
    {
      "id": "A",
      "score_0_to_100": 5,
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
      "score_0_to_100": 4,
      "ai_reasoning": "reason",
      "content_for_template": "content",
    }
  ],
}
"""
    envelope = parse_response_envelope(raw)
    assert envelope.variations[0].id == "A"
    assert envelope.variations[0].score_0_to_100 == 4


def test_parse_response_envelope_rejects_schema_mismatch() -> None:
    with pytest.raises(ResponseSchemaError):
        parse_response_envelope('{"variations":[{"id":"A"}]}')


def test_parse_response_envelope_rejects_legacy_score_key() -> None:
    with pytest.raises(ResponseSchemaError):
        parse_response_envelope(
            (
                '{"variations":[{"id":"A","score_0_to_5":5,'
                '"ai_reasoning":"reason","content_for_template":"content"}]}'
            )
        )


def test_parse_response_envelope_accepts_wrapped_json_with_extra_text() -> None:
    raw = """
Here is the result:
{
  "variations": [
    {
      "id": "A",
      "score_0_to_100": 4,
      "ai_reasoning": "reason",
      "content_for_template": "content"
    }
  ]
}
Thanks!
"""
    envelope = parse_response_envelope(raw)
    assert envelope.variations[0].id == "A"


def test_parse_response_envelope_reports_location_for_malformed_json() -> None:
    with pytest.raises(ResponseParseError) as exc_info:
        parse_response_envelope('{"variations":[{"id":"A" "score_0_to_100":4}]}')
    message = str(exc_info.value)
    assert "line=" in message
    assert "column=" in message
    assert "char=" in message


def test_parse_response_envelope_accepts_bom_prefix() -> None:
    raw = '\ufeff{"variations":[{"id":"A","score_0_to_100":4,"ai_reasoning":"r","content_for_template":"c"}]}'
    envelope = parse_response_envelope(raw)
    assert envelope.variations[0].id == "A"


@pytest.mark.parametrize(
    "section_id",
    ["section_experience_1", "section_experience_2", "section_experience_3"],
)
def test_parse_response_envelope_normalizes_experience_bullets_schema(
    section_id: str,
) -> None:
    raw = """
{
  "bullets": [
    {
      "bullet_id": 1,
      "variations": [
        {
          "id": "A",
          "score_0_to_100": 82,
          "ai_reasoning": "Strong JD match.",
          "artifact": "dashboard",
          "text": "Built observability dashboards for low-latency feeds."
        },
        {
          "id": "B",
          "score_0_to_100": 76,
          "ai_reasoning": "Good but less specific.",
          "artifact": "schema",
          "text": "Refactored schemas for downstream systems."
        }
      ]
    },
    {
      "bullet_id": 2,
      "variations": [
        {
          "id": "A",
          "score_0_to_100": 88,
          "ai_reasoning": "Quantified impact and ownership.",
          "artifact": "CI/CD release",
          "text": "Automated release checks and deployment gates."
        },
        {
          "id": "B",
          "score_0_to_100": 74,
          "ai_reasoning": "Credible but weaker alignment.",
          "artifact": "consumer",
          "text": "Improved consumer reliability for market data updates."
        }
      ]
    }
  ]
}
"""
    envelope = parse_response_envelope(raw, section_id=section_id)
    assert [item.id for item in envelope.variations] == ["A", "B"]
    assert envelope.variations[0].score_0_to_100 == 85
    assert (
        envelope.variations[0].content_for_template
        == "Built observability dashboards for low-latency feeds.\n"
        "Automated release checks and deployment gates."
    )


def test_parse_response_envelope_rejects_misaligned_experience_variation_ids() -> None:
    raw = """
{
  "bullets": [
    {
      "bullet_id": 1,
      "variations": [
        {
          "id": "A",
          "score_0_to_100": 80,
          "ai_reasoning": "ok",
          "artifact": "dashboard",
          "text": "Text one."
        }
      ]
    },
    {
      "bullet_id": 2,
      "variations": [
        {
          "id": "B",
          "score_0_to_100": 81,
          "ai_reasoning": "ok",
          "artifact": "schema",
          "text": "Text two."
        }
      ]
    }
  ]
}
"""
    with pytest.raises(ResponseSchemaError):
        parse_response_envelope(raw, section_id="section_experience_1")
