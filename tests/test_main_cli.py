from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from graph_state import GraphState, SectionState, Variation, create_initial_state
from main import (
    _configure_cache_runtime_context,
    _ensure_regenerate_allowed,
    _mark_sections_for_regeneration,
    _normalize_regeneration_note,
    _parse_requested_sections,
    _resolve_run_checkpoint_pair,
    _selected_variation_score,
)


def test_parse_requested_sections_all() -> None:
    sections = _parse_requested_sections("all")
    assert "section_professional_summary" in sections
    assert "doc_cover_letter" in sections


def test_parse_requested_sections_deduplicates() -> None:
    sections = _parse_requested_sections(
        "section_professional_summary, section_professional_summary, doc_cover_letter"
    )
    assert sections == ["section_professional_summary", "doc_cover_letter"]


def test_parse_requested_sections_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        _parse_requested_sections("section_professional_summary,unknown_section")


def test_resolve_run_checkpoint_pair_from_run_path() -> None:
    args = argparse.Namespace(run_path=Path("runs/acme"), checkpoint_path=None)
    run_dir, checkpoint_path = _resolve_run_checkpoint_pair(args)
    assert run_dir == Path("runs/acme")
    assert checkpoint_path == Path("runs/acme/state_checkpoint.json")


def test_resolve_run_checkpoint_pair_from_checkpoint_path() -> None:
    args = argparse.Namespace(
        run_path=None, checkpoint_path=Path("runs/acme/state_checkpoint.json")
    )
    run_dir, checkpoint_path = _resolve_run_checkpoint_pair(args)
    assert run_dir == Path("runs/acme")
    assert checkpoint_path == Path("runs/acme/state_checkpoint.json")


def test_selected_variation_score_returns_score() -> None:
    section_state = SectionState(
        selected_variation_id="B",
        variations=[
            Variation(
                id="A",
                score_0_to_100=91,
                ai_reasoning="r1",
                content_for_template="c1",
            ),
            Variation(
                id="B",
                score_0_to_100=94,
                ai_reasoning="r2",
                content_for_template="c2",
            ),
        ],
    )
    assert _selected_variation_score(section_state) == 94


def test_selected_variation_score_returns_none_when_not_found() -> None:
    section_state = SectionState(
        selected_variation_id="Z",
        variations=[
            Variation(
                id="A",
                score_0_to_100=91,
                ai_reasoning="r1",
                content_for_template="c1",
            )
        ],
    )
    assert _selected_variation_score(section_state) is None


def test_normalize_regeneration_note_rejects_empty() -> None:
    with pytest.raises(ValueError):
        _normalize_regeneration_note("   ")


def test_normalize_regeneration_note_strips_value() -> None:
    assert _normalize_regeneration_note("  improve metrics  ") == "improve metrics"


def test_ensure_regenerate_allowed_rejects_non_completed() -> None:
    section_state = SectionState()
    state = GraphState(
        run_id="run-1",
        status="running",
        current_node="review",
        section_states={"section_professional_summary": section_state},
    )
    with pytest.raises(ValueError):
        _ensure_regenerate_allowed(state)


def test_ensure_regenerate_allowed_rejects_triage_stop() -> None:
    section_state = SectionState()
    state = GraphState(
        run_id="run-2",
        status="completed",
        current_node="triage_stop",
        section_states={"section_professional_summary": section_state},
    )
    with pytest.raises(ValueError):
        _ensure_regenerate_allowed(state)


def test_mark_sections_for_regeneration_preserves_ai_outputs() -> None:
    state = create_initial_state("run-regen")
    section_state = state.section_states["section_skills_alignment"]
    section_state.selected_variation_id = "A"
    section_state.selected_content = "Skills"
    section_state.variations = [
        Variation(
            id="A",
            score_0_to_100=97,
            ai_reasoning="best",
            content_for_template="Skills",
        )
    ]
    section_state.ai_outputs = [
        {
            "attempt": 1,
            "status": "parsed",
            "raw_response": "{}",
            "parsed_payload": {
                "meta": {
                    "jd_top_keywords": ["python"],
                    "covered_keywords": ["python"],
                    "missing_keywords_not_in_matrix": [],
                },
                "variations": [],
            },
            "normalized_payload": {"variations": []},
            "error_detail": None,
        }
    ]

    _mark_sections_for_regeneration(state, ["section_skills_alignment"], "retry")

    updated = state.section_states["section_skills_alignment"]
    assert updated.status == "retry_requested"
    assert updated.selected_content is None
    assert updated.variations == []
    assert len(updated.ai_outputs) == 1


def test_configure_cache_runtime_context_prefers_explicit_force_flag() -> None:
    context = argparse.Namespace(
        invalidate_role_wide_knowledge_cache=False,
        force_knowledge_reupload=False,
        knowledge_cache_ttl_seconds=0,
        knowledge_cache_registry_path=None,
    )

    _configure_cache_runtime_context(
        context,
        invalidate_cache=True,
        force_knowledge_reupload=True,
    )

    assert context.invalidate_role_wide_knowledge_cache is True
    assert context.force_knowledge_reupload is True
