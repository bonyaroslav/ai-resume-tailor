from __future__ import annotations

from rich.console import Console

import console_ui
from graph_state import TriageResult, Variation


def test_render_prompt_truncates_to_first_five_lines(
    monkeypatch: object,
) -> None:
    console = Console(record=True, width=140)
    monkeypatch.setattr(console_ui, "_CONSOLE", console)
    monkeypatch.setenv("ART_UI_ENABLED", "1")
    monkeypatch.setenv("ART_UI_SHOW_PROMPTS", "1")

    prompt = "\n".join(
        [
            "line 1",
            "line 2",
            "line 3",
            "line 4",
            "line 5",
            "line 6",
            "line 7",
        ]
    )
    console_ui.render_prompt("section_professional_summary", prompt)
    output = console.export_text()

    assert "line 1" in output
    assert "line 5" in output
    assert "line 6" not in output
    assert "... [truncated; total_lines=7]" in output


def test_render_triage_result_is_compact(monkeypatch: object) -> None:
    console = Console(record=True, width=140)
    monkeypatch.setattr(console_ui, "_CONSOLE", console)
    monkeypatch.setenv("ART_UI_ENABLED", "1")
    monkeypatch.setenv("ART_UI_SHOW_RESPONSES", "1")

    triage_result = TriageResult.model_validate(
        {
            "verdict": "APPLY_WITH_CAVEATS",
            "decision_score_0_to_100": 74,
            "confidence_0_to_100": 68,
            "summary": "Good fit with unresolved contract questions.",
            "raw_subscores": {
                "technical_fit_0_to_35": 30,
                "company_risk_0_to_20": 12,
                "role_quality_0_to_15": 11,
                "spain_entity_compat_0_to_20": 10,
                "evidence_quality_0_to_10": 7,
            },
            "top_reasons": ["Reason 1", "Reason 2", "Reason 3"],
            "key_risks": [
                {
                    "risk": "Contract model unclear.",
                    "severity": "medium",
                    "type": "uncertainty",
                    "mitigation": "Ask recruiter.",
                }
            ],
            "spain_entity_risk": {
                "status": "UNCLEAR",
                "confidence_0_to_100": 60,
                "explanation": "No explicit statement found.",
                "recruiter_questions": ["Q1", "Q2", "Q3"],
            },
            "sources": [
                {
                    "label": "Company page",
                    "url": "https://example.com",
                    "evidence_grade": "A",
                    "used_for": "Policy",
                }
            ],
            "report_markdown": "### Final Verdict\nApply with caveats.",
        }
    )

    console_ui.render_triage_result("triage_job_fit_and_risks", triage_result)
    output = console.export_text()

    assert "Verdict: APPLY_WITH_CAVEATS | Score: 74/100 | Confidence: 68/100" in output
    assert "Top Reasons" in output
    assert "Reason 1" in output
    assert "Top Risks" in output
    assert "medium: Contract model unclear." in output


def test_render_variations_skips_triage_section(monkeypatch: object) -> None:
    console = Console(record=True, width=140)
    monkeypatch.setattr(console_ui, "_CONSOLE", console)
    monkeypatch.setenv("ART_UI_ENABLED", "1")
    monkeypatch.setenv("ART_UI_SHOW_RESPONSES", "1")

    variations = [
        Variation(
            id="A",
            score_0_to_100=80,
            ai_reasoning="reason",
            content_for_template="content",
        )
    ]
    console_ui.render_variations("triage_job_fit_and_risks", variations)
    output = console.export_text()
    assert output.strip() == ""
