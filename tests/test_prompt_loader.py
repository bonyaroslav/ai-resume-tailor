from __future__ import annotations

from pathlib import Path

import pytest

from prompt_loader import PromptValidationError, discover_prompt_templates
from tests.test_support import make_workspace_temp_dir
from workflow_definition import WORKFLOW_SECTION_IDS


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_minimal_prompt_set(prompts_dir: Path) -> None:
    _write(prompts_dir / "triage_job_fit_and_risks.md", "Triage")
    _write(prompts_dir / "section_professional_summary.md", "Summary")
    _write(prompts_dir / "section_skills_alignment.md", "Skills")
    _write(prompts_dir / "section_experience_1_oldest.md", "Exp1")
    _write(prompts_dir / "section_experience_2_previous.md", "Exp2")
    _write(prompts_dir / "section_experience_3_latest.md", "Exp3")
    _write(prompts_dir / "doc_cover_letter.md", "Cover")


def test_discover_prompt_templates_with_frontmatter_knowledge_files() -> None:
    tmp_path = make_workspace_temp_dir("prompt-loader-success")
    prompts_dir = tmp_path / "prompts"
    knowledge_dir = tmp_path / "knowledge"
    _write_minimal_prompt_set(prompts_dir)
    _write(knowledge_dir / "skills.md", "python")
    _write(
        prompts_dir / "section_professional_summary.md",
        """---
knowledge_files:
  - "skills.md"
---
Summary prompt body
""",
    )

    templates = discover_prompt_templates(prompts_dir, knowledge_dir)
    assert tuple(templates.keys()) == WORKFLOW_SECTION_IDS
    assert (
        templates["section_professional_summary"].knowledge_files[0].name == "skills.md"
    )


def test_discover_prompt_templates_rejects_unsupported_frontmatter_keys() -> None:
    tmp_path = make_workspace_temp_dir("prompt-loader-unsupported")
    prompts_dir = tmp_path / "prompts"
    knowledge_dir = tmp_path / "knowledge"
    _write_minimal_prompt_set(prompts_dir)
    _write(
        prompts_dir / "section_professional_summary.md",
        """---
unsupported_key: "value"
---
Summary prompt body
""",
    )

    with pytest.raises(PromptValidationError):
        discover_prompt_templates(prompts_dir, knowledge_dir)


def test_discover_prompt_templates_fails_on_missing_knowledge_file() -> None:
    tmp_path = make_workspace_temp_dir("prompt-loader-missing-knowledge")
    prompts_dir = tmp_path / "prompts"
    knowledge_dir = tmp_path / "knowledge"
    _write_minimal_prompt_set(prompts_dir)
    _write(
        prompts_dir / "section_skills_alignment.md",
        """---
knowledge_files:
  - "missing.md"
---
Skills prompt body
""",
    )

    with pytest.raises(PromptValidationError):
        discover_prompt_templates(prompts_dir, knowledge_dir)


def test_discover_prompt_templates_fails_on_duplicate_normalized_experience_sections() -> (
    None
):
    tmp_path = make_workspace_temp_dir("prompt-loader-duplicate")
    prompts_dir = tmp_path / "prompts"
    knowledge_dir = tmp_path / "knowledge"
    _write(prompts_dir / "triage_job_fit_and_risks.md", "Triage")
    _write(prompts_dir / "section_professional_summary.md", "Summary")
    _write(prompts_dir / "section_skills_alignment.md", "Skills")
    _write(prompts_dir / "section_experience_1_oldest.md", "Exp1")
    _write(prompts_dir / "section_experience_1_latest.md", "Exp1 dup")
    _write(prompts_dir / "section_experience_2_previous.md", "Exp2")
    _write(prompts_dir / "section_experience_3_latest.md", "Exp3")
    _write(prompts_dir / "doc_cover_letter.md", "Cover")

    with pytest.raises(PromptValidationError):
        discover_prompt_templates(prompts_dir, knowledge_dir)


def test_discover_prompt_templates_rejects_example_only_files() -> None:
    tmp_path = make_workspace_temp_dir("prompt-loader-example-only")
    prompts_dir = tmp_path / "prompts"
    knowledge_dir = tmp_path / "knowledge"
    _write(prompts_dir / "triage_job_fit_and_risks.example.md", "Triage")
    _write(prompts_dir / "section_professional_summary.example.md", "Summary")
    _write(prompts_dir / "section_skills_alignment.example.md", "Skills")
    _write(prompts_dir / "section_experience_1_oldest.example.md", "Exp1")
    _write(prompts_dir / "section_experience_2_previous.example.md", "Exp2")
    _write(prompts_dir / "section_experience_3_latest.example.md", "Exp3")
    _write(prompts_dir / "doc_cover_letter.example.md", "Cover")

    with pytest.raises(PromptValidationError) as exc_info:
        discover_prompt_templates(prompts_dir, knowledge_dir)
    message = str(exc_info.value)
    assert "without '.example' suffix" in message
    assert "Create your own prompt files" in message
