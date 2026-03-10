from __future__ import annotations

from pathlib import Path

from prompt_loader import discover_prompt_templates

REQUIRED_JSON_SCHEMA_KEYS: tuple[str, ...] = (
    '"variations"',
    '"id"',
    '"score_0_to_100"',
    '"ai_reasoning"',
    '"content_for_template"',
)


def test_active_prompts_keep_universal_json_envelope_contract() -> None:
    templates = discover_prompt_templates(Path("prompts"), Path("knowledge"))

    for section_id, template in templates.items():
        for key in REQUIRED_JSON_SCHEMA_KEYS:
            assert (
                key in template.body
            ), f"Prompt '{section_id}' is missing required JSON key {key}."
        assert (
            "score_0_to_5" not in template.body
        ), f"Prompt '{section_id}' contains legacy score_0_to_5 field."
