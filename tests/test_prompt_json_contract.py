from __future__ import annotations

from prompt_loader import discover_prompt_templates
from settings import (
    DEFAULT_INPUT_PROFILE,
    input_profile_knowledge_dir,
    input_profile_prompts_dir,
)

DEFAULT_REQUIRED_JSON_SCHEMA_KEYS: tuple[str, ...] = (
    '"variations"',
    '"id"',
    '"score_0_to_100"',
    '"ai_reasoning"',
    '"content_for_template"',
)

SKILLS_REQUIRED_JSON_SCHEMA_KEYS: tuple[str, ...] = (
    '"meta"',
    '"jd_top_keywords"',
    '"covered_keywords"',
    '"missing_keywords_not_in_matrix"',
    '"variations"',
    '"id"',
    '"score_0_to_100"',
    '"ai_reasoning"',
    '"categories"',
    '"category_name"',
    '"category_text"',
    "category_count",
)

EXPERIENCE_REQUIRED_JSON_SCHEMA_KEYS: tuple[str, ...] = (
    '"bullets"',
    '"bullet_id"',
    '"variations"',
    '"id"',
    '"score_0_to_100"',
    '"ai_reasoning"',
    '"artifact"',
    '"text"',
)

TRIAGE_REQUIRED_JSON_SCHEMA_KEYS: tuple[str, ...] = (
    '"triage_result"',
    '"verdict"',
    '"decision_score_0_to_100"',
    '"confidence_0_to_100"',
    '"summary"',
    '"raw_subscores"',
    '"top_reasons"',
    '"key_risks"',
    '"spain_entity_risk"',
    '"sources"',
    '"report_markdown"',
)

AUDIT_REQUIRED_MARKDOWN_HEADINGS: tuple[str, ...] = (
    "# Deep Dive CV Audit",
    "## Executive Summary",
    "## ATS Match Rate",
    "## Keyword Gap Analysis",
    "## Hiring Manager Read",
    "## Section-by-Section Critique",
    "## Evidence Gaps",
    "## Prioritized Fixes",
    "## Rewrite Directions",
    "## Final Verdict",
)


def test_active_prompts_keep_universal_json_envelope_contract() -> None:
    templates = discover_prompt_templates(
        input_profile_prompts_dir(DEFAULT_INPUT_PROFILE),
        input_profile_knowledge_dir(DEFAULT_INPUT_PROFILE),
    )

    for section_id, template in templates.items():
        if section_id == "audit_cv_deep_dive":
            for heading in AUDIT_REQUIRED_MARKDOWN_HEADINGS:
                assert (
                    heading in template.body
                ), f"Prompt '{section_id}' is missing required Markdown heading {heading}."
            assert (
                "Do not return JSON." in template.body
            ), "Prompt 'audit_cv_deep_dive' must explicitly request Markdown output."
            assert (
                '"variations"' not in template.body
            ), "Prompt 'audit_cv_deep_dive' must not require the JSON variations envelope."
            continue

        required_keys = DEFAULT_REQUIRED_JSON_SCHEMA_KEYS
        if section_id == "triage_job_fit_and_risks":
            required_keys = TRIAGE_REQUIRED_JSON_SCHEMA_KEYS
        elif section_id == "section_skills_alignment":
            required_keys = SKILLS_REQUIRED_JSON_SCHEMA_KEYS
        elif section_id.startswith("section_experience_"):
            required_keys = EXPERIENCE_REQUIRED_JSON_SCHEMA_KEYS

        for key in required_keys:
            assert (
                key in template.body
            ), f"Prompt '{section_id}' is missing required JSON key {key}."
        assert (
            "score_0_to_5" not in template.body
        ), f"Prompt '{section_id}' contains legacy score_0_to_5 field."
        if section_id == "triage_job_fit_and_risks":
            assert (
                '"variations"' not in template.body
            ), "Prompt 'triage_job_fit_and_risks' must not use variations envelope."
        if section_id == "section_skills_alignment":
            assert (
                '"content_for_template"' not in template.body
            ), "Prompt 'section_skills_alignment' must not use content_for_template."
            assert (
                '"text"' not in template.body
            ), "Prompt 'section_skills_alignment' must use categories instead of text."
