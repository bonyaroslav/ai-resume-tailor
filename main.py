from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path
from time import monotonic

from checkpoint import CheckpointError, load_checkpoint, save_checkpoint
from document_builder import TemplateValidationError, preflight_template
from graph_nodes import (
    RuntimeContext,
    node_audit,
    node_assemble,
    node_generate_sections,
    node_review,
    node_triage,
    resolve_triage_decision_mode,
)
from graph_router import route_next_node
from graph_state import GraphState, SectionState, create_initial_state, touch_state
from job_description_loader import read_job_description
from knowledge_cache import (
    DEFAULT_KNOWLEDGE_CACHE_REGISTRY_PATH,
    DEFAULT_KNOWLEDGE_CACHE_TTL_SECONDS,
    KnowledgeCacheError,
    prepare_run_scoped_knowledge_cache,
)
from logging_utils import configure_logging, log_failure, sha256_short
from prompt_loader import PromptValidationError, discover_prompt_templates
from run_artifacts import create_run_directory, load_run_metadata, write_run_metadata
from settings import (
    DEFAULT_ROLE_NAME,
    ROLE_NAME_ENV,
    default_template_path_for_role,
    role_knowledge_dir,
    role_prompts_dir,
    resolve_gemini_model_name,
    resolve_output_cv_filename,
    resolve_role_name,
)
from workflow_definition import (
    GENERATION_SECTION_IDS,
    TEMPLATE_SECTION_IDS,
    TRIAGE_SECTION_ID,
)

LEGACY_DEFAULT_TEMPLATE_PATH = Path(
    "knowledge/Template - YB Senior Software Engineer.docx"
)
DEFAULT_TEMPLATE_PATH = str(default_template_path_for_role(DEFAULT_ROLE_NAME))
AUTO_APPROVE_REVIEW_ENV = "ART_AUTO_APPROVE_REVIEW"
TRIAGE_DECISION_MODE_ENV = "ART_TRIAGE_DECISION_MODE"
OFFLINE_MODE_ENV = "ART_OFFLINE_MODE"
USE_ROLE_WIDE_KNOWLEDGE_CACHE_ENV = "ART_USE_ROLE_WIDE_KNOWLEDGE_CACHE"
REQUIRE_CACHED_TOKEN_CONFIRMATION_ENV = "ART_REQUIRE_CACHED_TOKEN_CONFIRMATION"
KNOWLEDGE_CACHE_TTL_SECONDS_ENV = "ART_KNOWLEDGE_CACHE_TTL_SECONDS"
KNOWLEDGE_CACHE_REGISTRY_PATH_ENV = "ART_KNOWLEDGE_CACHE_REGISTRY_PATH"
FORCE_KNOWLEDGE_REUPLOAD_ENV = "ART_FORCE_KNOWLEDGE_REUPLOAD"
DEFAULT_SKILLS_CATEGORY_COUNT = 4
RUN_JOB_DESCRIPTION_FILENAME = "job_description.md"
LEGACY_RUN_JOB_DESCRIPTION_FILENAME = "job_description.txt"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI Resume Tailor")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Start a new run")
    run_parser.add_argument("--jd-path", required=True, type=Path)
    run_parser.add_argument("--company", required=True)
    run_parser.add_argument("--job-title", default=None)
    run_parser.add_argument("--template-path", type=Path, default=None)
    run_parser.add_argument("--model", default=None)
    run_parser.add_argument("--role", default=None)
    run_parser.add_argument("--debug", action="store_true")
    run_parser.add_argument("--invalidate-cache", action="store_true")
    run_parser.add_argument("--force-knowledge-reupload", action="store_true")
    run_parser.add_argument("--skills-category-count", type=int, default=None)

    resume_parser = subparsers.add_parser("resume", help="Resume from checkpoint")
    resume_group = resume_parser.add_mutually_exclusive_group(required=True)
    resume_group.add_argument("--run-path", type=Path)
    resume_group.add_argument("--checkpoint-path", type=Path)
    resume_parser.add_argument("--model", default=None)
    resume_parser.add_argument("--role", default=None)
    resume_parser.add_argument("--invalidate-cache", action="store_true")
    resume_parser.add_argument("--force-knowledge-reupload", action="store_true")
    resume_parser.add_argument("--skills-category-count", type=int, default=None)

    status_parser = subparsers.add_parser(
        "status", help="Show status summary for a run"
    )
    status_group = status_parser.add_mutually_exclusive_group(required=True)
    status_group.add_argument("--run-path", type=Path)
    status_group.add_argument("--checkpoint-path", type=Path)

    regenerate_parser = subparsers.add_parser(
        "regenerate", help="Regenerate selected sections for an existing run"
    )
    regenerate_group = regenerate_parser.add_mutually_exclusive_group(required=True)
    regenerate_group.add_argument("--run-path", type=Path)
    regenerate_group.add_argument("--checkpoint-path", type=Path)
    regenerate_parser.add_argument("--sections", required=True)
    regenerate_parser.add_argument("--note", required=True)
    regenerate_parser.add_argument("--model", default=None)
    regenerate_parser.add_argument("--role", default=None)
    regenerate_parser.add_argument("--invalidate-cache", action="store_true")
    regenerate_parser.add_argument("--force-knowledge-reupload", action="store_true")
    regenerate_parser.add_argument("--skills-category-count", type=int, default=None)

    rebuild_parser = subparsers.add_parser(
        "rebuild-output", help="Rebuild CV and cover letter from approved content"
    )
    rebuild_group = rebuild_parser.add_mutually_exclusive_group(required=True)
    rebuild_group.add_argument("--run-path", type=Path)
    rebuild_group.add_argument("--checkpoint-path", type=Path)
    rebuild_parser.add_argument("--role", default=None)

    return parser


def _load_api_key() -> str:
    if _is_truthy_env(os.getenv(OFFLINE_MODE_ENV)):
        return "offline-mode"
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY environment variable.")
    return api_key


def _is_truthy_env(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _truthy_env_with_default(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    stripped = value.strip()
    if not stripped:
        return default
    return _is_truthy_env(stripped)


def _int_env_with_default(value: str | None, *, default: int) -> int:
    if value is None:
        return default
    stripped = value.strip()
    if not stripped:
        return default
    try:
        parsed = int(stripped)
    except ValueError:
        return default
    return max(1, parsed)


def _resolve_skills_category_count(
    explicit_count: int | None,
    *,
    metadata_count: str | None,
) -> int:
    if explicit_count is not None:
        return max(1, explicit_count)
    if metadata_count:
        try:
            return max(1, int(metadata_count.strip()))
        except ValueError:
            return DEFAULT_SKILLS_CATEGORY_COUNT
    return DEFAULT_SKILLS_CATEGORY_COUNT


def _knowledge_cache_registry_path() -> Path:
    raw_value = os.getenv(KNOWLEDGE_CACHE_REGISTRY_PATH_ENV, "").strip()
    if not raw_value:
        return DEFAULT_KNOWLEDGE_CACHE_REGISTRY_PATH
    return Path(raw_value)


def _job_description_preview(job_description: str, *, max_lines: int = 3) -> str:
    lines = [line.strip() for line in job_description.splitlines() if line.strip()]
    if not lines:
        return "-"
    preview = " | ".join(lines[:max_lines]).strip()
    if len(lines) > max_lines:
        return f"{preview} | ..."
    return preview


def _print_status_summary(state: GraphState, run_dir: Path) -> None:
    triage_status = state.section_states[TRIAGE_SECTION_ID].status
    pending = 0
    generated = 0
    approved = 0
    retry_requested = 0
    for section_id in GENERATION_SECTION_IDS:
        section_status = state.section_states[section_id].status
        if section_status == "approved":
            approved += 1
            continue
        if section_status == "generated":
            generated += 1
            continue
        if section_status == "retry_requested":
            retry_requested += 1
            continue
        pending += 1

    print("")
    print("=" * 72)
    print(f"Run folder: {run_dir}")
    print(f"Overall status: {state.status} | Current node: {state.current_node}")
    print(
        "Stages: "
        f"triage={triage_status}, "
        f"approved={approved}/{len(GENERATION_SECTION_IDS)}, "
        f"generated={generated}, retry_requested={retry_requested}, pending={pending}"
    )
    print("=" * 72)

    print("Selected variations:")
    for section_id in GENERATION_SECTION_IDS:
        section_state = state.section_states[section_id]
        selected_id = section_state.selected_variation_id or "-"
        selected_score = _selected_variation_score(section_state)
        score_text = str(selected_score) if selected_score is not None else "-"
        print(
            f"- {section_id}: selected={selected_id}, score_0_to_100={score_text}, status={section_state.status}"
        )


def _print_next_steps(state: GraphState, run_dir: Path) -> None:
    print("What you can do next:")
    if state.status in {"running", "awaiting_review"}:
        print(f"1. Resume: python main.py resume --run-path {run_dir}")
        print(f"2. Inspect status: python main.py status --run-path {run_dir}")
        return
    if state.status == "failed":
        print(f"1. Resume after fix: python main.py resume --run-path {run_dir}")
        print(f"2. Inspect status: python main.py status --run-path {run_dir}")
        return
    if state.current_node == "triage_stop":
        print(f"1. Resume and continue: python main.py resume --run-path {run_dir}")
        print(f"2. Inspect status: python main.py status --run-path {run_dir}")
        return
    if state.status == "completed":
        print(f"1. Rebuild outputs: python main.py rebuild-output --run-path {run_dir}")
        print(
            f'2. Regenerate sections: python main.py regenerate --run-path {run_dir} --sections section_professional_summary --note "improve impact metrics"'
        )
        print(f"3. Inspect status: python main.py status --run-path {run_dir}")
        return
    print("1. Exit.")


def _prompt_action(prompt_text: str, allowed: dict[str, str]) -> str:
    while True:
        raw = input(prompt_text).strip().lower()
        choice = allowed.get(raw, raw)
        if choice in allowed.values():
            return choice
        print(
            f"Invalid choice. Valid options: {', '.join(sorted(set(allowed.values())))}"
        )


def _mark_sections_for_regeneration(
    state: GraphState, section_ids: list[str], note: str
) -> None:
    for section_id in section_ids:
        section_state = state.section_states[section_id]
        section_state.status = "retry_requested"
        section_state.selected_variation_id = None
        section_state.selected_content = None
        section_state.user_note = note
        section_state.variations = []
    state.status = "running"
    state.current_node = "review"
    state.review_queue = section_ids
    touch_state(state)


def _prompt_sections_for_regeneration() -> list[str]:
    print("Available section IDs:")
    for section_id in GENERATION_SECTION_IDS:
        print(f"- {section_id}")
    while True:
        raw = input("Sections to regenerate (comma-separated or 'all'): ").strip()
        if not raw:
            print("Please provide at least one section id or 'all'.")
            continue
        if raw.lower() == "all":
            return list(GENERATION_SECTION_IDS)
        requested = [item.strip() for item in raw.split(",") if item.strip()]
        unique_requested = list(dict.fromkeys(requested))
        invalid = [
            item for item in unique_requested if item not in GENERATION_SECTION_IDS
        ]
        if invalid:
            print(f"Unknown section ids: {', '.join(invalid)}")
            continue
        return unique_requested


def _prepare_rebuild_from_completed_state(state: GraphState) -> bool:
    missing_sections = [
        section_id
        for section_id in GENERATION_SECTION_IDS
        if not state.section_states[section_id].selected_content
    ]
    if missing_sections:
        print("Cannot rebuild outputs because approved content is missing for:")
        print(", ".join(missing_sections))
        print("Use regenerate first, then approve sections in review.")
        return False
    state.status = "running"
    state.current_node = "assemble"
    state.review_queue = []
    touch_state(state)
    return True


def _selected_variation_score(section_state: SectionState) -> int | None:
    selected_id = section_state.selected_variation_id
    if not selected_id:
        return None
    for variation in section_state.variations:
        if variation.id == selected_id:
            return variation.score_0_to_100
    return None


def _load_metadata_or_default(
    run_dir: Path, args: argparse.Namespace
) -> dict[str, str]:
    try:
        metadata = load_run_metadata(run_dir)
    except Exception:
        metadata = {
            "run_id": run_dir.name,
            "company_name": args.company,
            "job_title": getattr(args, "job_title", None) or "",
            "model_name": resolve_gemini_model_name(args.model),
            "output_cv_filename": resolve_output_cv_filename(),
            "debug_mode": str(bool(args.debug)).lower(),
        }
    return metadata


def _resolve_role_name_for_command(
    explicit_role: str | None,
    *,
    metadata_role: str | None,
) -> str:
    if (
        explicit_role
        and metadata_role
        and explicit_role.strip()
        and explicit_role.strip() != metadata_role.strip()
    ):
        raise SystemExit(
            "Role mismatch for this run. "
            f"Saved role is '{metadata_role.strip()}', "
            f"but '--role {explicit_role.strip()}' was requested."
        )
    return resolve_role_name(explicit_role, metadata_role=metadata_role)


def _resolve_template_path(
    explicit_template: Path | None,
    *,
    metadata_template: str | None,
    role_name: str,
) -> Path:
    if explicit_template is not None:
        return explicit_template
    if metadata_template:
        candidate = Path(metadata_template)
        role_default = default_template_path_for_role(role_name)
        if (
            candidate == LEGACY_DEFAULT_TEMPLATE_PATH
            and not candidate.exists()
            and role_default.exists()
        ):
            return role_default
        return candidate
    return default_template_path_for_role(role_name)


def _resolve_run_checkpoint_pair(args: argparse.Namespace) -> tuple[Path, Path]:
    checkpoint_path = getattr(args, "checkpoint_path", None)
    if checkpoint_path:
        return checkpoint_path.parent, checkpoint_path
    run_path = getattr(args, "run_path", None)
    if run_path:
        return run_path, run_path / "state_checkpoint.json"
    raise ValueError("Expected run-path or checkpoint-path.")


def _parse_requested_sections(raw_sections: str) -> list[str]:
    value = raw_sections.strip()
    if not value:
        raise ValueError("sections cannot be empty.")
    if value.lower() == "all":
        return list(GENERATION_SECTION_IDS)
    parsed = [item.strip() for item in value.split(",") if item.strip()]
    unique_parsed = list(dict.fromkeys(parsed))
    invalid = [item for item in unique_parsed if item not in GENERATION_SECTION_IDS]
    if invalid:
        raise ValueError(f"Unknown section ids: {', '.join(invalid)}")
    return unique_parsed


def _normalize_regeneration_note(raw_note: str) -> str:
    note = raw_note.strip()
    if not note:
        raise ValueError("Regeneration note cannot be empty.")
    return note


def _prompt_regeneration_note() -> str:
    while True:
        raw_note = input("Regeneration note: ")
        try:
            return _normalize_regeneration_note(raw_note)
        except ValueError as exc:
            print(str(exc))


def _ensure_regenerate_allowed(state: GraphState) -> None:
    if state.current_node == "triage_stop":
        raise ValueError(
            "Cannot regenerate because this run stopped at triage. "
            "Resume the run and choose continue_anyway first."
        )
    if state.status != "completed" or state.current_node != "completed":
        raise ValueError(
            "Regenerate is only available for completed runs. "
            "Use resume for in-progress runs."
        )


def _ensure_rebuild_allowed(state: GraphState) -> None:
    if state.current_node == "triage_stop":
        raise ValueError(
            "Cannot rebuild outputs because this run stopped at triage. "
            "Resume the run and choose continue_anyway first."
        )
    if state.status != "completed" or state.current_node != "completed":
        raise ValueError(
            "Rebuild-output is only available for completed runs. "
            "Use resume for in-progress runs."
        )


def _resolve_run_state_for_run_command(
    *,
    run_dir: Path,
    checkpoint_path: Path,
    args: argparse.Namespace,
) -> tuple[GraphState, str]:
    if not checkpoint_path.exists():
        initial_state = create_initial_state(run_id=run_dir.name)
        save_checkpoint(checkpoint_path, initial_state)
        return initial_state, "start"

    state = load_checkpoint(checkpoint_path)
    _print_status_summary(state, run_dir)
    _print_next_steps(state, run_dir)

    if state.status in {"running", "awaiting_review", "failed"}:
        action = _prompt_action(
            "Action [resume/exit] (r/e): ",
            {"r": "resume", "e": "exit", "resume": "resume", "exit": "exit"},
        )
        return state, action

    if state.current_node == "triage_stop":
        action = _prompt_action(
            "Action [continue_anyway/exit] (c/e): ",
            {
                "c": "continue_anyway",
                "e": "exit",
                "continue_anyway": "continue_anyway",
                "exit": "exit",
            },
        )
        if action == "continue_anyway":
            state.status = "running"
            state.current_node = "generate_sections"
            state.review_queue = []
            touch_state(state)
            save_checkpoint(checkpoint_path, state)
        return state, action

    if state.status == "completed":
        action = _prompt_action(
            "Action [rebuild/regenerate/exit] (b/g/e): ",
            {
                "b": "rebuild",
                "g": "regenerate",
                "e": "exit",
                "rebuild": "rebuild",
                "regenerate": "regenerate",
                "exit": "exit",
            },
        )
        if action == "rebuild":
            if not _prepare_rebuild_from_completed_state(state):
                return state, "exit"
            save_checkpoint(checkpoint_path, state)
            return state, "resume"
        if action == "regenerate":
            target_sections = _prompt_sections_for_regeneration()
            note = _prompt_regeneration_note()
            _mark_sections_for_regeneration(state, target_sections, note)
            save_checkpoint(checkpoint_path, state)
            return state, "resume"
        return state, "exit"

    return state, "exit"


def _save_checkpoint_or_raise(
    *,
    checkpoint_path: Path,
    state: GraphState,
    logger: logging.Logger,
    node: str,
) -> None:
    try:
        save_checkpoint(checkpoint_path, state)
    except Exception as exc:
        log_failure(
            logger,
            category="checkpoint_error",
            node=node,
            detail=str(exc),
        )
        raise


async def _ensure_role_wide_knowledge_cache(
    *,
    state: GraphState,
    context: RuntimeContext,
    logger: logging.Logger,
) -> None:
    next_node = route_next_node(state)
    if next_node not in {"triage", "generate_sections"}:
        return
    if not context.use_role_wide_knowledge_cache:
        return
    if context.cached_content_name:
        return
    if context.api_key == "offline-mode":
        logger.info("Knowledge cache disabled because offline mode is active.")
        context.use_role_wide_knowledge_cache = False
        return

    cache = await asyncio.to_thread(
        prepare_run_scoped_knowledge_cache,
        api_key=context.api_key,
        run_id=state.run_id,
        role_name=context.role_name,
        model_name=context.model_name,
        prompt_templates=context.prompt_templates,
        job_description_path=context.job_description_path,
        registry_path=context.knowledge_cache_registry_path,
        ttl_seconds=context.knowledge_cache_ttl_seconds,
        invalidate_cache=context.invalidate_role_wide_knowledge_cache,
        force_reupload=context.force_knowledge_reupload,
        logger=logger,
    )
    context.cached_content_name = cache.remote_cache_name
    logger.info(
        "Knowledge cache ready remote_cache_name=%s stable_fingerprint=%s expires_at=%s",
        cache.remote_cache_name,
        cache.stable_fingerprint,
        cache.expires_at or "-",
    )


async def _run_graph(state: GraphState, context: RuntimeContext) -> GraphState:
    logger = configure_logging(context.run_dir, context.debug_mode)
    logger.info("Run started. run_id=%s, model=%s", state.run_id, context.model_name)
    logger.info(
        "Loaded JD metadata path=%s chars=%s sha256=%s",
        context.job_description_path,
        len(context.job_description),
        sha256_short(context.job_description),
    )
    logger.info(
        "Loaded JD preview first_3_lines=%s",
        _job_description_preview(context.job_description, max_lines=3),
    )

    while True:
        next_node = route_next_node(state)
        if next_node == "end":
            break

        await _ensure_role_wide_knowledge_cache(
            state=state,
            context=context,
            logger=logger,
        )

        _save_checkpoint_or_raise(
            checkpoint_path=context.checkpoint_path,
            state=state,
            logger=logger,
            node=next_node,
        )
        node_started = monotonic()
        try:
            if next_node == "triage":
                state = await node_triage(state, context, logger)
                logger.info(
                    "Node triage completed duration_ms=%s status=%s current_node=%s",
                    int((monotonic() - node_started) * 1000),
                    state.status,
                    state.current_node,
                )
                continue

            if next_node == "generate_sections":
                state = await node_generate_sections(state, context, logger)
                logger.info(
                    "Node generate_sections completed duration_ms=%s status=%s current_node=%s",
                    int((monotonic() - node_started) * 1000),
                    state.status,
                    state.current_node,
                )
                continue

            if next_node == "review":
                state, should_exit = node_review(state, context, logger)
                _save_checkpoint_or_raise(
                    checkpoint_path=context.checkpoint_path,
                    state=state,
                    logger=logger,
                    node=next_node,
                )
                logger.info(
                    "Node review completed duration_ms=%s status=%s current_node=%s should_exit=%s",
                    int((monotonic() - node_started) * 1000),
                    state.status,
                    state.current_node,
                    should_exit,
                )
                if should_exit:
                    logger.info("State saved. Exiting on user save_and_exit action.")
                    return state
                continue

            if next_node == "assemble":
                state = node_assemble(state, context, logger)
                logger.info(
                    "Node assemble completed duration_ms=%s status=%s current_node=%s",
                    int((monotonic() - node_started) * 1000),
                    state.status,
                    state.current_node,
                )
                continue

            if next_node == "audit_cv_deep_dive":
                state = await node_audit(state, context, logger)
                logger.info(
                    "Node audit_cv_deep_dive completed duration_ms=%s status=%s current_node=%s",
                    int((monotonic() - node_started) * 1000),
                    state.status,
                    state.current_node,
                )
                continue

            raise ValueError(f"Unhandled node '{next_node}'")
        except Exception:
            state.status = "failed"
            state.current_node = next_node
            touch_state(state)
            log_failure(
                logger,
                category="workflow_error",
                node=next_node,
                detail="Workflow node execution failed.",
            )
            _save_checkpoint_or_raise(
                checkpoint_path=context.checkpoint_path,
                state=state,
                logger=logger,
                node=next_node,
            )
            logger.exception("Workflow failed at node '%s'.", next_node)
            raise

    _save_checkpoint_or_raise(
        checkpoint_path=context.checkpoint_path,
        state=state,
        logger=logger,
        node=state.current_node,
    )
    logger.info("Run finished with status=%s.", state.status)
    return state


def _prepare_runtime_context(
    *,
    run_dir: Path,
    company_name: str,
    job_description_path: Path,
    job_description: str,
    template_path: Path,
    model_name: str,
    role_name: str,
    output_cv_filename: str,
    debug_mode: bool,
    skills_category_count: int,
) -> RuntimeContext:
    prompts_dir = role_prompts_dir(role_name)
    knowledge_dir = role_knowledge_dir(role_name)
    prompt_templates = discover_prompt_templates(prompts_dir, knowledge_dir)
    preflight_template(template_path, TEMPLATE_SECTION_IDS)

    checkpoint_path = run_dir / "state_checkpoint.json"
    context = RuntimeContext(
        run_dir=run_dir,
        checkpoint_path=checkpoint_path,
        template_path=template_path,
        output_cv_path=run_dir / output_cv_filename,
        output_cover_letters_path=run_dir / "cover_letters.md",
        output_audit_path=run_dir / "cv_deep_dive_audit.md",
        company_name=company_name,
        job_description_path=job_description_path,
        job_description=job_description,
        api_key=_load_api_key(),
        model_name=model_name,
        role_name=role_name,
        prompt_templates=prompt_templates,
        debug_mode=debug_mode,
        auto_approve_review=_truthy_env_with_default(
            os.getenv(AUTO_APPROVE_REVIEW_ENV),
            default=True,
        ),
        triage_decision_mode=resolve_triage_decision_mode(
            os.getenv(TRIAGE_DECISION_MODE_ENV)
        ),
        use_role_wide_knowledge_cache=_truthy_env_with_default(
            os.getenv(USE_ROLE_WIDE_KNOWLEDGE_CACHE_ENV),
            default=True,
        ),
        require_cached_token_confirmation=_truthy_env_with_default(
            os.getenv(REQUIRE_CACHED_TOKEN_CONFIRMATION_ENV),
            default=True,
        ),
        skills_category_count=skills_category_count,
        cached_content_name=None,
    )
    return context


def _configure_cache_runtime_context(
    context: RuntimeContext, *, invalidate_cache: bool, force_knowledge_reupload: bool
) -> None:
    context.invalidate_role_wide_knowledge_cache = invalidate_cache
    env_force = _truthy_env_with_default(
        os.getenv(FORCE_KNOWLEDGE_REUPLOAD_ENV), default=False
    )
    context.force_knowledge_reupload = force_knowledge_reupload or env_force
    context.knowledge_cache_ttl_seconds = _int_env_with_default(
        os.getenv(KNOWLEDGE_CACHE_TTL_SECONDS_ENV),
        default=DEFAULT_KNOWLEDGE_CACHE_TTL_SECONDS,
    )
    context.knowledge_cache_registry_path = _knowledge_cache_registry_path()


def _run_job_description_path(run_dir: Path) -> Path:
    return run_dir / RUN_JOB_DESCRIPTION_FILENAME


def _legacy_run_job_description_path(run_dir: Path) -> Path:
    return run_dir / LEGACY_RUN_JOB_DESCRIPTION_FILENAME


def _load_existing_run_job_description(run_dir: Path) -> tuple[Path, str]:
    jd_path = _run_job_description_path(run_dir)
    if jd_path.exists():
        return jd_path, jd_path.read_text(encoding="utf-8")

    legacy_path = _legacy_run_job_description_path(run_dir)
    if legacy_path.exists():
        jd_text = legacy_path.read_text(encoding="utf-8")
        jd_path.write_text(jd_text, encoding="utf-8")
        return jd_path, jd_text

    raise FileNotFoundError(
        f"Run job description not found: {_run_job_description_path(run_dir)}"
    )


def _persist_run_job_description(run_dir: Path, source_path: Path) -> tuple[Path, str]:
    jd_text = read_job_description(source_path)
    jd_path = _run_job_description_path(run_dir)
    jd_path.write_text(jd_text, encoding="utf-8")
    return jd_path, jd_text


async def _handle_run(args: argparse.Namespace) -> None:
    run_dir = create_run_directory(
        Path("runs"),
        args.company,
        getattr(args, "job_title", None),
    )
    checkpoint_path = run_dir / "state_checkpoint.json"
    state, action = _resolve_run_state_for_run_command(
        run_dir=run_dir,
        checkpoint_path=checkpoint_path,
        args=args,
    )
    if action == "exit":
        print("Exited without changes.")
        return

    metadata = _load_metadata_or_default(run_dir, args)
    role_name = _resolve_role_name_for_command(
        args.role,
        metadata_role=metadata.get("role_name"),
    )
    os.environ[ROLE_NAME_ENV] = role_name
    jd_path, jd_text = _persist_run_job_description(run_dir, args.jd_path)

    model_name = resolve_gemini_model_name(
        args.model,
        metadata_model=metadata.get("model_name"),
    )
    output_cv_filename = resolve_output_cv_filename(
        metadata_filename=metadata.get("output_cv_filename")
    )
    template_path = _resolve_template_path(
        args.template_path,
        metadata_template=metadata.get("template_path"),
        role_name=role_name,
    )
    debug_mode = metadata.get("debug_mode", "false") == "true"
    if args.debug:
        debug_mode = True

    skills_category_count = _resolve_skills_category_count(
        getattr(args, "skills_category_count", None),
        metadata_count=metadata.get("skills_category_count"),
    )
    context = _prepare_runtime_context(
        run_dir=run_dir,
        company_name=metadata.get("company_name", args.company),
        job_description_path=jd_path,
        job_description=jd_text,
        template_path=template_path,
        model_name=model_name,
        role_name=role_name,
        output_cv_filename=output_cv_filename,
        debug_mode=debug_mode,
        skills_category_count=skills_category_count,
    )
    _configure_cache_runtime_context(
        context,
        invalidate_cache=getattr(args, "invalidate_cache", False),
        force_knowledge_reupload=getattr(args, "force_knowledge_reupload", False),
    )

    write_run_metadata(
        run_dir,
        {
            "run_id": run_dir.name,
            "company_name": metadata.get("company_name", args.company),
            "job_title": metadata.get("job_title", getattr(args, "job_title", None))
            or "",
            "template_path": str(template_path),
            "model_name": model_name,
            "role_name": role_name,
            "output_cv_filename": output_cv_filename,
            "debug_mode": str(debug_mode).lower(),
            "skills_category_count": str(skills_category_count),
        },
    )
    print(f"Using run folder: {run_dir}")
    print(f"Model: {model_name}")
    print(f"Role: {role_name}")
    print(f"JD preview: {_job_description_preview(jd_text, max_lines=3)}")
    final_state = await _run_graph(state, context)
    _print_status_summary(final_state, run_dir)
    _print_next_steps(final_state, run_dir)


async def _handle_resume(args: argparse.Namespace) -> None:
    run_dir, checkpoint_path = _resolve_run_checkpoint_pair(args)

    state = load_checkpoint(checkpoint_path)
    metadata = load_run_metadata(run_dir)
    role_name = _resolve_role_name_for_command(
        args.role,
        metadata_role=metadata.get("role_name"),
    )
    os.environ[ROLE_NAME_ENV] = role_name
    jd_path, jd_text = _load_existing_run_job_description(run_dir)
    _print_status_summary(state, run_dir)
    _print_next_steps(state, run_dir)

    model_name = resolve_gemini_model_name(
        args.model,
        metadata_model=metadata.get("model_name"),
    )
    output_cv_filename = resolve_output_cv_filename(
        metadata_filename=metadata.get("output_cv_filename")
    )
    context = _prepare_runtime_context(
        run_dir=run_dir,
        company_name=metadata["company_name"],
        job_description_path=jd_path,
        job_description=jd_text,
        template_path=_resolve_template_path(
            explicit_template=None,
            metadata_template=metadata.get("template_path"),
            role_name=role_name,
        ),
        model_name=model_name,
        role_name=role_name,
        output_cv_filename=output_cv_filename,
        debug_mode=metadata.get("debug_mode", "false") == "true",
        skills_category_count=_resolve_skills_category_count(
            getattr(args, "skills_category_count", None),
            metadata_count=metadata.get("skills_category_count"),
        ),
    )
    _configure_cache_runtime_context(
        context,
        invalidate_cache=getattr(args, "invalidate_cache", False),
        force_knowledge_reupload=getattr(args, "force_knowledge_reupload", False),
    )
    final_state = await _run_graph(state, context)
    _print_status_summary(final_state, run_dir)
    _print_next_steps(final_state, run_dir)


def _handle_status(args: argparse.Namespace) -> None:
    run_dir, checkpoint_path = _resolve_run_checkpoint_pair(args)
    state = load_checkpoint(checkpoint_path)
    _print_status_summary(state, run_dir)
    _print_next_steps(state, run_dir)


async def _handle_regenerate(args: argparse.Namespace) -> None:
    run_dir, checkpoint_path = _resolve_run_checkpoint_pair(args)
    state = load_checkpoint(checkpoint_path)
    try:
        _ensure_regenerate_allowed(state)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    metadata = load_run_metadata(run_dir)
    role_name = _resolve_role_name_for_command(
        args.role,
        metadata_role=metadata.get("role_name"),
    )
    os.environ[ROLE_NAME_ENV] = role_name
    jd_path, jd_text = _load_existing_run_job_description(run_dir)
    try:
        sections = _parse_requested_sections(args.sections)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    try:
        note = _normalize_regeneration_note(args.note)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    _mark_sections_for_regeneration(state, sections, note)
    save_checkpoint(checkpoint_path, state)

    model_name = resolve_gemini_model_name(
        args.model,
        metadata_model=metadata.get("model_name"),
    )
    output_cv_filename = resolve_output_cv_filename(
        metadata_filename=metadata.get("output_cv_filename")
    )
    context = _prepare_runtime_context(
        run_dir=run_dir,
        company_name=metadata["company_name"],
        job_description_path=jd_path,
        job_description=jd_text,
        template_path=_resolve_template_path(
            explicit_template=None,
            metadata_template=metadata.get("template_path"),
            role_name=role_name,
        ),
        model_name=model_name,
        role_name=role_name,
        output_cv_filename=output_cv_filename,
        debug_mode=metadata.get("debug_mode", "false") == "true",
        skills_category_count=_resolve_skills_category_count(
            getattr(args, "skills_category_count", None),
            metadata_count=metadata.get("skills_category_count"),
        ),
    )
    _configure_cache_runtime_context(
        context,
        invalidate_cache=getattr(args, "invalidate_cache", False),
        force_knowledge_reupload=getattr(args, "force_knowledge_reupload", False),
    )
    final_state = await _run_graph(state, context)
    _print_status_summary(final_state, run_dir)
    _print_next_steps(final_state, run_dir)


async def _handle_rebuild_output(args: argparse.Namespace) -> None:
    run_dir, checkpoint_path = _resolve_run_checkpoint_pair(args)
    state = load_checkpoint(checkpoint_path)
    try:
        _ensure_rebuild_allowed(state)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if not _prepare_rebuild_from_completed_state(state):
        raise SystemExit("Rebuild aborted: missing approved content.")
    save_checkpoint(checkpoint_path, state)

    metadata = load_run_metadata(run_dir)
    role_name = _resolve_role_name_for_command(
        args.role,
        metadata_role=metadata.get("role_name"),
    )
    os.environ[ROLE_NAME_ENV] = role_name
    jd_path, jd_text = _load_existing_run_job_description(run_dir)
    context = _prepare_runtime_context(
        run_dir=run_dir,
        company_name=metadata["company_name"],
        job_description_path=jd_path,
        job_description=jd_text,
        template_path=_resolve_template_path(
            explicit_template=None,
            metadata_template=metadata.get("template_path"),
            role_name=role_name,
        ),
        model_name=resolve_gemini_model_name(
            explicit_model=None,
            metadata_model=metadata.get("model_name"),
        ),
        role_name=role_name,
        output_cv_filename=resolve_output_cv_filename(
            metadata_filename=metadata.get("output_cv_filename")
        ),
        debug_mode=metadata.get("debug_mode", "false") == "true",
        skills_category_count=_resolve_skills_category_count(
            explicit_count=None,
            metadata_count=metadata.get("skills_category_count"),
        ),
    )
    _configure_cache_runtime_context(
        context,
        invalidate_cache=False,
        force_knowledge_reupload=False,
    )
    final_state = await _run_graph(state, context)
    _print_status_summary(final_state, run_dir)
    _print_next_steps(final_state, run_dir)


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        if args.command == "run":
            asyncio.run(_handle_run(args))
            return
        if args.command == "resume":
            asyncio.run(_handle_resume(args))
            return
        if args.command == "status":
            _handle_status(args)
            return
        if args.command == "regenerate":
            asyncio.run(_handle_regenerate(args))
            return
        if args.command == "rebuild-output":
            asyncio.run(_handle_rebuild_output(args))
            return
        parser.error(f"Unknown command: {args.command}")
    except (
        CheckpointError,
        PromptValidationError,
        TemplateValidationError,
        KnowledgeCacheError,
    ) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
