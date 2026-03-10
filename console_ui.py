from __future__ import annotations

import os
from dataclasses import dataclass

from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from graph_state import TriageResult, Variation
from workflow_definition import TRIAGE_SECTION_ID

_CONSOLE = Console(safe_box=True)
UI_ENABLED_ENV = "ART_UI_ENABLED"
SHOW_PROMPTS_ENV = "ART_UI_SHOW_PROMPTS"
SHOW_RESPONSES_ENV = "ART_UI_SHOW_RESPONSES"
MAX_PROMPT_PREVIEW_LINES = 5


@dataclass(frozen=True)
class UiStyles:
    prompt_border: str = "cyan"
    prompt_title: str = "bold cyan"
    prompt_body: str = "white"
    response_border: str = "green"
    response_title: str = "bold green"
    score: str = "bold magenta"
    reasoning_label: str = "bold yellow"
    reasoning_body: str = "yellow"
    content_label: str = "bold white"
    content_body: str = "white"
    triage_apply_border: str = "green"
    triage_caveat_border: str = "yellow"
    triage_avoid_border: str = "red"
    triage_summary_border: str = "bright_blue"
    triage_detail_border: str = "bright_black"


def _is_truthy_env(value: str | None, *, default: bool) -> bool:
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _enabled(env_name: str, *, default: bool) -> bool:
    return _is_truthy_env(os.getenv(env_name), default=default)


def _style(env_name: str, default: str) -> str:
    value = os.getenv(env_name, "").strip()
    return value or default


def _styles() -> UiStyles:
    return UiStyles(
        prompt_border=_style("ART_UI_PROMPT_BORDER_STYLE", "cyan"),
        prompt_title=_style("ART_UI_PROMPT_TITLE_STYLE", "bold cyan"),
        prompt_body=_style("ART_UI_PROMPT_BODY_STYLE", "white"),
        response_border=_style("ART_UI_RESPONSE_BORDER_STYLE", "green"),
        response_title=_style("ART_UI_RESPONSE_TITLE_STYLE", "bold green"),
        score=_style("ART_UI_SCORE_STYLE", "bold magenta"),
        reasoning_label=_style("ART_UI_REASONING_LABEL_STYLE", "bold yellow"),
        reasoning_body=_style("ART_UI_REASONING_BODY_STYLE", "yellow"),
        content_label=_style("ART_UI_CONTENT_LABEL_STYLE", "bold white"),
        content_body=_style("ART_UI_CONTENT_BODY_STYLE", "white"),
        triage_apply_border=_style("ART_UI_TRIAGE_APPLY_BORDER_STYLE", "green"),
        triage_caveat_border=_style("ART_UI_TRIAGE_CAVEAT_BORDER_STYLE", "yellow"),
        triage_avoid_border=_style("ART_UI_TRIAGE_AVOID_BORDER_STYLE", "red"),
        triage_summary_border=_style(
            "ART_UI_TRIAGE_SUMMARY_BORDER_STYLE", "bright_blue"
        ),
        triage_detail_border=_style(
            "ART_UI_TRIAGE_DETAIL_BORDER_STYLE", "bright_black"
        ),
    )


def _safe_console_text(value: str) -> str:
    encoding = getattr(_CONSOLE.file, "encoding", None) or "utf-8"
    return value.encode(encoding, errors="replace").decode(encoding, errors="replace")


def _truncate_lines(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    preview = "\n".join(lines[:max_lines])
    return f"{preview}\n... [truncated; total_lines={len(lines)}]"


def render_prompt(section_id: str, prompt: str) -> None:
    if not _enabled(UI_ENABLED_ENV, default=True):
        return
    if not _enabled(SHOW_PROMPTS_ENV, default=True):
        return

    styles = _styles()
    display_prompt = _truncate_lines(prompt, MAX_PROMPT_PREVIEW_LINES)
    _CONSOLE.print(
        Panel(
            Text(_safe_console_text(display_prompt), style=styles.prompt_body),
            title=_safe_console_text(f"Prompt: {section_id}"),
            title_align="left",
            border_style=styles.prompt_border,
        )
    )


def render_variations(section_id: str, variations: list[Variation]) -> None:
    if not _enabled(UI_ENABLED_ENV, default=True):
        return
    if not _enabled(SHOW_RESPONSES_ENV, default=True):
        return

    if section_id == TRIAGE_SECTION_ID:
        return

    styles = _styles()
    for variation in variations:
        body = Group(
            Text(
                _safe_console_text(f"Score: {variation.score_0_to_100}/100"),
                style=styles.score,
            ),
            Text("Reasoning", style=styles.reasoning_label),
            Text(
                _safe_console_text(variation.ai_reasoning), style=styles.reasoning_body
            ),
            Text("Content", style=styles.content_label),
            Text(
                _safe_console_text(variation.content_for_template),
                style=styles.content_body,
            ),
        )
        _CONSOLE.print(
            Panel(
                body,
                title=_safe_console_text(f"AI Output: {section_id} [{variation.id}]"),
                title_align="left",
                border_style=styles.response_border,
            )
        )


def render_triage_result(section_id: str, triage_result: TriageResult) -> None:
    if not _enabled(UI_ENABLED_ENV, default=True):
        return
    if not _enabled(SHOW_RESPONSES_ENV, default=True):
        return

    styles = _styles()
    verdict_to_style = {
        "APPLY": ("APPLY", "bold white on green", styles.triage_apply_border),
        "APPLY_WITH_CAVEATS": (
            "APPLY WITH CAVEATS",
            "bold black on yellow",
            styles.triage_caveat_border,
        ),
        "AVOID": ("AVOID", "bold white on red", styles.triage_avoid_border),
    }
    verdict_label, verdict_style, border_style = verdict_to_style[triage_result.verdict]

    top_reasons = "\n".join(f"• {reason}" for reason in triage_result.top_reasons)

    subscores = Table(
        show_header=True, header_style="bold cyan", box=None, pad_edge=False
    )
    subscores.add_column("Dimension", style="bold")
    subscores.add_column("Score", justify="right")
    subscores.add_column("Weight", justify="right")
    subscores.add_row(
        "Technical fit",
        str(triage_result.raw_subscores.technical_fit_0_to_35),
        "/35",
    )
    subscores.add_row(
        "Company risk",
        str(triage_result.raw_subscores.company_risk_0_to_20),
        "/20",
    )
    subscores.add_row(
        "Role quality",
        str(triage_result.raw_subscores.role_quality_0_to_15),
        "/15",
    )
    subscores.add_row(
        "Spain compatibility",
        str(triage_result.raw_subscores.spain_entity_compat_0_to_20),
        "/20",
    )
    subscores.add_row(
        "Evidence quality",
        str(triage_result.raw_subscores.evidence_quality_0_to_10),
        "/10",
    )

    risks = Table(
        show_header=True, header_style="bold yellow", box=None, pad_edge=False
    )
    risks.add_column("Severity", style="bold")
    risks.add_column("Type", style="dim")
    risks.add_column("Risk")
    risks.add_column("Mitigation")
    for risk in triage_result.key_risks:
        severity_style = {
            "high": "bold red",
            "medium": "bold yellow",
            "low": "bold green",
        }[risk.severity]
        risks.add_row(
            f"[{severity_style}]{risk.severity.upper()}[/]",
            risk.type.replace("_", " "),
            risk.risk,
            risk.mitigation,
        )

    sources = Table(
        show_header=True, header_style="bold blue", box=None, pad_edge=False
    )
    sources.add_column("Evidence", style="bold")
    sources.add_column("Used for")
    sources.add_column("Source")
    for source in triage_result.sources:
        sources.add_row(
            f"{source.evidence_grade} | {source.label}",
            source.used_for,
            source.url,
        )

    spain_questions = "\n".join(
        f"{index}. {question}"
        for index, question in enumerate(
            triage_result.spain_entity_risk.recruiter_questions, start=1
        )
    )
    spain_status_style = {
        "YES": "bold red",
        "NO": "bold green",
        "UNCLEAR": "bold yellow",
    }[triage_result.spain_entity_risk.status]
    spain_risk_body = Group(
        Text.from_markup(
            f"Status: [{spain_status_style}]{triage_result.spain_entity_risk.status}[/] | "
            f"Confidence: {triage_result.spain_entity_risk.confidence_0_to_100}/100"
        ),
        Text(_safe_console_text(triage_result.spain_entity_risk.explanation)),
        Text("Recruiter Questions", style="bold"),
        Text(_safe_console_text(spain_questions)),
    )

    body = Group(
        Panel(
            Group(
                Text.from_markup(f"[{verdict_style}] {verdict_label} [/]"),
                Text(
                    _safe_console_text(
                        f"Decision Score: {triage_result.decision_score_0_to_100}/100 | "
                        f"Confidence: {triage_result.confidence_0_to_100}/100"
                    ),
                    style="bold",
                ),
                Text("Summary", style="bold"),
                Text(_safe_console_text(triage_result.summary)),
            ),
            title="Decision Overview",
            title_align="left",
            border_style=border_style,
        ),
        Panel(
            Group(
                Text("Top Reasons", style="bold green"),
                Text(_safe_console_text(top_reasons)),
            ),
            title="Reasons",
            title_align="left",
            border_style=styles.triage_summary_border,
        ),
        Panel(
            subscores,
            title="Weighted Subscores",
            title_align="left",
            border_style=styles.triage_detail_border,
        ),
        Panel(
            risks,
            title="Risk Register",
            title_align="left",
            border_style=styles.triage_detail_border,
        ),
        Panel(
            spain_risk_body,
            title="Spain Entity Compatibility",
            title_align="left",
            border_style=styles.triage_detail_border,
        ),
        Panel(
            sources,
            title="Evidence Sources",
            title_align="left",
            border_style=styles.triage_detail_border,
        ),
        Panel(
            Markdown(_safe_console_text(triage_result.report_markdown)),
            title="Detailed Report",
            title_align="left",
            border_style=styles.triage_detail_border,
        ),
    )
    _CONSOLE.print(
        Panel(
            body,
            title=_safe_console_text(f"Triage: {section_id}"),
            title_align="left",
            border_style=border_style,
        )
    )


def render_triage_decision_prompt(*, suggested_action: str) -> None:
    if not _enabled(UI_ENABLED_ENV, default=True):
        return

    styles = _styles()
    recommendation = (
        "[bold red]STOP[/] (possible poor fit)"
        if suggested_action == "stop"
        else "[bold green]CONTINUE[/]"
    )
    body = Group(
        Text("Job fit triage completed.", style="bold"),
        Text.from_markup(f"AI recommendation: {recommendation}"),
        Text(
            "Review the full evidence above, then confirm if you want to continue with generation or stop.",
            style=styles.content_body,
        ),
    )
    _CONSOLE.print(
        Panel(
            body,
            title="Decision Required",
            title_align="left",
            border_style=styles.triage_summary_border,
        )
    )
