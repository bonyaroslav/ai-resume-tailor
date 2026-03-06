from __future__ import annotations

from graph_router import route_next_node
from graph_state import create_initial_state
from workflow_definition import GENERATION_SECTION_IDS


def test_route_next_node_for_triage_stop_returns_end() -> None:
    state = create_initial_state("run-1")
    state.current_node = "triage_stop"
    state.status = "completed"
    assert route_next_node(state) == "end"


def test_route_next_node_review_with_retry_goes_to_generation() -> None:
    state = create_initial_state("run-1")
    state.current_node = "review"
    state.status = "awaiting_review"
    state.section_states["section_professional_summary"].status = "retry_requested"
    assert route_next_node(state) == "generate_sections"


def test_route_next_node_review_all_approved_goes_to_assemble() -> None:
    state = create_initial_state("run-1")
    state.current_node = "review"
    state.status = "awaiting_review"
    for section_id in GENERATION_SECTION_IDS:
        section_state = state.section_states[section_id]
        section_state.status = "approved"
        section_state.selected_content = f"approved {section_id}"
    assert route_next_node(state) == "assemble"


def test_route_next_node_review_waits_when_not_all_approved() -> None:
    state = create_initial_state("run-1")
    state.current_node = "review"
    state.status = "awaiting_review"
    assert route_next_node(state) == "review"
