from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

import main
from checkpoint import load_checkpoint, save_checkpoint
from graph_router import route_next_node
from graph_state import GraphState, SectionState, Variation, create_initial_state
from workflow_definition import (
    ASSEMBLE_STEP_ID,
    AUDIT_SECTION_ID,
    GENERATION_SECTION_IDS,
    PIPELINE_STEP_IDS,
    PIPELINE_STEP_LABELS,
    TRIAGE_SECTION_ID,
)


def _approved_section(section_id: str) -> SectionState:
    variation = Variation(
        id=f"{section_id}_v1",
        score_0_to_100=80,
        ai_reasoning="reason",
        content_for_template=f"content for {section_id}",
    )
    return SectionState(
        status="approved",
        variations=[variation],
        selected_variation_id=variation.id,
        selected_content=variation.content_for_template,
    )


def _completed_state(run_id: str = "run-1") -> GraphState:
    state = create_initial_state(run_id)
    state.section_states[TRIAGE_SECTION_ID] = _approved_section(TRIAGE_SECTION_ID)
    for section_id in GENERATION_SECTION_IDS:
        state.section_states[section_id] = _approved_section(section_id)
    state.section_states[AUDIT_SECTION_ID] = _approved_section(AUDIT_SECTION_ID)
    state.status = "completed"
    state.current_node = "completed"
    return state


def _feed_inputs(monkeypatch: pytest.MonkeyPatch, values: list[str]) -> None:
    iterator = iter(values)

    def fake_input(prompt: str = "") -> str:
        try:
            return next(iterator)
        except StopIteration as exc:  # exhausted feed behaves like EOF
            raise EOFError from exc

    monkeypatch.setattr("builtins.input", fake_input)


# 1. Ordering + labels -------------------------------------------------------
def test_pipeline_step_ids_order_and_labels() -> None:
    assert PIPELINE_STEP_IDS == (
        TRIAGE_SECTION_ID,
        *GENERATION_SECTION_IDS,
        ASSEMBLE_STEP_ID,
        AUDIT_SECTION_ID,
    )
    for step_id in PIPELINE_STEP_IDS:
        assert step_id in PIPELINE_STEP_LABELS


# 2. Single-step regenerate --------------------------------------------------
def test_regenerate_one_generation_step_resets_only_that_section() -> None:
    state = _completed_state()
    ok = main._regenerate_one_step(state, "section_skills_alignment", "tighten skills")
    assert ok is True

    target = state.section_states["section_skills_alignment"]
    assert target.status == "retry_requested"
    assert target.selected_content is None
    assert target.variations == []
    assert target.user_note == "tighten skills"

    other = state.section_states["section_professional_summary"]
    assert other.selected_variation_id == "section_professional_summary_v1"
    assert state.current_node == "review"
    assert state.status == "running"


def test_regenerate_one_step_triage_and_audit_set_their_nodes() -> None:
    state = _completed_state()
    assert main._regenerate_one_step(state, TRIAGE_SECTION_ID, "") is True
    assert state.current_node == "triage"
    assert state.section_states[TRIAGE_SECTION_ID].selected_content is None

    state = _completed_state()
    assert main._regenerate_one_step(state, AUDIT_SECTION_ID, "") is True
    assert state.current_node == AUDIT_SECTION_ID
    assert state.section_states[AUDIT_SECTION_ID].selected_content is None
    # generation content must remain so audit can read the existing CV
    assert state.section_states["section_experience_1"].selected_content


# 3. Cascade restart from a station -----------------------------------------
def test_restart_from_experience_2_cascades_downstream_only() -> None:
    state = _completed_state()
    main._restart_from_step(state, "section_experience_2", "redo tail")

    reset_ids = {
        "section_experience_2",
        "section_experience_3",
        "section_experience_4",
        "doc_cover_letter",
    }
    for section_id in reset_ids:
        assert state.section_states[section_id].status == "retry_requested"
        assert state.section_states[section_id].selected_content is None

    for section_id in {
        "section_professional_summary",
        "section_skills_alignment",
        "section_experience_1",
    }:
        assert state.section_states[section_id].selected_content


# 4. Cascade on tail-only stations ------------------------------------------
def test_restart_from_assemble_and_audit_touch_no_generation_sections() -> None:
    state = _completed_state()
    assert main._restart_from_step(state, ASSEMBLE_STEP_ID, "") is True
    assert state.current_node == ASSEMBLE_STEP_ID
    for section_id in GENERATION_SECTION_IDS:
        assert state.section_states[section_id].selected_content

    state = _completed_state()
    assert main._restart_from_step(state, AUDIT_SECTION_ID, "") is True
    assert state.current_node == AUDIT_SECTION_ID
    for section_id in GENERATION_SECTION_IDS:
        assert state.section_states[section_id].selected_content


# 5. Full restart wipes artifacts, keeps metadata + JD -----------------------
def test_full_restart_wipes_artifacts_and_resets_checkpoint(tmp_path: Path) -> None:
    run_dir = tmp_path / "acme_senior"
    run_dir.mkdir()
    checkpoint_path = run_dir / "state_checkpoint.json"
    save_checkpoint(checkpoint_path, _completed_state(run_dir.name))

    docx_name = "Acme - Senior.docx"
    (run_dir / "run_metadata.json").write_text(
        json.dumps({"run_id": run_dir.name, "output_cv_filename": docx_name}),
        encoding="utf-8",
    )
    (run_dir / "job_description.md").write_text("jd", encoding="utf-8")
    (run_dir / docx_name).write_text("cv", encoding="utf-8")
    (run_dir / "cover_letters.md").write_text("cl", encoding="utf-8")
    (run_dir / "company_investigation.md").write_text("ci", encoding="utf-8")
    (run_dir / "cv_deep_dive_audit.md").write_text("audit", encoding="utf-8")
    responses_dir = run_dir / "responses"
    responses_dir.mkdir()
    (responses_dir / "x.txt").write_text("x", encoding="utf-8")

    state = main._full_restart(run_dir, checkpoint_path)

    assert not (run_dir / docx_name).exists()
    assert not (run_dir / "cover_letters.md").exists()
    assert not (run_dir / "company_investigation.md").exists()
    assert not (run_dir / "cv_deep_dive_audit.md").exists()
    assert not responses_dir.exists()

    assert (run_dir / "run_metadata.json").exists()
    assert (run_dir / "job_description.md").exists()

    assert state.status == "running"
    assert state.current_node == "triage"
    reloaded = load_checkpoint(checkpoint_path)
    assert reloaded.current_node == "triage"
    assert all(
        section.status == "pending" for section in reloaded.section_states.values()
    )


# 6. Menu dispatch + non-interactive fallback --------------------------------
def _prepare_menu_run(tmp_path: Path) -> tuple[Path, Path]:
    run_dir = tmp_path / "menu_run"
    run_dir.mkdir()
    checkpoint_path = run_dir / "state_checkpoint.json"
    save_checkpoint(checkpoint_path, _completed_state(run_dir.name))
    (run_dir / "run_metadata.json").write_text(
        json.dumps({"run_id": run_dir.name, "output_cv_filename": "out.docx"}),
        encoding="utf-8",
    )
    return run_dir, checkpoint_path


def test_menu_exit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run_dir, checkpoint_path = _prepare_menu_run(tmp_path)
    monkeypatch.setattr(main, "_stdin_is_interactive", lambda: True)
    _feed_inputs(monkeypatch, ["e"])
    _, action = main._resolve_run_state_for_run_command(
        run_dir=run_dir, checkpoint_path=checkpoint_path, args=argparse.Namespace()
    )
    assert action == "exit"


def test_menu_regen_one_dispatches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_dir, checkpoint_path = _prepare_menu_run(tmp_path)
    monkeypatch.setattr(main, "_stdin_is_interactive", lambda: True)
    # step 3 == section_skills_alignment (a generation step -> note prompted)
    _feed_inputs(monkeypatch, ["o", "3", "improve metrics"])
    state, action = main._resolve_run_state_for_run_command(
        run_dir=run_dir, checkpoint_path=checkpoint_path, args=argparse.Namespace()
    )
    assert action == "resume"
    assert state.section_states["section_skills_alignment"].status == "retry_requested"
    saved = load_checkpoint(checkpoint_path)
    assert saved.section_states["section_skills_alignment"].status == "retry_requested"


def test_menu_non_interactive_defaults_to_resume(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_dir, checkpoint_path = _prepare_menu_run(tmp_path)
    monkeypatch.setattr(main, "_stdin_is_interactive", lambda: False)
    state, action = main._resolve_run_state_for_run_command(
        run_dir=run_dir, checkpoint_path=checkpoint_path, args=argparse.Namespace()
    )
    assert action == "resume"
    assert state.status == "completed"


# 7. Router integration after a cascade --------------------------------------
def test_router_resumes_generation_after_cascade() -> None:
    state = _completed_state()
    main._restart_from_step(state, "section_experience_2", "redo")
    assert route_next_node(state) == "generate_sections"
