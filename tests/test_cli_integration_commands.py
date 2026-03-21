from __future__ import annotations

import sys
from pathlib import Path

import pytest

import main
from checkpoint import save_checkpoint
from graph_state import GraphState, Variation, create_initial_state
from run_artifacts import write_run_metadata
from settings import DEFAULT_GEMINI_MODEL
from tests.test_support import make_workspace_temp_dir
from workflow_definition import GENERATION_SECTION_IDS, TRIAGE_SECTION_ID


def _write_run_fixture(run_dir: Path, state: GraphState) -> None:
    run_dir.mkdir(parents=True, exist_ok=False)
    save_checkpoint(run_dir / "state_checkpoint.json", state)
    write_run_metadata(
        run_dir,
        {
            "run_id": run_dir.name,
            "company_name": "Acme",
            "job_title": "",
            "template_path": str(Path(main.DEFAULT_TEMPLATE_PATH)),
            "model_name": DEFAULT_GEMINI_MODEL,
            "debug_mode": "false",
        },
    )
    (run_dir / "job_description.md").write_text(
        "Example job description.", encoding="utf-8"
    )


def _completed_state(run_id: str) -> GraphState:
    state = create_initial_state(run_id=run_id)
    state.status = "completed"
    state.current_node = "completed"
    triage_state = state.section_states[TRIAGE_SECTION_ID]
    triage_state.status = "approved"
    triage_state.selected_content = "Proceed."
    triage_state.selected_variation_id = "A"
    triage_state.variations = [
        Variation(
            id="A",
            score_0_to_100=100,
            ai_reasoning="Proceed",
            content_for_template="Proceed.",
        )
    ]
    for section_id in GENERATION_SECTION_IDS:
        section_state = state.section_states[section_id]
        section_state.status = "approved"
        section_state.selected_content = f"Approved {section_id}"
        section_state.selected_variation_id = "A"
        section_state.variations = [
            Variation(
                id="A",
                score_0_to_100=95,
                ai_reasoning="Best",
                content_for_template=f"Approved {section_id}",
            )
        ]
    return state


def _running_state(run_id: str) -> GraphState:
    state = create_initial_state(run_id=run_id)
    state.status = "running"
    state.current_node = "review"
    return state


def _triage_stop_state(run_id: str) -> GraphState:
    state = create_initial_state(run_id=run_id)
    state.status = "completed"
    state.current_node = "triage_stop"
    return state


def test_cli_status_displays_summary_for_completed_run(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tmp_dir = make_workspace_temp_dir("cli-status")
    run_dir = tmp_dir / "acme"
    _write_run_fixture(run_dir, _completed_state(run_dir.name))

    monkeypatch.setattr(sys, "argv", ["main.py", "status", "--run-path", str(run_dir)])
    main.main()

    output = capsys.readouterr().out
    assert "Overall status: completed | Current node: completed" in output
    assert "Rebuild outputs: python main.py rebuild-output" in output


def test_cli_status_missing_checkpoint_raises_user_facing_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_dir = make_workspace_temp_dir("cli-status-missing")
    run_dir = tmp_dir / "missing-run"

    monkeypatch.setattr(sys, "argv", ["main.py", "status", "--run-path", str(run_dir)])
    with pytest.raises(SystemExit) as exc:
        main.main()
    assert "Unable to read checkpoint" in str(exc.value)


def test_cli_regenerate_rejects_triage_stop_with_clear_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_dir = make_workspace_temp_dir("cli-regenerate-triage-stop")
    run_dir = tmp_dir / "acme"
    _write_run_fixture(run_dir, _triage_stop_state(run_dir.name))

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "regenerate",
            "--run-path",
            str(run_dir),
            "--sections",
            "section_professional_summary",
            "--note",
            "add metrics",
        ],
    )
    with pytest.raises(SystemExit) as exc:
        main.main()
    assert "Cannot regenerate because this run stopped at triage." in str(exc.value)


def test_cli_regenerate_rejects_in_progress_state_with_clear_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_dir = make_workspace_temp_dir("cli-regenerate-running")
    run_dir = tmp_dir / "acme"
    _write_run_fixture(run_dir, _running_state(run_dir.name))

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "regenerate",
            "--run-path",
            str(run_dir),
            "--sections",
            "section_professional_summary",
            "--note",
            "add metrics",
        ],
    )
    with pytest.raises(SystemExit) as exc:
        main.main()
    assert "Regenerate is only available for completed runs." in str(exc.value)


def test_cli_regenerate_rejects_unknown_section_ids_with_clear_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_dir = make_workspace_temp_dir("cli-regenerate-unknown-section")
    run_dir = tmp_dir / "acme"
    _write_run_fixture(run_dir, _completed_state(run_dir.name))

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "regenerate",
            "--run-path",
            str(run_dir),
            "--sections",
            "unknown_section",
            "--note",
            "add metrics",
        ],
    )
    with pytest.raises(SystemExit) as exc:
        main.main()
    assert "Unknown section ids: unknown_section" in str(exc.value)


def test_cli_rebuild_rejects_triage_stop_with_clear_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_dir = make_workspace_temp_dir("cli-rebuild-triage-stop")
    run_dir = tmp_dir / "acme"
    _write_run_fixture(run_dir, _triage_stop_state(run_dir.name))

    monkeypatch.setattr(
        sys, "argv", ["main.py", "rebuild-output", "--run-path", str(run_dir)]
    )
    with pytest.raises(SystemExit) as exc:
        main.main()
    assert "Cannot rebuild outputs because this run stopped at triage." in str(
        exc.value
    )


def test_cli_rebuild_rejects_in_progress_state_with_clear_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_dir = make_workspace_temp_dir("cli-rebuild-running")
    run_dir = tmp_dir / "acme"
    _write_run_fixture(run_dir, _running_state(run_dir.name))

    monkeypatch.setattr(
        sys, "argv", ["main.py", "rebuild-output", "--run-path", str(run_dir)]
    )
    with pytest.raises(SystemExit) as exc:
        main.main()
    assert "Rebuild-output is only available for completed runs." in str(exc.value)


def test_cli_rebuild_rejects_when_approved_content_is_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tmp_dir = make_workspace_temp_dir("cli-rebuild-missing-approved")
    run_dir = tmp_dir / "acme"
    state = _completed_state(run_dir.name)
    state.section_states["section_professional_summary"].selected_content = None
    _write_run_fixture(run_dir, state)

    monkeypatch.setattr(
        sys, "argv", ["main.py", "rebuild-output", "--run-path", str(run_dir)]
    )
    with pytest.raises(SystemExit) as exc:
        main.main()
    output = capsys.readouterr().out
    assert "Cannot rebuild outputs because approved content is missing for:" in output
    assert "section_professional_summary" in output
    assert str(exc.value) == "Rebuild aborted: missing approved content."
