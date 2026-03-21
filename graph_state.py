from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from workflow_definition import WORKFLOW_SECTION_IDS

STATE_VERSION = "1.2"


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class Variation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str
    score_0_to_100: int = Field(ge=0, le=100)
    ai_reasoning: str
    content_for_template: str


class AiOutputRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt: int = Field(ge=1)
    status: Literal["received", "parsed", "parse_error", "schema_error"]
    raw_response: str
    parsed_payload: dict[str, object] | None = None
    normalized_payload: dict[str, object] | None = None
    error_detail: str | None = None


class ResponseEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variations: list[Variation]


class TriageRawSubscores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    technical_fit_0_to_35: int = Field(ge=0, le=35)
    company_risk_0_to_20: int = Field(ge=0, le=20)
    role_quality_0_to_15: int = Field(ge=0, le=15)
    spain_entity_compat_0_to_20: int = Field(ge=0, le=20)
    evidence_quality_0_to_10: int = Field(ge=0, le=10)


class TriageRisk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk: str
    severity: Literal["high", "medium", "low"]
    type: Literal["interview_blocker", "legal_blocker", "learnable", "uncertainty"]
    mitigation: str


class TriageSpainEntityRisk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["YES", "NO", "UNCLEAR"]
    confidence_0_to_100: int = Field(ge=0, le=100)
    explanation: str
    recruiter_questions: list[str] = Field(min_length=3, max_length=3)


class TriageSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    url: str
    evidence_grade: Literal["A", "B", "C", "D"]
    used_for: str


class TriageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Literal["APPLY", "APPLY_WITH_CAVEATS", "AVOID"]
    decision_score_0_to_100: int = Field(ge=0, le=100)
    confidence_0_to_100: int = Field(ge=0, le=100)
    summary: str
    raw_subscores: TriageRawSubscores
    top_reasons: list[str] = Field(min_length=3, max_length=3)
    key_risks: list[TriageRisk]
    spain_entity_risk: TriageSpainEntityRisk
    sources: list[TriageSource]
    report_markdown: str


class SectionState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "pending"
    variations: list[Variation] = Field(default_factory=list)
    selected_variation_id: str | None = None
    selected_content: str | None = None
    user_note: str | None = None
    retry_count: int = 0
    ai_outputs: list[AiOutputRecord] = Field(default_factory=list)


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
