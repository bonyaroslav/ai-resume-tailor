from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from time import monotonic
from pathlib import Path

from checkpoint import save_checkpoint
from console_ui import render_prompt, render_triage_result, render_variations
from document_builder import (
    assemble_cv_document,
    preflight_template,
    write_cover_letter,
)
from graph_state import GraphState, SectionState, TriageResult, Variation, touch_state
from json_parser import (
    ResponseParseError,
    ResponseSchemaError,
    parse_response_envelope,
    parse_triage_result,
)
from llm_client import QuotaExceededError, generate_with_gemini
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
LLM_MIN_INTERVAL_SECONDS = 12.0
LLM_MIN_INTERVAL_ENV = "ART_LLM_MIN_INTERVAL_SECONDS"
GENERATION_MODE_ENV = "ART_GENERATION_MODE"
GENERATION_MODE_SEQUENTIAL = "sequential"
GENERATION_MODE_CONCURRENT = "concurrent"
REVIEW_STEP_DELIMITER = "=" * 72
REVIEW_SUB_DELIMITER = "-" * 72
TRIAGE_STEP_DELIMITER = "=" * 72

_LAST_LLM_REQUEST_STARTED_AT: float | None = None
_LLM_PACING_LOCK: asyncio.Lock | None = None


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
    auto_approve_triage: bool


def _find_variation(variations: list[Variation], variation_id: str) -> Variation | None:
    for variation in variations:
        if variation.id == variation_id:
            return variation
    return None


def _best_variation(variations: list[Variation]) -> Variation:
    if not variations:
        raise ValueError("Cannot select a best variation from an empty list.")
    ranked = sorted(
        variations,
        key=lambda variation: (-variation.score_0_to_100, variation.id),
    )
    return ranked[0]


def _normalize_triage_action(raw_action: str) -> str:
    aliases = {
        "c": "continue",
        "s": "stop",
    }
    action = raw_action.strip().lower()
    return aliases.get(action, action)


def _prompt_triage_confirmation(*, suggested_action: str) -> str:
    while True:
        prompt = "Triage decision [continue/stop] (c/s): "
        if suggested_action == "stop":
            prompt = "Triage decision [stop/continue] (s/c): "
        action = _normalize_triage_action(input(prompt))
        if not action:
            return suggested_action
        if action in {"continue", "stop"}:
            return action
        print("Invalid decision. Use continue/stop (or c/s).")


def _heartbeat_interval_seconds() -> int:
    raw_value = os.getenv(LLM_HEARTBEAT_INTERVAL_ENV, "").strip()
    if not raw_value:
        return LLM_HEARTBEAT_INTERVAL_SECONDS
    try:
        interval = int(raw_value)
    except ValueError:
        return LLM_HEARTBEAT_INTERVAL_SECONDS
    return max(1, interval)


def _llm_min_interval_seconds() -> float:
    raw_value = os.getenv(LLM_MIN_INTERVAL_ENV, "").strip()
    if not raw_value:
        return LLM_MIN_INTERVAL_SECONDS
    try:
        interval = float(raw_value)
    except ValueError:
        return LLM_MIN_INTERVAL_SECONDS
    return max(0.0, interval)


def _generation_mode() -> str:
    mode = os.getenv(GENERATION_MODE_ENV, GENERATION_MODE_SEQUENTIAL).strip().lower()
    if mode in {GENERATION_MODE_SEQUENTIAL, GENERATION_MODE_CONCURRENT}:
        return mode
    return GENERATION_MODE_SEQUENTIAL


async def _wait_for_llm_pacing_slot(section_id: str, logger: logging.Logger) -> None:
    global _LAST_LLM_REQUEST_STARTED_AT
    global _LLM_PACING_LOCK

    if _LLM_PACING_LOCK is None:
        _LLM_PACING_LOCK = asyncio.Lock()

    min_interval_seconds = _llm_min_interval_seconds()
    if min_interval_seconds <= 0:
        return

    async with _LLM_PACING_LOCK:
        now = monotonic()
        if _LAST_LLM_REQUEST_STARTED_AT is not None:
            elapsed_seconds = now - _LAST_LLM_REQUEST_STARTED_AT
            wait_seconds = max(0.0, min_interval_seconds - elapsed_seconds)
            if wait_seconds > 0:
                logger.info(
                    "LLM pacing wait section_id=%s wait_s=%.2f min_interval_s=%.2f",
                    section_id,
                    wait_seconds,
                    min_interval_seconds,
                )
                await asyncio.sleep(wait_seconds)
        _LAST_LLM_REQUEST_STARTED_AT = monotonic()
        logger.info(
            "LLM pacing slot acquired section_id=%s min_interval_s=%.2f",
            section_id,
            min_interval_seconds,
        )


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
        await _wait_for_llm_pacing_slot(section_id, logger)
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
            except QuotaExceededError as exc:
                raise exc.with_section_id(section_id) from exc
        logger.info(
            "LLM request completed section_id=%s attempt=%s duration_ms=%s",
            section_id,
            attempt + 1,
            int((monotonic() - request_started) * 1000),
        )
        if context.debug_mode:
            _write_debug_response(context.run_dir, section_id, attempt, raw_response)
        try:
            envelope = parse_response_envelope(raw_response, section_id=section_id)
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


async def _generate_triage_result(
    section_state: SectionState, context: RuntimeContext, logger: logging.Logger
) -> TriageResult:
    template = context.prompt_templates[TRIAGE_SECTION_ID]
    prompt = build_prompt_text(
        template=template,
        company_name=context.company_name,
        job_description=context.job_description,
        retry_note=section_state.user_note,
    )
    render_prompt(TRIAGE_SECTION_ID, prompt)

    last_error: Exception | None = None
    heartbeat_interval_seconds = _heartbeat_interval_seconds()
    for attempt in range(MAX_AUTOMATIC_PARSE_RETRIES + 1):
        await _wait_for_llm_pacing_slot(TRIAGE_SECTION_ID, logger)
        logger.info(
            "LLM request started section_id=%s attempt=%s heartbeat_s=%s",
            TRIAGE_SECTION_ID,
            attempt + 1,
            heartbeat_interval_seconds,
        )
        request_started = monotonic()
        request_task = asyncio.create_task(
            generate_with_gemini(
                prompt, context.api_key, context.model_name, TRIAGE_SECTION_ID
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
                    TRIAGE_SECTION_ID,
                    attempt + 1,
                    elapsed_s,
                )
            except QuotaExceededError as exc:
                raise exc.with_section_id(TRIAGE_SECTION_ID) from exc
        logger.info(
            "LLM request completed section_id=%s attempt=%s duration_ms=%s",
            TRIAGE_SECTION_ID,
            attempt + 1,
            int((monotonic() - request_started) * 1000),
        )

        if context.debug_mode:
            _write_debug_response(
                context.run_dir, TRIAGE_SECTION_ID, attempt, raw_response
            )
        try:
            return parse_triage_result(raw_response)
        except ResponseParseError as exc:
            log_failure(
                logger,
                category="parse_error",
                node="triage",
                section_id=TRIAGE_SECTION_ID,
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
                node="triage",
                section_id=TRIAGE_SECTION_ID,
                attempt=attempt + 1,
                retry_count=section_state.retry_count,
                detail=str(exc),
            )
            last_error = exc
            continue

    raise RuntimeError(
        "LLM triage response failed parsing after allowed retries."
    ) from (last_error)


async def node_triage(
    state: GraphState, context: RuntimeContext, logger: logging.Logger
) -> GraphState:
    logger.info("Node triage started.")
    section_state = state.section_states[TRIAGE_SECTION_ID]
    triage_result = await _generate_triage_result(section_state, context, logger)
    render_triage_result(TRIAGE_SECTION_ID, triage_result)
    selected = Variation(
        id="TRIAGE",
        score_0_to_100=triage_result.decision_score_0_to_100,
        ai_reasoning=triage_result.summary,
        content_for_template=triage_result.report_markdown,
    )
    state.section_states[TRIAGE_SECTION_ID] = SectionState(
        status="approved",
        variations=[selected],
        selected_variation_id=selected.id,
        selected_content=selected.content_for_template,
        user_note=section_state.user_note,
        retry_count=section_state.retry_count,
    )

    suggested_action = "stop" if triage_result.verdict == "AVOID" else "continue"
    user_action = suggested_action
    if context.auto_approve_triage:
        logger.info(
            "Auto triage decision enabled. Using suggested_action=%s",
            suggested_action,
        )
    else:
        print("")
        print(TRIAGE_STEP_DELIMITER)
        print("Job fit triage completed.")
        print(
            "AI recommendation: "
            f"{'STOP (possible poor fit)' if suggested_action == 'stop' else 'CONTINUE'}"
        )
        print("Confirm if you want to continue with generation or stop now.")
        print(TRIAGE_STEP_DELIMITER)
        user_action = _prompt_triage_confirmation(suggested_action=suggested_action)
    logger.info(
        "Triage decision resolved suggested_action=%s user_action=%s",
        suggested_action,
        user_action,
    )

    if user_action == "stop":
        logger.info("Triage decision is stop. Ending run at triage_stop.")
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

    mode = _generation_mode()
    logger.info(
        "Generating sections mode=%s count=%s sections=%s",
        mode,
        len(targets),
        ", ".join(targets),
    )
    results: list[list[Variation] | Exception] = []
    if mode == GENERATION_MODE_CONCURRENT:
        tasks = [
            _generate_section_variations(
                section_id, state.section_states[section_id], context, logger
            )
            for section_id in targets
        ]
        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        for item in gathered:
            results.append(item)
    else:
        for section_id in targets:
            try:
                section_result = await _generate_section_variations(
                    section_id, state.section_states[section_id], context, logger
                )
                results.append(section_result)
            except Exception as exc:
                results.append(exc)

    for index, result in enumerate(results):
        section_id = targets[index]
        if isinstance(result, Exception):
            if isinstance(result, QuotaExceededError):
                raise result.with_section_id(section_id) from result
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
    print(REVIEW_SUB_DELIMITER)
    print(f"Section Variations: {section_id}")
    print(REVIEW_SUB_DELIMITER)
    for variation in section_state.variations:
        print(f"[{variation.id}] score={variation.score_0_to_100}")
        print(f"reason: {variation.ai_reasoning}")
        print(variation.content_for_template)
        print(REVIEW_SUB_DELIMITER)


def _print_review_header(
    section_id: str, position: int, total: int, retry_count: int
) -> None:
    print("")
    print(REVIEW_STEP_DELIMITER)
    print(f"[Review {position}/{total}] {section_id}")
    print(f"Retries used: {retry_count}/{MAX_USER_RETRIES_PER_SECTION}")
    print(REVIEW_STEP_DELIMITER)


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
    print("")
    print(REVIEW_STEP_DELIMITER)
    print("Review step started.")
    print("For each section, choose one action:")
    print("- choose: approve variation A/B/etc.")
    print("- edit: select a variation and provide final text")
    print("- retry: request regeneration with guidance note")
    print("- save_and_exit: save progress and continue later")
    print(REVIEW_STEP_DELIMITER)
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
            selected = _best_variation(section_state.variations)
            _approve_variation(section_state, selected)
            rejected = ", ".join(
                f"{variation.id}:{variation.score_0_to_100}"
                for variation in section_state.variations
                if variation.id != selected.id
            )
            logger.info(
                "Auto-approved section_id=%s variation_id=%s score_0_to_100=%s rejected=%s",
                section_id,
                section_state.selected_variation_id,
                selected.score_0_to_100,
                rejected or "-",
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
