from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from time import monotonic

from checkpoint import save_checkpoint
from console_ui import (
    render_prompt,
    render_triage_decision_prompt,
    render_triage_result,
    render_variations,
)
from document_builder import (
    assemble_cv_document,
    extract_docx_text,
    preflight_template,
    write_cover_letters_markdown,
)
from graph_state import (
    AiOutputRecord,
    GraphState,
    ResponseEnvelope,
    SectionState,
    TriageResult,
    Variation,
    touch_state,
)
from json_parser import (
    ResponseParseError,
    ResponseSchemaError,
    parse_response_envelope_payload,
    parse_response_payload,
    parse_triage_result,
)
from llm_client import LlmGenerationResult, QuotaExceededError, generate_with_gemini
from logging_utils import log_failure
from prompt_loader import PromptTemplate, build_prompt_text
from section_ids import is_experience_section
from workflow_definition import (
    AUDIT_SECTION_ID,
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
TRIAGE_DECISION_MODE_PROMPT = "prompt"
TRIAGE_DECISION_MODE_FOLLOW_AI = "follow_ai"
TRIAGE_DECISION_MODE_ALWAYS_CONTINUE = "always_continue"
TRIAGE_DECISION_MODES = {
    TRIAGE_DECISION_MODE_PROMPT,
    TRIAGE_DECISION_MODE_FOLLOW_AI,
    TRIAGE_DECISION_MODE_ALWAYS_CONTINUE,
}
AUDIT_REQUIRED_HEADINGS: tuple[str, ...] = (
    "# Deep Dive CV Audit",
    "## Executive Summary",
    "## ATS Match Rate",
    "## Keyword Gap Analysis",
    "## Hiring Manager Read",
    "## Section-by-Section Critique",
    "## Evidence Gaps",
    "## Prioritized Fixes",
    "## Rewrite Directions",
    "## Final Verdict",
)

_LAST_LLM_REQUEST_STARTED_AT: float | None = None
_LLM_PACING_LOCK: asyncio.Lock | None = None


@dataclass
class RuntimeContext:
    run_dir: Path
    checkpoint_path: Path
    template_path: Path
    output_cv_path: Path
    output_cover_letters_path: Path
    output_audit_path: Path
    company_name: str
    job_description_path: Path
    job_description: str
    api_key: str
    model_name: str
    role_name: str
    prompt_templates: dict[str, PromptTemplate]
    debug_mode: bool
    auto_approve_review: bool
    triage_decision_mode: str
    use_role_wide_knowledge_cache: bool = False
    require_cached_token_confirmation: bool = True
    skills_category_count: int = 4
    cached_content_name: str | None = None
    invalidate_role_wide_knowledge_cache: bool = False
    force_knowledge_reupload: bool = False
    knowledge_cache_ttl_seconds: int = 0
    knowledge_cache_registry_path: Path | None = None


def _find_variation(variations: list[Variation], variation_id: str) -> Variation | None:
    for variation in variations:
        if variation.id == variation_id:
            return variation
    return None


def _experience_schema_retry_note(
    error: Exception | None, section_id: str
) -> str | None:
    if error is None or not is_experience_section(section_id):
        return None
    if "ordered variation ids" not in str(error):
        return None
    return (
        "Schema correction: reuse the same variation ids for every bullet in the same "
        "order. Prefer A, B, C without bullet-number prefixes such as 1A or 2B."
    )


def _best_variation(variations: list[Variation]) -> Variation:
    if not variations:
        raise ValueError("Cannot select a best variation from an empty list.")
    ranked = sorted(
        variations,
        key=lambda variation: (-variation.score_0_to_100, variation.id),
    )
    return ranked[0]


def _sorted_variations(variations: list[Variation]) -> list[Variation]:
    return sorted(
        variations,
        key=lambda variation: (-variation.score_0_to_100, variation.id),
    )


def _normalize_triage_action(raw_action: str) -> str:
    aliases = {
        "c": "continue",
        "s": "stop",
    }
    action = raw_action.strip().lower()
    return aliases.get(action, action)


def resolve_triage_decision_mode(value: str | None) -> str:
    if value is None:
        return TRIAGE_DECISION_MODE_PROMPT
    normalized = value.strip().lower()
    if normalized in TRIAGE_DECISION_MODES:
        return normalized
    return TRIAGE_DECISION_MODE_PROMPT


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


def _log_llm_usage(
    result: LlmGenerationResult,
    *,
    section_id: str,
    prompt: str,
    context: RuntimeContext,
    logger: logging.Logger,
) -> None:
    usage = result.usage_metadata
    logger.info(
        "LLM usage section_id=%s cached_content_name=%s prompt_chars=%s prompt_token_count=%s cached_content_token_count=%s candidates_token_count=%s thoughts_token_count=%s total_token_count=%s",
        section_id,
        context.cached_content_name or "-",
        len(prompt),
        usage.prompt_token_count if usage.prompt_token_count is not None else "-",
        (
            usage.cached_content_token_count
            if usage.cached_content_token_count is not None
            else "-"
        ),
        (
            usage.candidates_token_count
            if usage.candidates_token_count is not None
            else "-"
        ),
        usage.thoughts_token_count if usage.thoughts_token_count is not None else "-",
        usage.total_token_count if usage.total_token_count is not None else "-",
    )
    if not context.cached_content_name:
        return
    if not context.require_cached_token_confirmation:
        return
    cached_tokens = usage.cached_content_token_count or 0
    if cached_tokens <= 0:
        raise RuntimeError(
            "Cached token confirmation failed for "
            f"section '{section_id}' using '{context.cached_content_name}'."
        )


async def _request_llm(
    *,
    prompt: str,
    section_id: str,
    context: RuntimeContext,
    logger: logging.Logger,
) -> LlmGenerationResult:
    heartbeat_interval_seconds = _heartbeat_interval_seconds()
    await _wait_for_llm_pacing_slot(section_id, logger)
    logger.info(
        "LLM request started section_id=%s heartbeat_s=%s cached_content_name=%s",
        section_id,
        heartbeat_interval_seconds,
        context.cached_content_name or "-",
    )
    request_started = monotonic()
    request_task = asyncio.create_task(
        generate_with_gemini(
            prompt,
            context.api_key,
            context.model_name,
            section_id,
            context.cached_content_name,
            context.skills_category_count,
        )
    )
    while True:
        try:
            result = await asyncio.wait_for(
                asyncio.shield(request_task),
                timeout=heartbeat_interval_seconds,
            )
            break
        except asyncio.TimeoutError:
            elapsed_s = int(monotonic() - request_started)
            logger.info(
                "LLM request in progress section_id=%s elapsed_s=%s",
                section_id,
                elapsed_s,
            )
        except QuotaExceededError as exc:
            raise exc.with_section_id(section_id) from exc
    logger.info(
        "LLM request completed section_id=%s duration_ms=%s",
        section_id,
        int((monotonic() - request_started) * 1000),
    )
    _log_llm_usage(
        result,
        section_id=section_id,
        prompt=prompt,
        context=context,
        logger=logger,
    )
    return result


def _next_ai_output_attempt(section_state: SectionState) -> int:
    return len(section_state.ai_outputs) + 1


async def _generate_section_variations(
    section_id: str,
    section_state: SectionState,
    context: RuntimeContext,
    logger: logging.Logger,
) -> list[Variation]:
    template = context.prompt_templates[section_id]
    last_error: Exception | None = None
    for attempt in range(MAX_AUTOMATIC_PARSE_RETRIES + 1):
        retry_note = section_state.user_note
        schema_retry_note = _experience_schema_retry_note(last_error, section_id)
        if schema_retry_note:
            retry_note = (
                f"{retry_note}\n\n{schema_retry_note}"
                if retry_note
                else schema_retry_note
            )
        prompt = build_prompt_text(
            template=template,
            company_name=context.company_name,
            retry_note=retry_note,
            inline_knowledge=not context.use_role_wide_knowledge_cache,
            skills_category_count=(
                context.skills_category_count
                if section_id == "section_skills_alignment"
                else None
            ),
        )
        render_prompt(section_id, prompt)
        try:
            result = await _request_llm(
                prompt=prompt,
                section_id=section_id,
                context=context,
                logger=logger,
            )
        except QuotaExceededError as exc:
            raise exc.with_section_id(section_id) from exc
        if context.debug_mode:
            _write_debug_response(context.run_dir, section_id, attempt, result.text)

        output_attempt = _next_ai_output_attempt(section_state)
        try:
            parsed_payload = parse_response_payload(result.text)
        except ResponseParseError as exc:
            section_state.ai_outputs.append(
                AiOutputRecord(
                    attempt=output_attempt,
                    status="parse_error",
                    raw_response=result.text,
                    error_detail=str(exc),
                )
            )
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

        try:
            payload = parse_response_envelope_payload(
                result.text,
                section_id=section_id,
                skills_category_count=context.skills_category_count,
            )
            envelope = ResponseEnvelope.model_validate(payload.normalized_payload)
        except ResponseSchemaError as exc:
            section_state.ai_outputs.append(
                AiOutputRecord(
                    attempt=output_attempt,
                    status="schema_error",
                    raw_response=result.text,
                    parsed_payload=parsed_payload,
                    error_detail=str(exc),
                )
            )
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

        section_state.ai_outputs.append(
            AiOutputRecord(
                attempt=output_attempt,
                status="parsed",
                raw_response=result.text,
                parsed_payload=payload.parsed_payload,
                normalized_payload=payload.normalized_payload,
            )
        )

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
        if section_id == COVER_LETTER_SECTION_ID and len(envelope.variations) != 4:
            last_error = ResponseSchemaError(
                "Cover letter envelope must contain exactly 4 variations."
            )
            log_failure(
                logger,
                category="schema_error",
                node="generate_sections",
                section_id=section_id,
                attempt=attempt + 1,
                retry_count=section_state.retry_count,
                detail="Cover letter envelope must contain exactly 4 variations.",
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


def _validate_audit_markdown(markdown: str) -> str:
    normalized = markdown.strip()
    if not normalized:
        raise ResponseSchemaError("Audit response is empty.")
    if not normalized.startswith("#"):
        raise ResponseSchemaError("Audit response must start with a Markdown heading.")

    missing_headings = [
        heading for heading in AUDIT_REQUIRED_HEADINGS if heading not in normalized
    ]
    if missing_headings:
        missing = ", ".join(missing_headings)
        raise ResponseSchemaError(
            f"Audit response is missing required headings: {missing}."
        )
    return normalized


async def _generate_triage_result(
    section_state: SectionState, context: RuntimeContext, logger: logging.Logger
) -> TriageResult:
    template = context.prompt_templates[TRIAGE_SECTION_ID]
    prompt = build_prompt_text(
        template=template,
        company_name=context.company_name,
        retry_note=section_state.user_note,
        inline_knowledge=not context.use_role_wide_knowledge_cache,
    )
    render_prompt(TRIAGE_SECTION_ID, prompt)

    last_error: Exception | None = None
    for attempt in range(MAX_AUTOMATIC_PARSE_RETRIES + 1):
        try:
            result = await _request_llm(
                prompt=prompt,
                section_id=TRIAGE_SECTION_ID,
                context=context,
                logger=logger,
            )
        except QuotaExceededError as exc:
            raise exc.with_section_id(TRIAGE_SECTION_ID) from exc

        if context.debug_mode:
            _write_debug_response(
                context.run_dir, TRIAGE_SECTION_ID, attempt, result.text
            )

        output_attempt = _next_ai_output_attempt(section_state)
        try:
            parsed_payload = parse_response_payload(result.text)
        except ResponseParseError as exc:
            section_state.ai_outputs.append(
                AiOutputRecord(
                    attempt=output_attempt,
                    status="parse_error",
                    raw_response=result.text,
                    error_detail=str(exc),
                )
            )
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

        try:
            triage_result = parse_triage_result(result.text)
        except ResponseSchemaError as exc:
            section_state.ai_outputs.append(
                AiOutputRecord(
                    attempt=output_attempt,
                    status="schema_error",
                    raw_response=result.text,
                    parsed_payload=parsed_payload,
                    error_detail=str(exc),
                )
            )
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

        section_state.ai_outputs.append(
            AiOutputRecord(
                attempt=output_attempt,
                status="parsed",
                raw_response=result.text,
                parsed_payload=parsed_payload,
                normalized_payload={
                    "triage_result": triage_result.model_dump(mode="json")
                },
            )
        )
        return triage_result

    raise RuntimeError(
        "LLM triage response failed parsing after allowed retries."
    ) from last_error


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
        ai_outputs=section_state.ai_outputs,
    )

    suggested_action = "stop" if triage_result.verdict == "AVOID" else "continue"
    user_action = suggested_action
    if context.triage_decision_mode == TRIAGE_DECISION_MODE_ALWAYS_CONTINUE:
        user_action = "continue"
        logger.info(
            "Auto triage decision enabled. mode=%s suggested_action=%s forced_action=%s",
            context.triage_decision_mode,
            suggested_action,
            user_action,
        )
    elif context.triage_decision_mode == TRIAGE_DECISION_MODE_FOLLOW_AI:
        logger.info(
            "Auto triage decision enabled. mode=%s suggested_action=%s",
            context.triage_decision_mode,
            suggested_action,
        )
    else:
        print("")
        render_triage_decision_prompt(suggested_action=suggested_action)
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
            ai_outputs=section_state.ai_outputs,
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
    cover_letter_variations = state.section_states[COVER_LETTER_SECTION_ID].variations
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
    write_cover_letters_markdown(
        context.output_cover_letters_path,
        selected_content=cover_letter_content,
        variations=[
            {
                "id": variation.id,
                "score_0_to_100": variation.score_0_to_100,
                "ai_reasoning": variation.ai_reasoning,
                "content_for_template": variation.content_for_template,
            }
            for variation in _sorted_variations(cover_letter_variations)
        ],
    )

    logger.info("Generated CV: %s", context.output_cv_path)
    logger.info("Generated cover letters: %s", context.output_cover_letters_path)
    state.current_node = AUDIT_SECTION_ID
    state.status = "running"
    touch_state(state)
    return state


async def node_audit(
    state: GraphState, context: RuntimeContext, logger: logging.Logger
) -> GraphState:
    logger.info("Node audit started.")
    section_state = state.section_states[AUDIT_SECTION_ID]
    template = context.prompt_templates[AUDIT_SECTION_ID]
    cv_text = extract_docx_text(context.output_cv_path)
    prompt = build_prompt_text(
        template=template,
        company_name=context.company_name,
        inline_knowledge=not context.use_role_wide_knowledge_cache,
    )
    prompt = (
        f"{prompt}\n\n## Final Tailored CV\n\n"
        "Use this extracted text from the final generated CV as the audit target.\n\n"
        f"{cv_text}"
    ).strip()
    render_prompt(AUDIT_SECTION_ID, prompt)

    result = await _request_llm(
        prompt=prompt,
        section_id=AUDIT_SECTION_ID,
        context=context,
        logger=logger,
    )
    if context.debug_mode:
        _write_debug_response(context.run_dir, AUDIT_SECTION_ID, 0, result.text)

    output_attempt = _next_ai_output_attempt(section_state)
    audit_markdown = _validate_audit_markdown(result.text)

    section_state.ai_outputs.append(
        AiOutputRecord(
            attempt=output_attempt,
            status="parsed",
            raw_response=result.text,
        )
    )
    section_state.variations = []
    section_state.selected_variation_id = None
    section_state.selected_content = audit_markdown
    section_state.status = "approved"
    context.output_audit_path.write_text(audit_markdown + "\n", encoding="utf-8")
    logger.info("Generated CV audit: %s", context.output_audit_path)
    state.current_node = "completed"
    state.status = "completed"
    touch_state(state)
    return state
