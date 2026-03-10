from __future__ import annotations

import asyncio
import json
from pathlib import Path

from docx import Document

import graph_nodes
from checkpoint import load_checkpoint
from graph_nodes import RuntimeContext
from graph_state import GraphState, create_initial_state
from main import _run_graph
from prompt_loader import PromptTemplate
from tests.test_support import make_workspace_temp_dir
from workflow_definition import (
    GENERATION_SECTION_IDS,
    TEMPLATE_SECTION_IDS,
    WORKFLOW_SECTION_IDS,
)


def _make_template(path: Path) -> None:
    document = Document()
    document.add_paragraph("Summary: {{section_professional_summary}}")
    document.add_paragraph("Skills: {{section_skills_alignment}}")
    document.add_paragraph("Exp1: {{section_experience_1_oldest}}")
    document.add_paragraph("Exp2: {{section_experience_2_previous}}")
    document.add_paragraph("Exp3: {{section_experience_3_latest}}")
    document.save(path)


def _build_prompt_templates(run_dir: Path) -> dict[str, PromptTemplate]:
    templates: dict[str, PromptTemplate] = {}
    for section_id in WORKFLOW_SECTION_IDS:
        templates[section_id] = PromptTemplate(
            section_id=section_id,
            path=run_dir / f"{section_id}.md",
            body=f"SECTION_ID: {section_id}",
            knowledge_files=[],
        )
    return templates


def _build_runtime_context(run_dir: Path, template_path: Path) -> RuntimeContext:
    return RuntimeContext(
        run_dir=run_dir,
        checkpoint_path=run_dir / "state_checkpoint.json",
        template_path=template_path,
        output_cv_path=run_dir / "tailored_cv.docx",
        output_cover_letter_path=run_dir / "cover_letter.txt",
        company_name="Acme",
        job_description="Example JD",
        api_key="test-key",
        model_name="fake-model",
        prompt_templates=_build_prompt_templates(run_dir),
        debug_mode=False,
        auto_approve_review=False,
        auto_approve_triage=False,
    )


def _fake_response_for_section(section_id: str) -> str:
    if section_id == "triage_job_fit_and_risks":
        return json.dumps(
            {
                "triage_result": {
                    "verdict": "APPLY",
                    "decision_score_0_to_100": 85,
                    "confidence_0_to_100": 80,
                    "summary": "Strong alignment for this role.",
                    "raw_subscores": {
                        "technical_fit_0_to_35": 31,
                        "company_risk_0_to_20": 16,
                        "role_quality_0_to_15": 12,
                        "spain_entity_compat_0_to_20": 14,
                        "evidence_quality_0_to_10": 8,
                    },
                    "top_reasons": [
                        "Strong backend fit",
                        "Good role scope",
                        "Manageable risk profile",
                    ],
                    "key_risks": [
                        {
                            "risk": "Need recruiter confirmation on contract type.",
                            "severity": "medium",
                            "type": "uncertainty",
                            "mitigation": "Ask direct hiring-entity questions early.",
                        }
                    ],
                    "spain_entity_risk": {
                        "status": "UNCLEAR",
                        "confidence_0_to_100": 55,
                        "explanation": "Public policy does not clarify B2B constraints.",
                        "recruiter_questions": [
                            "Can you hire via contractor agreement?",
                            "Which legal entity signs the contract?",
                            "Is payroll employment mandatory in Spain?",
                        ],
                    },
                    "sources": [
                        {
                            "label": "Company careers",
                            "url": "https://example.com/careers",
                            "evidence_grade": "A",
                            "used_for": "Hiring policy",
                        }
                    ],
                    "report_markdown": "### Final Verdict\nProceed with this role.",
                }
            }
        )

    envelope = {
        "variations": [
            {
                "id": "A",
                "score_0_to_100": 5,
                "ai_reasoning": f"Reason for {section_id}",
                "content_for_template": f"Approved content for {section_id}",
            },
            {
                "id": "B",
                "score_0_to_100": 3,
                "ai_reasoning": "Fallback",
                "content_for_template": f"Fallback content for {section_id}",
            },
        ]
    }
    return json.dumps(envelope)


def _extract_section_id_from_prompt(prompt: str) -> str:
    marker = "SECTION_ID: "
    for line in prompt.splitlines():
        if line.startswith(marker):
            return line[len(marker) :].strip()
    raise AssertionError(f"Missing section marker in prompt: {prompt}")


def test_run_graph_completes_with_mocked_llm_and_review_choices(
    monkeypatch: object,
) -> None:
    run_dir = make_workspace_temp_dir("integration-mocked-graph")
    template_path = run_dir / "template.docx"
    _make_template(template_path)
    context = _build_runtime_context(run_dir, template_path)
    state: GraphState = create_initial_state("integration-run-1")

    async def fake_generate_with_gemini(
        prompt: str, api_key: str, model: str, section_id: str | None = None
    ) -> str:
        assert api_key == "test-key"
        assert model == "fake-model"
        resolved_section_id = section_id or _extract_section_id_from_prompt(prompt)
        return _fake_response_for_section(resolved_section_id)

    review_inputs = ["continue"]
    for _ in GENERATION_SECTION_IDS:
        review_inputs.extend(["choose", "A"])
    response_iter = iter(review_inputs)

    def fake_input(_: str = "") -> str:
        try:
            return next(response_iter)
        except StopIteration as exc:
            raise AssertionError("Review requested more inputs than expected.") from exc

    monkeypatch.setattr(graph_nodes, "generate_with_gemini", fake_generate_with_gemini)
    monkeypatch.setattr("builtins.input", fake_input)

    final_state = asyncio.run(_run_graph(state, context))

    assert final_state.status == "completed"
    assert context.output_cv_path.exists()
    assert context.output_cover_letter_path.exists()
    checkpoint_state = load_checkpoint(context.checkpoint_path)
    assert checkpoint_state.status == "completed"

    rendered = Document(str(context.output_cv_path))
    output_text = "\n".join(paragraph.text for paragraph in rendered.paragraphs)
    for section_id in TEMPLATE_SECTION_IDS:
        assert f"Approved content for {section_id}" in output_text

    cover_letter = context.output_cover_letter_path.read_text(encoding="utf-8")
    assert "Approved content for doc_cover_letter" in cover_letter


def test_run_graph_stops_at_triage_when_user_selects_stop(monkeypatch: object) -> None:
    run_dir = make_workspace_temp_dir("integration-mocked-triage-stop")
    template_path = run_dir / "template.docx"
    _make_template(template_path)
    context = _build_runtime_context(run_dir, template_path)
    state: GraphState = create_initial_state("integration-run-2")

    async def fake_generate_with_gemini(
        prompt: str, api_key: str, model: str, section_id: str | None = None
    ) -> str:
        assert api_key == "test-key"
        assert model == "fake-model"
        resolved_section_id = section_id or _extract_section_id_from_prompt(prompt)
        if resolved_section_id == "triage_job_fit_and_risks":
            return json.dumps(
                {
                    "triage_result": {
                        "verdict": "AVOID",
                        "decision_score_0_to_100": 22,
                        "confidence_0_to_100": 78,
                        "summary": "High legal and role mismatch risk.",
                        "raw_subscores": {
                            "technical_fit_0_to_35": 15,
                            "company_risk_0_to_20": 4,
                            "role_quality_0_to_15": 5,
                            "spain_entity_compat_0_to_20": 1,
                            "evidence_quality_0_to_10": 7,
                        },
                        "top_reasons": ["Reason 1", "Reason 2", "Reason 3"],
                        "key_risks": [
                            {
                                "risk": "Likely legal blocker for Spain setup.",
                                "severity": "high",
                                "type": "legal_blocker",
                                "mitigation": "Do not proceed without explicit B2B path.",
                            }
                        ],
                        "spain_entity_risk": {
                            "status": "YES",
                            "confidence_0_to_100": 85,
                            "explanation": "Evidence points to local employment requirement.",
                            "recruiter_questions": ["Q1", "Q2", "Q3"],
                        },
                        "sources": [
                            {
                                "label": "Policy",
                                "url": "https://example.com/policy",
                                "evidence_grade": "A",
                                "used_for": "Employment constraints",
                            }
                        ],
                        "report_markdown": "### Final Verdict\nAvoid.",
                    }
                }
            )
        return _fake_response_for_section(resolved_section_id)

    monkeypatch.setattr(graph_nodes, "generate_with_gemini", fake_generate_with_gemini)
    monkeypatch.setattr("builtins.input", lambda _: "stop")

    final_state = asyncio.run(_run_graph(state, context))

    assert final_state.status == "completed"
    assert final_state.current_node == "triage_stop"
    assert not context.output_cv_path.exists()
    assert not context.output_cover_letter_path.exists()
