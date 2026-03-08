from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from graph_state import GraphState, STATE_VERSION, touch_state


class CheckpointError(RuntimeError):
    pass


def _migrate_state_v1_0_to_v1_1(data: dict[str, object]) -> dict[str, object]:
    section_states = data.get("section_states")
    if not isinstance(section_states, dict):
        data["state_version"] = "1.1"
        return data

    for section_state in section_states.values():
        if not isinstance(section_state, dict):
            continue
        variations = section_state.get("variations")
        if not isinstance(variations, list):
            continue
        for variation in variations:
            if not isinstance(variation, dict):
                continue
            legacy_score = variation.pop("score_0_to_5", None)
            if isinstance(legacy_score, int):
                variation["score_0_to_100"] = max(0, min(100, legacy_score * 20))
    data["state_version"] = "1.1"
    return data


def _migrate_checkpoint_data(data: dict[str, object]) -> dict[str, object]:
    version = data.get("state_version")
    if version == "1.1":
        return data
    if version == "1.0":
        return _migrate_state_v1_0_to_v1_1(data)
    raise CheckpointError(
        f"Unsupported checkpoint state_version '{version}'. Expected '1.1'."
    )


def save_checkpoint(checkpoint_path: Path, state: GraphState) -> None:
    touch_state(state)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = checkpoint_path.with_suffix(checkpoint_path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(state.model_dump(mode="json"), indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    temp_path.replace(checkpoint_path)


def load_checkpoint(checkpoint_path: Path) -> GraphState:
    try:
        raw = checkpoint_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CheckpointError(f"Unable to read checkpoint: {checkpoint_path}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CheckpointError(f"Checkpoint is corrupt JSON: {checkpoint_path}") from exc

    data = _migrate_checkpoint_data(data)
    if data.get("state_version") != STATE_VERSION:
        raise CheckpointError(
            "Checkpoint migration failed to match GraphState state_version."
        )

    try:
        return GraphState.model_validate(data)
    except ValidationError as exc:
        raise CheckpointError("Checkpoint does not match GraphState contract.") from exc
