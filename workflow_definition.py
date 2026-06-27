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
    "section_experience_4",
    COVER_LETTER_SECTION_ID,
    AUDIT_SECTION_ID,
)

GENERATION_SECTION_IDS: tuple[str, ...] = (
    "section_professional_summary",
    "section_skills_alignment",
    "section_experience_1",
    "section_experience_2",
    "section_experience_3",
    "section_experience_4",
    COVER_LETTER_SECTION_ID,
)
TEMPLATE_SECTION_IDS: tuple[str, ...] = tuple(
    section_id
    for section_id in GENERATION_SECTION_IDS
    if section_id != COVER_LETTER_SECTION_ID
)

# Non-section pipeline node that assembles the final CV + cover letters document.
ASSEMBLE_STEP_ID = "assemble"

# Ordered, user-facing pipeline "stations" for the resume menu. Reuses the
# GENERATION_SECTION_IDS ordering so there is no second ordering to keep in sync.
PIPELINE_STEP_IDS: tuple[str, ...] = (
    TRIAGE_SECTION_ID,
    *GENERATION_SECTION_IDS,
    ASSEMBLE_STEP_ID,
    AUDIT_SECTION_ID,
)

PIPELINE_STEP_LABELS: dict[str, str] = {
    TRIAGE_SECTION_ID: "Triage / company investigation",
    "section_professional_summary": "Professional summary",
    "section_skills_alignment": "Skills alignment",
    "section_experience_1": "Experience 1",
    "section_experience_2": "Experience 2",
    "section_experience_3": "Experience 3",
    "section_experience_4": "Experience 4",
    COVER_LETTER_SECTION_ID: "Cover letter",
    ASSEMBLE_STEP_ID: "Assemble CV + cover letters",
    AUDIT_SECTION_ID: "CV deep-dive audit",
}


def validate_workflow_definition() -> None:
    normalized = [
        normalize_section_id(section_id) for section_id in WORKFLOW_SECTION_IDS
    ]
    if len(normalized) != len(set(normalized)):
        raise ValueError("Workflow contains duplicate canonical section_id values.")
    missing_labels = [
        step_id for step_id in PIPELINE_STEP_IDS if step_id not in PIPELINE_STEP_LABELS
    ]
    if missing_labels:
        raise ValueError(f"Pipeline steps missing labels: {', '.join(missing_labels)}")
