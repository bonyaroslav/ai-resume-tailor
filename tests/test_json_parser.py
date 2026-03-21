from __future__ import annotations

import pytest

from json_parser import (
    ResponseParseError,
    ResponseSchemaError,
    clean_llm_json,
    parse_response_envelope,
    parse_response_envelope_payload,
    parse_triage_result,
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


def test_parse_response_envelope_normalizes_skills_schema_and_preserves_meta() -> None:
    raw = """
{
  "meta": {
    "jd_top_keywords": ["python", "aws"],
    "covered_keywords": ["python"],
    "missing_keywords_not_in_matrix": ["aws"]
  },
  "variations": [
    {
      "id": "A",
      "score_0_to_100": 87,
      "ai_reasoning": "Best keyword alignment.",
      "categories": [
        {"category_name": "Languages, core stack", "category_text": "Python, SQL"},
        {"category_name": "Cloud, infra", "category_text": "AWS"},
        {"category_name": "Testing, quality", "category_text": "pytest"},
        {"category_name": "Delivery, tooling", "category_text": "Docker"}
      ]
    }
  ]
}
"""
    payload = parse_response_envelope_payload(
        raw, section_id="section_skills_alignment"
    )
    envelope = parse_response_envelope(raw, section_id="section_skills_alignment")

    assert payload.parsed_payload["meta"]["jd_top_keywords"] == ["python", "aws"]
    assert envelope.variations[0].content_for_template == (
        "**Languages, core stack:** Python, SQL\n\n"
        "**Cloud, infra:** AWS\n\n"
        "**Testing, quality:** pytest\n\n"
        "**Delivery, tooling:** Docker"
    )
    assert envelope.variations[0].score_0_to_100 == 87


def test_parse_response_envelope_rejects_skills_payload_without_meta() -> None:
    raw = """
{
  "variations": [
    {
      "id": "A",
      "score_0_to_100": 87,
      "ai_reasoning": "Best keyword alignment.",
      "categories": [
        {"category_name": "Languages, core stack", "category_text": "Python, SQL"},
        {"category_name": "Cloud, infra", "category_text": "AWS"},
        {"category_name": "Testing, quality", "category_text": "pytest"},
        {"category_name": "Delivery, tooling", "category_text": "Docker"}
      ]
    }
  ]
}
"""
    with pytest.raises(ResponseSchemaError, match="meta object"):
        parse_response_envelope(raw, section_id="section_skills_alignment")


def test_parse_response_envelope_rejects_wrong_skills_category_count() -> None:
    raw = """
{
  "meta": {
    "jd_top_keywords": ["python"],
    "covered_keywords": ["python"],
    "missing_keywords_not_in_matrix": []
  },
  "variations": [
    {
      "id": "A",
      "score_0_to_100": 87,
      "ai_reasoning": "Best keyword alignment.",
      "categories": [
        {"category_name": "Languages, core stack", "category_text": "Python, SQL"},
        {"category_name": "Cloud, infra", "category_text": "AWS"},
        {"category_name": "Testing, quality", "category_text": "pytest"}
      ]
    }
  ]
}
"""
    with pytest.raises(ResponseSchemaError, match="exactly 4"):
        parse_response_envelope(raw, section_id="section_skills_alignment")


def test_parse_response_envelope_normalizes_experience_bullets_schema() -> None:
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
    envelope = parse_response_envelope(raw, section_id="section_experience_1")
    assert [item.id for item in envelope.variations] == ["A", "B"]
    assert envelope.variations[0].score_0_to_100 == 85
    assert (
        envelope.variations[0].content_for_template
        == "- Built observability dashboards for low-latency feeds.\n"
        "- Automated release checks and deployment gates."
    )


def test_parse_response_envelope_normalizes_existing_bullet_prefixes() -> None:
    raw = """
{
  "bullets": [
    {
      "bullet_id": 1,
      "variations": [
        {
          "id": "A",
          "score_0_to_100": 90,
          "ai_reasoning": "ok",
          "artifact": "service",
          "text": "- Improved service reliability."
        }
      ]
    },
    {
      "bullet_id": 2,
      "variations": [
        {
          "id": "A",
          "score_0_to_100": 92,
          "ai_reasoning": "ok",
          "artifact": "release",
          "text": "2. Hardened release automation."
        }
      ]
    }
  ]
}
"""
    envelope = parse_response_envelope(raw, section_id="section_experience_1")
    assert envelope.variations[0].content_for_template == (
        "- Improved service reliability.\n" "- Hardened release automation."
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


def test_parse_triage_result_accepts_valid_payload() -> None:
    raw = """
{
  "triage_result": {
    "verdict": "APPLY_WITH_CAVEATS",
    "decision_score_0_to_100": 76,
    "confidence_0_to_100": 70,
    "summary": "Solid fit with manageable risks.",
    "raw_subscores": {
      "technical_fit_0_to_35": 29,
      "company_risk_0_to_20": 15,
      "role_quality_0_to_15": 11,
      "spain_entity_compat_0_to_20": 12,
      "evidence_quality_0_to_10": 8
    },
    "top_reasons": ["Reason 1", "Reason 2", "Reason 3"],
    "key_risks": [
      {
        "risk": "Risk 1",
        "severity": "medium",
        "type": "uncertainty",
        "mitigation": "Ask recruiter."
      }
    ],
    "spain_entity_risk": {
      "status": "UNCLEAR",
      "confidence_0_to_100": 55,
      "explanation": "No clear policy published.",
      "recruiter_questions": ["Q1", "Q2", "Q3"]
    },
    "sources": [
      {
        "label": "Company careers",
        "url": "https://example.com/careers",
        "evidence_grade": "A",
        "used_for": "Remote policy"
      }
    ],
    "report_markdown": "### Final Verdict\\nApply with caveats."
  }
}
"""
    triage = parse_triage_result(raw)
    assert triage.verdict == "APPLY_WITH_CAVEATS"
    assert triage.decision_score_0_to_100 == 76
    assert triage.top_reasons == ["Reason 1", "Reason 2", "Reason 3"]


def test_parse_triage_result_accepts_markdown_wrapped_json() -> None:
    raw = """
```json
{
  "triage_result": {
    "verdict": "AVOID",
    "decision_score_0_to_100": 20,
    "confidence_0_to_100": 65,
    "summary": "High legal risk.",
    "raw_subscores": {
      "technical_fit_0_to_35": 18,
      "company_risk_0_to_20": 3,
      "role_quality_0_to_15": 8,
      "spain_entity_compat_0_to_20": 1,
      "evidence_quality_0_to_10": 6
    },
    "top_reasons": ["R1", "R2", "R3"],
    "key_risks": [
      {
        "risk": "Legal blocker",
        "severity": "high",
        "type": "legal_blocker",
        "mitigation": "Do not proceed."
      }
    ],
    "spain_entity_risk": {
      "status": "YES",
      "confidence_0_to_100": 80,
      "explanation": "Likely local employment requirement.",
      "recruiter_questions": ["Q1", "Q2", "Q3"]
    },
    "sources": [
      {
        "label": "Policy page",
        "url": "https://example.com/policy",
        "evidence_grade": "A",
        "used_for": "Hiring entity rules"
      }
    ],
    "report_markdown": "### Final Verdict\\nAvoid."
  }
}
```
"""
    triage = parse_triage_result(raw)
    assert triage.verdict == "AVOID"


def test_parse_triage_result_rejects_missing_triage_result() -> None:
    with pytest.raises(ResponseSchemaError):
        parse_triage_result('{"variations":[{"id":"A"}]}')


def test_parse_triage_result_rejects_wrong_verdict_value() -> None:
    raw = """
{
  "triage_result": {
    "verdict": "GO",
    "decision_score_0_to_100": 70,
    "confidence_0_to_100": 70,
    "summary": "summary",
    "raw_subscores": {
      "technical_fit_0_to_35": 25,
      "company_risk_0_to_20": 12,
      "role_quality_0_to_15": 10,
      "spain_entity_compat_0_to_20": 14,
      "evidence_quality_0_to_10": 9
    },
    "top_reasons": ["R1", "R2", "R3"],
    "key_risks": [],
    "spain_entity_risk": {
      "status": "NO",
      "confidence_0_to_100": 60,
      "explanation": "ok",
      "recruiter_questions": ["Q1", "Q2", "Q3"]
    },
    "sources": [],
    "report_markdown": "report"
  }
}
"""
    with pytest.raises(ResponseSchemaError):
        parse_triage_result(raw)
