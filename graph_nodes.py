from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from time import monotonic
from pathlib import Path

from checkpoint import save_checkpoint
from console_ui import render_prompt, render_variations
from document_builder import (
    assemble_cv_document,
    preflight_template,
    write_cover_letter,
)
from graph_state import GraphState, SectionState, Variation, touch_state
from json_parser import ResponseParseError, ResponseSchemaError, parse_response_envelope
from llm_client import generate_with_gemini
from logging_utils import log_failure
from prompt_loader import PromptTemplate, build_prompt_text
from workflow_definition import (
    COVER_LETTER_SECTION_ID,
    GENERATION_SECTION_IDS,
    TEMPLATE_SECTION_IDS,
    TRIAGE_SECTION_ID,
)

MAX_AUTOMATIC_PARSE_RETRIES = 1
MAX_USER_RETRIES_PER_SECTION = 2
LLM_HEARTBEAT_INTERVAL_SECONDS = 15
LLM_HEARTBEAT_INTERVAL_ENV = "ART_LLM_HEARTBEAT_SECONDS"


@dataclass(frozen=True)
class RuntimeContext:
    run_dir: Path
    checkpoint_path: Path
    template_path: Path
    output_cv_path: Path
    output_cover_letter_path: Path
    company_name: str
    job_description: str
    api_key: str
    model_name: str
    prompt_templates: dict[str, PromptTemplate]
    debug_mode: bool
    auto_approve_review: bool


def _find_variation(variations: list[Variation], variation_id: str) -> Variation | None:
    for variation in variations:
        if variation.id == variation_id:
            return variation
    return None


def _triage_is_no_go(variation: Variation) -> bool:
    verdict_text = f"{variation.ai_reasoning}\n{variation.content_for_template}".lower()
    return "no-go" in verdict_text or "avoid" in verdict_text


def _heartbeat_interval_seconds() -> int:
    raw_value = os.getenv(LLM_HEARTBEAT_INTERVAL_ENV, "").strip()
    if not raw_value:
        return LLM_HEARTBEAT_INTERVAL_SECONDS
    try:
        interval = int(raw_value)
    except ValueError:
        return LLM_HEARTBEAT_INTERVAL_SECONDS
    return max(1, interval)


async def _generate_section_variations(
    section_id: str,
    section_state: SectionState,
    context: RuntimeContext,
    logger: logging.Logger,
) -> list[Variation]:
    template = context.prompt_templates[section_id]
    prompt = build_prompt_text(
        template=template,
        company_name=context.company_name,
        job_description=context.job_description,
        retry_note=section_state.user_note,
    )
    render_prompt(section_id, prompt)

    last_error: Exception | None = None
    heartbeat_interval_seconds = _heartbeat_interval_seconds()
    for attempt in range(MAX_AUTOMATIC_PARSE_RETRIES + 1):
        logger.info(
            "LLM request started section_id=%s attempt=%s heartbeat_s=%s",
            section_id,
            attempt + 1,
            heartbeat_interval_seconds,
        )
        request_started = monotonic()
        request_task = asyncio.create_task(
            generate_with_gemini(
                prompt, context.api_key, context.model_name, section_id
            )
        )
        while True:
            try:
                raw_response = await asyncio.wait_for(
                    asyncio.shield(request_task),
                    timeout=heartbeat_interval_seconds,
                )
                break
            except asyncio.TimeoutError:
                elapsed_s = int(monotonic() - request_started)
                logger.info(
                    "LLM request in progress section_id=%s attempt=%s elapsed_s=%s",
                    section_id,
                    attempt + 1,
                    elapsed_s,
                )
        logger.info(
            "LLM request completed section_id=%s attempt=%s duration_ms=%s",
            section_id,
            attempt + 1,
            int((monotonic() - request_started) * 1000),
        )
        if context.debug_mode:
            _write_debug_response(context.run_dir, section_id, attempt, raw_response)
        try:
            envelope = parse_response_envelope(raw_response)
        except ResponseParseError as exc:
            log_failure(
                logger,
                category="parse_error",
                node="generate_sections",
                section_id=section_id,
                attempt=attempt + 1,
                retry_count=section_state.retry_count,
                detail=str(exc),
            )
            last_error = exc
            continue
        except ResponseSchemaError as exc:
            log_failure(
                logger,
                category="schema_error",
                node="generate_sections",
                section_id=section_id,
                attempt=attempt + 1,
                retry_count=section_state.retry_count,
                detail=str(exc),
            )
            last_error = exc
            continue

        if not envelope.variations:
            last_error = ResponseSchemaError("Envelope contains no variations.")
            log_failure(
                logger,
                category="schema_error",
                node="generate_sections",
                section_id=section_id,
                attempt=attempt + 1,
                retry_count=section_state.retry_count,
                detail="Envelope contains no variations.",
            )
            continue
        render_variations(section_id, envelope.variations)
        return envelope.variations

    log_failure(
        logger,
        category="generation_error",
        node="generate_sections",
        section_id=section_id,
        retry_count=section_state.retry_count,
        detail="LLM response failed parsing after allowed retries.",
    )
    raise RuntimeError(
        f"LLM response failed parsing for section '{section_id}'."
    ) from last_error


def _write_debug_response(
    run_dir: Path, section_id: str, attempt: int, raw_response: str
) -> None:
    debug_dir = run_dir / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{section_id}.attempt_{attempt + 1}.raw_response.txt"
    (debug_dir / filename).write_text(raw_response, encoding="utf-8")


async def node_triage(
    state: GraphState, context: RuntimeContext, logger: logging.Logger
) -> GraphState:
    logger.info("Node triage started.")
    section_state = state.section_states[TRIAGE_SECTION_ID]
    variations = await _generate_section_variations(
        TRIAGE_SECTION_ID, section_state, context, logger
    )

    selected = variations[0]
    state.section_states[TRIAGE_SECTION_ID] = SectionState(
        status="approved",
        variations=variations,
        selected_variation_id=selected.id,
        selected_content=selected.content_for_template,
        user_note=section_state.user_note,
        retry_count=section_state.retry_count,
    )

    if _triage_is_no_go(selected):
        logger.info("Triage verdict detected as No-Go. Ending run at triage_stop.")
        state.status = "completed"
        state.current_node = "triage_stop"
        state.review_queue = []
    else:
        state.current_node = "generate_sections"
        state.status = "running"
    touch_state(state)
    return state


async def node_generate_sections(
    state: GraphState,
    context: RuntimeContext,
    logger: logging.Logger,
) -> GraphState:
    logger.info("Node generate_sections started.")
    targets: list[str] = []
    for section_id in GENERATION_SECTION_IDS:
        section_state = state.section_states[section_id]
        if (
            section_state.status in {"pending", "retry_requested"}
            or not section_state.variations
        ):
            targets.append(section_id)

    if not targets:
        logger.info("No sections require generation; moving to review.")
        state.current_node = "review"
        state.status = "awaiting_review"
        state.review_queue = [
            section_id
            for section_id in GENERATION_SECTION_IDS
            if state.section_states[section_id].status == "generated"
        ]
        touch_state(state)
        return state

    logger.info("Generating sections concurrently: %s", ", ".join(targets))
    tasks = [
        _generate_section_variations(
            section_id, state.section_states[section_id], context, logger
        )
        for section_id in targets
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for index, result in enumerate(results):
        section_id = targets[index]
        if isinstance(result, Exception):
            log_failure(
                logger,
                category="generation_error",
                node="generate_sections",
                section_id=section_id,
                retry_count=state.section_states[section_id].retry_count,
                detail=str(result),
            )
            raise RuntimeError(
                f"Generation failed for section '{section_id}'."
            ) from result

        section_state = state.section_states[section_id]
        state.section_states[section_id] = SectionState(
            status="generated",
            variations=result,
            selected_variation_id=None,
            selected_content=None,
            user_note=None,
            retry_count=section_state.retry_count,
        )

    state.review_queue = targets
    state.current_node = "review"
    state.status = "awaiting_review"
    touch_state(state)
    return state


def _print_section_variations(section_id: str, section_state: SectionState) -> None:
    print("")
    print(f"== {section_id} ==")
    for variation in section_state.variations:
        print(f"[{variation.id}] score={variation.score_0_to_5}")
        print(f"reason: {variation.ai_reasoning}")
        print(variation.content_for_template)
        print("-" * 40)


def _print_review_header(
    section_id: str, position: int, total: int, retry_count: int
) -> None:
    print("")
    print(f"[Review {position}/{total}] {section_id}")
    print(f"Retries used: {retry_count}/{MAX_USER_RETRIES_PER_SECTION}")


def _normalize_action(raw_action: str) -> str:
    aliases = {
        "c": "choose",
        "e": "edit",
        "r": "retry",
        "s": "save_and_exit",
    }
    action = raw_action.strip().lower()
    return aliases.get(action, action)


def _prompt_for_action() -> str:
    valid_actions = "choose/edit/retry/save_and_exit"
    while True:
        action = _normalize_action(input(f"Action [{valid_actions}] (c/e/r/s): "))
        if action in {"choose", "edit", "retry", "save_and_exit"}:
            return action
        print("Invalid action. Use choose/edit/retry/save_and_exit (or c/e/r/s).")


def _prompt_for_variation_id(
    section_state: SectionState, *, prompt_text: str, default_id: str | None = None
) -> Variation:
    valid_ids = [variation.id for variation in section_state.variations]
    print(f"Valid variation IDs: {', '.join(valid_ids)}")
    while True:
        chosen_id = input(prompt_text).strip()
        if not chosen_id and default_id is not None:
            chosen_id = default_id

        chosen = _find_variation(section_state.variations, chosen_id)
        if chosen:
            return chosen
        print("Invalid variation id. Try again.")


def _approve_variation(
    section_state: SectionState, variation: Variation, edited_content: str | None = None
) -> None:
    section_state.status = "approved"
    section_state.selected_variation_id = variation.id
    section_state.selected_content = (
        edited_content if edited_content is not None else variation.content_for_template
    )
    section_state.user_note = None
    if not section_state.selected_content:
        raise ValueError("Approved section content cannot be empty.")


def _handle_retry(section_state: SectionState) -> None:
    if section_state.retry_count >= MAX_USER_RETRIES_PER_SECTION:
        print("Retry limit reached. Choose or edit an existing variation.")
        return

    note = input("Retry note: ").strip()
    if not note:
        print("Retry note is required.")
        return

    section_state.retry_count += 1
    section_state.user_note = note
    section_state.status = "retry_requested"
    section_state.selected_variation_id = None
    section_state.selected_content = None


def _review_single_section(
    section_id: str, section_state: SectionState, position: int, total: int
) -> bool:
    _print_review_header(section_id, position, total, section_state.retry_count)
    _print_section_variations(section_id, section_state)

    while True:
        action = _prompt_for_action()
        if action == "save_and_exit":
            print("Saving current progress and exiting review.")
            return True

        if action == "choose":
            chosen = _prompt_for_variation_id(
                section_state, prompt_text="Variation id: "
            )
            _approve_variation(section_state, chosen)
            print(f"Approved variation '{chosen.id}'.")
            return False

        if action == "edit":
            default_id = (
                section_state.selected_variation_id or section_state.variations[0].id
            )
            chosen = _prompt_for_variation_id(
                section_state,
                prompt_text=f"Variation id to edit [{default_id}]: ",
                default_id=default_id,
            )
            while True:
                edited_content = input("Final edited content: ").strip()
                if edited_content:
                    break
                print("Edited content cannot be empty.")
            _approve_variation(section_state, chosen, edited_content)
            print(f"Approved edited content for variation '{chosen.id}'.")
            return False

        if action == "retry":
            before = section_state.status
            _handle_retry(section_state)
            if section_state.status != before:
                print(
                    "Retry requested. "
                    f"Retry count is now {section_state.retry_count}/{MAX_USER_RETRIES_PER_SECTION}."
                )
                return False
            continue


def node_review(
    state: GraphState, context: RuntimeContext, logger: logging.Logger
) -> tuple[GraphState, bool]:
    logger.info("Node review started.")
    queue = state.review_queue or [
        section_id
        for section_id in GENERATION_SECTION_IDS
        if state.section_states[section_id].status == "generated"
    ]

    total = len(queue)
    if context.auto_approve_review:
        for section_id in queue:
            section_state = state.section_states[section_id]
            if section_state.status != "generated":
                continue
            if not section_state.variations:
                continue
            _approve_variation(section_state, section_state.variations[0])
            logger.info(
                "Auto-approved section_id=%s with variation_id=%s",
                section_id,
                section_state.selected_variation_id,
            )

    for index, section_id in enumerate(queue, start=1):
        section_state = state.section_states[section_id]
        if section_state.status != "generated":
            continue
        if not section_state.variations:
            continue

        save_checkpoint(context.checkpoint_path, state)
        should_exit = _review_single_section(section_id, section_state, index, total)
        if should_exit:
            state.current_node = "review"
            state.status = "awaiting_review"
            state.review_queue = queue
            touch_state(state)
            print(f"Checkpoint ready at: {context.checkpoint_path}")
            return state, True
        logger.info(
            "Review decision captured for section_id=%s, status=%s",
            section_id,
            section_state.status,
        )

    retry_sections = [
        section_id
        for section_id in GENERATION_SECTION_IDS
        if state.section_states[section_id].status == "retry_requested"
    ]
    if retry_sections:
        state.current_node = "generate_sections"
        state.status = "running"
        state.review_queue = retry_sections
        touch_state(state)
        return state, False

    all_approved = all(
        bool(state.section_states[section_id].selected_content)
        for section_id in GENERATION_SECTION_IDS
    )
    if all_approved:
        state.current_node = "assemble"
        state.status = "running"
        state.review_queue = []
        touch_state(state)
        return state, False

    state.current_node = "review"
    state.status = "awaiting_review"
    state.review_queue = queue
    touch_state(state)
    return state, False


def node_assemble(
    state: GraphState, context: RuntimeContext, logger: logging.Logger
) -> GraphState:
    logger.info("Node assemble started.")
    preflight_template(context.template_path, TEMPLATE_SECTION_IDS)

    selected_cv_content: dict[str, str] = {}
    for section_id in TEMPLATE_SECTION_IDS:
        content = state.section_states[section_id].selected_content
        if not content:
            log_failure(
                logger,
                category="assemble_error",
                node="assemble",
                section_id=section_id,
                retry_count=state.section_states[section_id].retry_count,
                detail="Missing approved content for section.",
            )
            raise ValueError(f"Missing approved content for section '{section_id}'.")
        selected_cv_content[section_id] = content

    assemble_cv_document(
        template_path=context.template_path,
        output_path=context.output_cv_path,
        selected_content=selected_cv_content,
    )

    cover_letter_content = state.section_states[
        COVER_LETTER_SECTION_ID
    ].selected_content
    if not cover_letter_content:
        log_failure(
            logger,
            category="assemble_error",
            node="assemble",
            section_id=COVER_LETTER_SECTION_ID,
            retry_count=state.section_states[COVER_LETTER_SECTION_ID].retry_count,
            detail="Missing approved content for doc_cover_letter.",
        )
        raise ValueError("Missing approved content for doc_cover_letter.")
    write_cover_letter(context.output_cover_letter_path, cover_letter_content)

    logger.info("Generated CV: %s", context.output_cv_path)
    logger.info("Generated cover letter: %s", context.output_cover_letter_path)
    state.current_node = "completed"
    state.status = "completed"
    touch_state(state)
    return state
