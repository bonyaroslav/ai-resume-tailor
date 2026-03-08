from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from graph_state import SectionState, Variation
from main import (
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
