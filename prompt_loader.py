from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from section_ids import canonical_section_id_from_prompt_path
from workflow_definition import WORKFLOW_SECTION_IDS

ALLOWED_FRONTMATTER_KEYS = {"knowledge_files"}


class PromptValidationError(ValueError):
    pass


@dataclass(frozen=True)
class PromptTemplate:
    section_id: str
    path: Path
    body: str
    knowledge_files: list[Path]


def _parse_frontmatter(markdown_text: str) -> tuple[dict[str, Any], str]:
    stripped = markdown_text.lstrip()
    if not stripped.startswith("---"):
        return {}, markdown_text

    lines = stripped.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, markdown_text

    end_index = -1
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break

    if end_index == -1:
        raise PromptValidationError("Invalid YAML frontmatter: missing closing '---'.")

    frontmatter_text = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :]).lstrip()

    try:
        parsed = yaml.safe_load(frontmatter_text) if frontmatter_text.strip() else {}
    except yaml.YAMLError as exc:
        raise PromptValidationError("Invalid YAML frontmatter syntax.") from exc

    if parsed is None:
        parsed = {}
    if not isinstance(parsed, dict):
        raise PromptValidationError("Prompt frontmatter must be a mapping.")
    return parsed, body


def _validate_frontmatter_and_resolve_context(
    frontmatter: dict[str, Any],
    knowledge_dir: Path,
) -> list[Path]:
    unsupported_keys = set(frontmatter) - ALLOWED_FRONTMATTER_KEYS
    if unsupported_keys:
        joined = ", ".join(sorted(unsupported_keys))
        raise PromptValidationError(f"Unsupported frontmatter keys: {joined}")

    raw_files = frontmatter.get("knowledge_files", [])
    if not isinstance(raw_files, list) or not all(
        isinstance(item, str) for item in raw_files
    ):
        raise PromptValidationError("'knowledge_files' must be a list of file names.")

    resolved_paths: list[Path] = []
    for filename in raw_files:
        candidate = (knowledge_dir / filename).resolve()
        if candidate.parent != knowledge_dir.resolve():
            raise PromptValidationError(f"Invalid knowledge file path: {filename}")
        if not candidate.exists():
            raise PromptValidationError(f"Missing knowledge file: {filename}")
        resolved_paths.append(candidate)
    return resolved_paths


def _is_example_prompt(path: Path) -> bool:
    return path.name.endswith(".example.md")


def discover_prompt_templates(
    prompts_dir: Path, knowledge_dir: Path
) -> dict[str, PromptTemplate]:
    raw_paths = sorted(prompts_dir.glob("*.md"))
    active: dict[str, Path] = {}
    examples: dict[str, list[Path]] = {}

    for path in raw_paths:
        section_id = canonical_section_id_from_prompt_path(path)
        if section_id not in WORKFLOW_SECTION_IDS:
            continue

        if _is_example_prompt(path):
            examples.setdefault(section_id, []).append(path)
            continue

        if section_id in active:
            raise PromptValidationError(
                f"Duplicate prompt files normalize to section_id '{section_id}'."
            )
        active[section_id] = path

    for section_id, candidates in examples.items():
        if section_id in active:
            continue
        if len(candidates) > 1:
            raise PromptValidationError(
                f"Duplicate example prompts normalize to section_id '{section_id}'."
            )
        active[section_id] = candidates[0]

    missing_sections = [
        section_id for section_id in WORKFLOW_SECTION_IDS if section_id not in active
    ]
    if missing_sections:
        missing = ", ".join(missing_sections)
        raise PromptValidationError(f"Missing prompt files for sections: {missing}")

    templates: dict[str, PromptTemplate] = {}
    for section_id in WORKFLOW_SECTION_IDS:
        path = active[section_id]
        text = path.read_text(encoding="utf-8")
        frontmatter, body = _parse_frontmatter(text)
        context_files = _validate_frontmatter_and_resolve_context(
            frontmatter, knowledge_dir
        )
        templates[section_id] = PromptTemplate(
            section_id=section_id,
            path=path,
            body=body,
            knowledge_files=context_files,
        )
    return templates


def inject_context(prompt: str, context_files: list[Path]) -> str:
    if not context_files:
        return prompt.strip()

    sections: list[str] = [prompt.strip(), "## Context Files"]
    for path in context_files:
        content = path.read_text(encoding="utf-8").strip()
        sections.append(f"### {path.name}\n{content}")
    return "\n\n".join(sections).strip()


def build_prompt_text(
    template: PromptTemplate,
    company_name: str,
    job_description: str,
    retry_note: str | None = None,
) -> str:
    prompt_with_context = inject_context(template.body, template.knowledge_files)
    runtime_fields = [
        "## Runtime Input",
        f"Company Name: {company_name}",
        "Job Description:",
        job_description,
    ]
    if retry_note:
        runtime_fields.extend(["", "## User Retry Note", retry_note])
    return "\n\n".join([prompt_with_context, "\n".join(runtime_fields)]).strip()
