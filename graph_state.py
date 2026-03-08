from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from workflow_definition import WORKFLOW_SECTION_IDS

STATE_VERSION = "1.1"


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class Variation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str
    score_0_to_100: int = Field(ge=0, le=100)
    ai_reasoning: str
    content_for_template: str


class ResponseEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variations: list[Variation]


class SectionState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "pending"
    variations: list[Variation] = Field(default_factory=list)
    selected_variation_id: str | None = None
    selected_content: str | None = None
    user_note: str | None = None
    retry_count: int = 0


class GraphState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state_version: str = STATE_VERSION
    run_id: str
    status: Literal["running", "awaiting_review", "completed", "failed"] = "running"
    current_node: str = "triage"
    section_states: dict[str, SectionState] = Field(default_factory=dict)
    review_queue: list[str] = Field(default_factory=list)
    updated_at: str = Field(default_factory=utc_now_iso)


def create_initial_state(run_id: str) -> GraphState:
    section_states = {section_id: SectionState() for section_id in WORKFLOW_SECTION_IDS}
    return GraphState(run_id=run_id, section_states=section_states)


def touch_state(state: GraphState) -> None:
    state.updated_at = utc_now_iso()
