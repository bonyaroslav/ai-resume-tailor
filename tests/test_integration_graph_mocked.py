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
        content = "Proceed with this role."
        reasoning = "Strong alignment. Go."
    else:
        content = f"Approved content for {section_id}"
        reasoning = f"Reason for {section_id}"

    envelope = {
        "variations": [
            {
                "id": "A",
                "score_0_to_100": 5,
                "ai_reasoning": reasoning,
                "content_for_template": content,
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
