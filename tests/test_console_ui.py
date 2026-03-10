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


def test_render_triage_result_shows_full_evidence(monkeypatch: object) -> None:
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

    assert "Decision Overview" in output
    assert "APPLY WITH CAVEATS" in output
    assert "Decision Score: 74/100 | Confidence: 68/100" in output
    assert "Weighted Subscores" in output
    assert "Risk Register" in output
    assert "Spain Entity Compatibility" in output
    assert "Evidence Sources" in output
    assert "Detailed Report" in output
    assert "Reason 1" in output
    assert "Contract model unclear." in output
    assert "Ask recruiter." in output
    assert "Q1" in output
    assert "https://example.com" in output


def test_render_triage_decision_prompt(monkeypatch: object) -> None:
    console = Console(record=True, width=140)
    monkeypatch.setattr(console_ui, "_CONSOLE", console)
    monkeypatch.setenv("ART_UI_ENABLED", "1")

    console_ui.render_triage_decision_prompt(suggested_action="stop")
    output = console.export_text()

    assert "Decision Required" in output
    assert "Job fit triage completed." in output
    assert "AI recommendation: STOP (possible poor fit)" in output


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
