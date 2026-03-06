from __future__ import annotations

from graph_state import create_initial_state
from section_ids import normalize_section_id
from workflow_definition import COVER_LETTER_SECTION_ID, TEMPLATE_SECTION_IDS


def test_state_has_canonical_template_section_ids() -> None:
    state = create_initial_state("run-1")
    for section_id in TEMPLATE_SECTION_IDS:
        assert section_id in state.section_states


def test_experience_placeholder_suffix_normalizes_to_canonical_state_key() -> None:
    placeholder_name = "section_experience_2_previous"
    canonical = normalize_section_id(placeholder_name)
    state = create_initial_state("run-1")
    assert canonical in state.section_states
    assert canonical == "section_experience_2"


def test_cover_letter_is_not_template_section() -> None:
    assert COVER_LETTER_SECTION_ID not in TEMPLATE_SECTION_IDS
