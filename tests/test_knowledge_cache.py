from __future__ import annotations

from pathlib import Path

from knowledge_cache import (
    compute_role_wide_knowledge_cache_fingerprint,
    discover_role_wide_knowledge_files,
)
from prompt_loader import PromptTemplate
from tests.test_support import make_workspace_temp_dir


def _template(
    section_id: str, body: str, knowledge_files: list[Path]
) -> PromptTemplate:
    return PromptTemplate(
        section_id=section_id,
        path=Path(f"prompts/{section_id}.md"),
        body=body,
        knowledge_files=knowledge_files,
    )


def test_discover_role_wide_knowledge_files_deduplicates_and_sorts() -> None:
    tmp_path = make_workspace_temp_dir("knowledge-cache-discovery")
    file_b = tmp_path / "b.md"
    file_a = tmp_path / "a.md"
    file_a.write_text("A", encoding="utf-8")
    file_b.write_text("B", encoding="utf-8")
    templates = {
        "section_professional_summary": _template(
            "section_professional_summary",
            "summary",
            [file_b, file_a],
        ),
        "section_skills_alignment": _template(
            "section_skills_alignment",
            "skills",
            [file_a],
        ),
    }

    discovered = discover_role_wide_knowledge_files(templates)

    assert [item.path.name for item in discovered] == ["a.md", "b.md"]


def test_cache_fingerprint_changes_when_knowledge_content_changes() -> None:
    tmp_path = make_workspace_temp_dir("knowledge-cache-fingerprint-content")
    knowledge_file = tmp_path / "rules.md"
    knowledge_file.write_text("first", encoding="utf-8")
    templates = {
        "section_professional_summary": _template(
            "section_professional_summary",
            "summary",
            [knowledge_file],
        )
    }

    first = compute_role_wide_knowledge_cache_fingerprint(
        role_name="role_a",
        model_name="gemini-test",
        knowledge_files=discover_role_wide_knowledge_files(templates),
    )
    knowledge_file.write_text("second", encoding="utf-8")
    second = compute_role_wide_knowledge_cache_fingerprint(
        role_name="role_a",
        model_name="gemini-test",
        knowledge_files=discover_role_wide_knowledge_files(templates),
    )

    assert first != second


def test_cache_fingerprint_does_not_change_when_prompt_body_changes_only() -> None:
    tmp_path = make_workspace_temp_dir("knowledge-cache-fingerprint-body")
    knowledge_file = tmp_path / "rules.md"
    knowledge_file.write_text("same", encoding="utf-8")
    first_templates = {
        "section_professional_summary": _template(
            "section_professional_summary",
            "first body",
            [knowledge_file],
        )
    }
    second_templates = {
        "section_professional_summary": _template(
            "section_professional_summary",
            "second body",
            [knowledge_file],
        )
    }

    first = compute_role_wide_knowledge_cache_fingerprint(
        role_name="role_a",
        model_name="gemini-test",
        knowledge_files=discover_role_wide_knowledge_files(first_templates),
    )
    second = compute_role_wide_knowledge_cache_fingerprint(
        role_name="role_a",
        model_name="gemini-test",
        knowledge_files=discover_role_wide_knowledge_files(second_templates),
    )

    assert first == second
