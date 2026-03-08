from __future__ import annotations

import os
from dataclasses import dataclass

from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

from graph_state import Variation

_CONSOLE = Console(safe_box=True)
UI_ENABLED_ENV = "ART_UI_ENABLED"
SHOW_PROMPTS_ENV = "ART_UI_SHOW_PROMPTS"
SHOW_RESPONSES_ENV = "ART_UI_SHOW_RESPONSES"
MAX_KNOWLEDGE_PREVIEW_LINES = 3


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
    )


def _safe_console_text(value: str) -> str:
    encoding = getattr(_CONSOLE.file, "encoding", None) or "utf-8"
    return value.encode(encoding, errors="replace").decode(encoding, errors="replace")


def _truncate_lines(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    head = "\n".join(lines[:max_lines])
    omitted = len(lines) - max_lines
    suffix = f"\n... ({omitted} more line{'s' if omitted != 1 else ''})"
    return f"{head}{suffix}"


def _prompt_for_display(prompt: str) -> str:
    lines = prompt.splitlines()
    if "## Context Files" not in lines:
        return prompt

    output: list[str] = []
    in_context = False
    current_header: str | None = None
    current_content: list[str] = []

    def _flush_current() -> None:
        if current_header is None:
            return
        output.append(current_header)
        output.append(
            _truncate_lines("\n".join(current_content), MAX_KNOWLEDGE_PREVIEW_LINES)
        )

    for line in lines:
        if line == "## Context Files":
            in_context = True
            output.append(line)
            continue
        if not in_context:
            output.append(line)
            continue
        if line.startswith("## Runtime Input"):
            _flush_current()
            current_header = None
            current_content = []
            in_context = False
            output.append(line)
            continue
        if line.startswith("### "):
            _flush_current()
            current_header = line
            current_content = []
            continue
        if current_header is None:
            output.append(line)
            continue
        current_content.append(line)

    if in_context:
        _flush_current()

    return "\n".join(output)


def render_prompt(section_id: str, prompt: str) -> None:
    if not _enabled(UI_ENABLED_ENV, default=True):
        return
    if not _enabled(SHOW_PROMPTS_ENV, default=True):
        return

    styles = _styles()
    display_prompt = _prompt_for_display(prompt)
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

    styles = _styles()
    for variation in variations:
        body = Group(
            Text(
                _safe_console_text(f"Score: {variation.score_0_to_5}/5"),
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
