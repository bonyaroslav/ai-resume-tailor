from __future__ import annotations

from graph_state import GraphState
from workflow_definition import GENERATION_SECTION_IDS


def _all_required_sections_approved(state: GraphState) -> bool:
    for section_id in GENERATION_SECTION_IDS:
        section_state = state.section_states[section_id]
        if not section_state.selected_content:
            return False
    return True


def _has_retry_requests(state: GraphState) -> bool:
    return any(
        state.section_states[section_id].status == "retry_requested"
        for section_id in GENERATION_SECTION_IDS
    )


def route_next_node(state: GraphState) -> str:
    if state.status in {"completed", "failed"}:
        return "end"

    if state.current_node == "triage":
        return "triage"

    if state.current_node == "triage_stop":
        return "end"

    if state.current_node == "generate_sections":
        return "generate_sections"

    if state.current_node == "review":
        if _has_retry_requests(state):
            return "generate_sections"
        if _all_required_sections_approved(state):
            return "assemble"
        return "review"

    if state.current_node == "assemble":
        return "assemble"

    if state.current_node == "audit_cv_deep_dive":
        return "audit_cv_deep_dive"

    raise ValueError(f"Unknown graph node '{state.current_node}'.")
