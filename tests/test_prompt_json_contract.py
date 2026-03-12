from __future__ import annotations

from prompt_loader import discover_prompt_templates
from settings import DEFAULT_ROLE_NAME, role_knowledge_dir, role_prompts_dir

DEFAULT_REQUIRED_JSON_SCHEMA_KEYS: tuple[str, ...] = (
    '"variations"',
    '"id"',
    '"score_0_to_100"',
    '"ai_reasoning"',
    '"content_for_template"',
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


def test_active_prompts_keep_universal_json_envelope_contract() -> None:
    templates = discover_prompt_templates(
        role_prompts_dir(DEFAULT_ROLE_NAME),
        role_knowledge_dir(DEFAULT_ROLE_NAME),
    )

    for section_id, template in templates.items():
        required_keys = DEFAULT_REQUIRED_JSON_SCHEMA_KEYS
        if section_id == "triage_job_fit_and_risks":
            required_keys = TRIAGE_REQUIRED_JSON_SCHEMA_KEYS
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
