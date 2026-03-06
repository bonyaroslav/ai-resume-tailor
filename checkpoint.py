from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from graph_state import GraphState, STATE_VERSION, touch_state


class CheckpointError(RuntimeError):
    pass


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

    version = data.get("state_version")
    if version != STATE_VERSION:
        raise CheckpointError(
            f"Unsupported checkpoint state_version '{version}'. Expected '{STATE_VERSION}'."
        )

    try:
        return GraphState.model_validate(data)
    except ValidationError as exc:
        raise CheckpointError("Checkpoint does not match GraphState contract.") from exc
