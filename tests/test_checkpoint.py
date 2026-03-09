from __future__ import annotations

import json
from pathlib import Path

import pytest

from checkpoint import CheckpointError, load_checkpoint, save_checkpoint
from graph_state import GraphState, create_initial_state
from tests.test_support import make_workspace_temp_dir


def test_load_checkpoint_rejects_non_object_json() -> None:
    temp_dir = make_workspace_temp_dir("checkpoint-non-object")
    checkpoint_path = temp_dir / "state_checkpoint.json"
    checkpoint_path.write_text("[]", encoding="utf-8")

    with pytest.raises(CheckpointError, match="must be an object"):
        load_checkpoint(checkpoint_path)


def test_load_checkpoint_migrates_v1_score_field() -> None:
    state = create_initial_state("run-legacy")
    state.status = "completed"
    state.current_node = "completed"
    section_id = next(iter(state.section_states.keys()))
    section_state = state.section_states[section_id]
    section_state.variations = []
    payload = state.model_dump(mode="json")
    payload["state_version"] = "1.0"
    payload["section_states"][section_id]["variations"] = [
        {
            "id": "A",
            "score_0_to_5": 4,
            "ai_reasoning": "legacy score",
            "content_for_template": "legacy content",
        }
    ]

    temp_dir = make_workspace_temp_dir("checkpoint-migrate")
    checkpoint_path = temp_dir / "state_checkpoint.json"
    checkpoint_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_checkpoint(checkpoint_path)
    migrated = loaded.section_states[section_id].variations[0]
    assert migrated.score_0_to_100 == 80


def test_save_checkpoint_wraps_os_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    state: GraphState = create_initial_state("run-write-error")
    temp_dir = make_workspace_temp_dir("checkpoint-save-error")
    checkpoint_path = temp_dir / "state_checkpoint.json"

    def _raise_os_error(self: Path, *_: object, **__: object) -> int:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", _raise_os_error)

    with pytest.raises(CheckpointError, match="Unable to write checkpoint"):
        save_checkpoint(checkpoint_path, state)
