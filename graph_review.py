from __future__ import annotations

import logging

from checkpoint import save_checkpoint
from graph_generation import RuntimeContext
from graph_state import GraphState, SectionState, Variation, touch_state
from workflow_definition import GENERATION_SECTION_IDS

MAX_USER_RETRIES_PER_SECTION = 2
REVIEW_STEP_DELIMITER = "=" * 72
REVIEW_SUB_DELIMITER = "-" * 72


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


def _generated_review_queue(state: GraphState) -> list[str]:
    return [
        section_id
        for section_id in GENERATION_SECTION_IDS
        if state.section_states[section_id].status == "generated"
    ]


def _retry_requested_sections(state: GraphState) -> list[str]:
    return [
        section_id
        for section_id in GENERATION_SECTION_IDS
        if state.section_states[section_id].status == "retry_requested"
    ]


def _all_required_sections_approved(state: GraphState) -> bool:
    return all(
        bool(state.section_states[section_id].selected_content)
        for section_id in GENERATION_SECTION_IDS
    )


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
    queue = state.review_queue or _generated_review_queue(state)

    total = len(queue)
    if context.auto_approve_review:
        for section_id in queue:
            section_state = state.section_states[section_id]
            if section_state.status != "generated" or not section_state.variations:
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
        if section_state.status != "generated" or not section_state.variations:
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

    retry_sections = _retry_requested_sections(state)
    if retry_sections:
        state.current_node = "generate_sections"
        state.status = "running"
        state.review_queue = retry_sections
        touch_state(state)
        return state, False

    if _all_required_sections_approved(state):
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
