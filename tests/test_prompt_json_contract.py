from __future__ import annotations

from pathlib import Path

from prompt_loader import discover_prompt_templates

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


def test_active_prompts_keep_universal_json_envelope_contract() -> None:
    templates = discover_prompt_templates(Path("prompts"), Path("knowledge"))

    for section_id, template in templates.items():
        required_keys = DEFAULT_REQUIRED_JSON_SCHEMA_KEYS
        if section_id.startswith("section_experience_"):
            required_keys = EXPERIENCE_REQUIRED_JSON_SCHEMA_KEYS

        for key in required_keys:
            assert (
                key in template.body
            ), f"Prompt '{section_id}' is missing required JSON key {key}."
        assert (
            "score_0_to_5" not in template.body
        ), f"Prompt '{section_id}' contains legacy score_0_to_5 field."
