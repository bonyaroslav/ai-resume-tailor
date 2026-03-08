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
    node_assemble,
    node_generate_sections,
    node_review,
    node_triage,
)
from graph_router import route_next_node
from graph_state import GraphState, create_initial_state, touch_state
from job_description_loader import read_job_description
from logging_utils import configure_logging, log_failure, sha256_short
from prompt_loader import PromptValidationError, discover_prompt_templates
from run_artifacts import create_run_directory, load_run_metadata, write_run_metadata
from workflow_definition import TEMPLATE_SECTION_IDS

DEFAULT_TEMPLATE_PATH = "knowledge/Default Template - Senior Software Engineer.docx"
DEFAULT_MODEL = "gemini-2.5-flash"
AUTO_APPROVE_REVIEW_ENV = "ART_AUTO_APPROVE_REVIEW"
OFFLINE_MODE_ENV = "ART_OFFLINE_MODE"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI Resume Tailor")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Start a new run")
    run_parser.add_argument("--jd-path", required=True, type=Path)
    run_parser.add_argument("--company", required=True)
    run_parser.add_argument(
        "--template-path", type=Path, default=Path(DEFAULT_TEMPLATE_PATH)
    )
    run_parser.add_argument("--model", default=None)
    run_parser.add_argument("--debug", action="store_true")

    resume_parser = subparsers.add_parser("resume", help="Resume from checkpoint")
    resume_group = resume_parser.add_mutually_exclusive_group(required=True)
    resume_group.add_argument("--run-path", type=Path)
    resume_group.add_argument("--checkpoint-path", type=Path)
    resume_parser.add_argument("--model", default=None)

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


def _job_description_preview(job_description: str, *, max_lines: int = 3) -> str:
    lines = [line.strip() for line in job_description.splitlines() if line.strip()]
    if not lines:
        return "-"
    preview = " | ".join(lines[:max_lines]).strip()
    if len(lines) > max_lines:
        return f"{preview} | ..."
    return preview


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


async def _run_graph(state: GraphState, context: RuntimeContext) -> GraphState:
    logger = configure_logging(context.run_dir, context.debug_mode)
    logger.info("Run started. run_id=%s, model=%s", state.run_id, context.model_name)
    logger.info(
        "Loaded JD metadata (chars=%s, sha256=%s)",
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
    job_description: str,
    template_path: Path,
    model_name: str,
    debug_mode: bool,
) -> RuntimeContext:
    prompts_dir = Path("prompts")
    knowledge_dir = Path("knowledge")
    prompt_templates = discover_prompt_templates(prompts_dir, knowledge_dir)
    preflight_template(template_path, TEMPLATE_SECTION_IDS)

    checkpoint_path = run_dir / "state_checkpoint.json"
    return RuntimeContext(
        run_dir=run_dir,
        checkpoint_path=checkpoint_path,
        template_path=template_path,
        output_cv_path=run_dir / "tailored_cv.docx",
        output_cover_letter_path=run_dir / "cover_letter.txt",
        company_name=company_name,
        job_description=job_description,
        api_key=_load_api_key(),
        model_name=model_name,
        prompt_templates=prompt_templates,
        debug_mode=debug_mode,
        auto_approve_review=_is_truthy_env(os.getenv(AUTO_APPROVE_REVIEW_ENV)),
    )


async def _handle_run(args: argparse.Namespace) -> None:
    run_dir = create_run_directory(Path("runs"), args.company)
    jd_text = read_job_description(args.jd_path)
    (run_dir / "job_description.txt").write_text(jd_text, encoding="utf-8")

    model_name = args.model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    context = _prepare_runtime_context(
        run_dir=run_dir,
        company_name=args.company,
        job_description=jd_text,
        template_path=args.template_path,
        model_name=model_name,
        debug_mode=bool(args.debug),
    )

    write_run_metadata(
        run_dir,
        {
            "run_id": run_dir.name,
            "company_name": args.company,
            "template_path": str(args.template_path),
            "model_name": model_name,
            "debug_mode": str(bool(args.debug)).lower(),
        },
    )

    state = create_initial_state(run_id=run_dir.name)
    save_checkpoint(context.checkpoint_path, state)
    await _run_graph(state, context)


async def _handle_resume(args: argparse.Namespace) -> None:
    if args.checkpoint_path:
        checkpoint_path = args.checkpoint_path
        run_dir = checkpoint_path.parent
    else:
        run_dir = args.run_path
        checkpoint_path = run_dir / "state_checkpoint.json"

    state = load_checkpoint(checkpoint_path)
    metadata = load_run_metadata(run_dir)
    jd_text = (run_dir / "job_description.txt").read_text(encoding="utf-8")

    model_name = args.model or metadata.get("model_name", DEFAULT_MODEL)
    context = _prepare_runtime_context(
        run_dir=run_dir,
        company_name=metadata["company_name"],
        job_description=jd_text,
        template_path=Path(metadata["template_path"]),
        model_name=model_name,
        debug_mode=metadata.get("debug_mode", "false") == "true",
    )
    await _run_graph(state, context)


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
        parser.error(f"Unknown command: {args.command}")
    except (CheckpointError, PromptValidationError, TemplateValidationError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
