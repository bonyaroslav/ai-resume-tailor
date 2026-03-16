from __future__ import annotations

from section_ids import normalize_section_id

TRIAGE_SECTION_ID = "triage_job_fit_and_risks"
COVER_LETTER_SECTION_ID = "doc_cover_letter"
AUDIT_SECTION_ID = "audit_cv_deep_dive"

WORKFLOW_SECTION_IDS: tuple[str, ...] = (
    TRIAGE_SECTION_ID,
    "section_professional_summary",
    "section_skills_alignment",
    "section_experience_1",
    "section_experience_2",
    "section_experience_3",
    COVER_LETTER_SECTION_ID,
    AUDIT_SECTION_ID,
)

GENERATION_SECTION_IDS: tuple[str, ...] = (
    "section_professional_summary",
    "section_skills_alignment",
    "section_experience_1",
    "section_experience_2",
    "section_experience_3",
    COVER_LETTER_SECTION_ID,
)
TEMPLATE_SECTION_IDS: tuple[str, ...] = tuple(
    section_id
    for section_id in GENERATION_SECTION_IDS
    if section_id != COVER_LETTER_SECTION_ID
)


def validate_workflow_definition() -> None:
    normalized = [
        normalize_section_id(section_id) for section_id in WORKFLOW_SECTION_IDS
    ]
    if len(normalized) != len(set(normalized)):
        raise ValueError("Workflow contains duplicate canonical section_id values.")
