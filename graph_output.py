from __future__ import annotations

import logging

from document_builder import (
    assemble_cv_document,
    extract_docx_text,
    preflight_template,
    write_cover_letters_markdown,
)
from graph_generation import RuntimeContext, _record_ai_output, _request_llm
from graph_state import GraphState, SectionState, Variation, touch_state
from json_parser import ResponseSchemaError
from logging_utils import log_failure
from prompt_loader import build_prompt_text
from workflow_definition import (
    AUDIT_SECTION_ID,
    COVER_LETTER_SECTION_ID,
    TEMPLATE_SECTION_IDS,
)


def _sorted_variations(variations: list[Variation]) -> list[Variation]:
    return sorted(
        variations,
        key=lambda variation: (-variation.score_0_to_100, variation.id),
    )


def _normalize_audit_markdown(markdown: str) -> str:
    normalized = markdown.strip()
    if not normalized:
        raise ResponseSchemaError("Audit response is empty.")
    return normalized


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
    from console_ui import render_prompt

    render_prompt(AUDIT_SECTION_ID, prompt)

    result = await _request_llm(
        prompt=prompt,
        section_id=AUDIT_SECTION_ID,
        context=context,
        logger=logger,
    )
    output_record = _record_ai_output(
        run_dir=context.run_dir,
        section_id=AUDIT_SECTION_ID,
        attempt=0,
        raw_response=result.text,
        section_state=section_state,
        debug_mode=context.debug_mode,
    )
    audit_markdown = _normalize_audit_markdown(result.text)
    output_record.status = "parsed"
    state.section_states[AUDIT_SECTION_ID] = SectionState(
        status="approved",
        variations=[],
        selected_variation_id=None,
        selected_content=audit_markdown,
        user_note=section_state.user_note,
        retry_count=section_state.retry_count,
        ai_outputs=section_state.ai_outputs,
    )
    context.output_audit_path.write_text(audit_markdown + "\n", encoding="utf-8")
    logger.info("Generated CV audit: %s", context.output_audit_path)
    state.current_node = "completed"
    state.status = "completed"
    touch_state(state)
    return state
