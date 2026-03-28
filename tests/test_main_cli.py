from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

import pytest

from graph_state import GraphState, SectionState, Variation, create_initial_state
from main import (
    _configure_cache_runtime_context,
    _ensure_regenerate_allowed,
    _load_existing_run_job_description,
    _mark_sections_for_regeneration,
    _normalize_regeneration_note,
    _parse_requested_sections,
    _resolve_run_checkpoint_pair,
    _selected_variation_score,
)
from tests.test_support import make_workspace_temp_dir
from settings import DEFAULT_OUTPUT_CV_FILENAME, resolve_output_cv_filename


def test_parse_requested_sections_all() -> None:
    sections = _parse_requested_sections("all")
    assert "section_professional_summary" in sections
    assert "doc_cover_letter" in sections


def test_parse_requested_sections_deduplicates() -> None:
    sections = _parse_requested_sections(
        "section_professional_summary, section_professional_summary, doc_cover_letter"
    )
    assert sections == ["section_professional_summary", "doc_cover_letter"]


def test_parse_requested_sections_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        _parse_requested_sections("section_professional_summary,unknown_section")


def test_resolve_run_checkpoint_pair_from_run_path() -> None:
    args = argparse.Namespace(run_path=Path("runs/acme"), checkpoint_path=None)
    run_dir, checkpoint_path = _resolve_run_checkpoint_pair(args)
    assert run_dir == Path("runs/acme")
    assert checkpoint_path == Path("runs/acme/state_checkpoint.json")


def test_resolve_run_checkpoint_pair_from_checkpoint_path() -> None:
    args = argparse.Namespace(
        run_path=None, checkpoint_path=Path("runs/acme/state_checkpoint.json")
    )
    run_dir, checkpoint_path = _resolve_run_checkpoint_pair(args)
    assert run_dir == Path("runs/acme")
    assert checkpoint_path == Path("runs/acme/state_checkpoint.json")


def test_selected_variation_score_returns_score() -> None:
    section_state = SectionState(
        selected_variation_id="B",
        variations=[
            Variation(
                id="A",
                score_0_to_100=91,
                ai_reasoning="r1",
                content_for_template="c1",
            ),
            Variation(
                id="B",
                score_0_to_100=94,
                ai_reasoning="r2",
                content_for_template="c2",
            ),
        ],
    )
    assert _selected_variation_score(section_state) == 94


def test_selected_variation_score_returns_none_when_not_found() -> None:
    section_state = SectionState(
        selected_variation_id="Z",
        variations=[
            Variation(
                id="A",
                score_0_to_100=91,
                ai_reasoning="r1",
                content_for_template="c1",
            )
        ],
    )
    assert _selected_variation_score(section_state) is None


def test_normalize_regeneration_note_rejects_empty() -> None:
    with pytest.raises(ValueError):
        _normalize_regeneration_note("   ")


def test_normalize_regeneration_note_strips_value() -> None:
    assert _normalize_regeneration_note("  improve metrics  ") == "improve metrics"


def test_ensure_regenerate_allowed_rejects_non_completed() -> None:
    section_state = SectionState()
    state = GraphState(
        run_id="run-1",
        status="running",
        current_node="review",
        section_states={"section_professional_summary": section_state},
    )
    with pytest.raises(ValueError):
        _ensure_regenerate_allowed(state)


def test_ensure_regenerate_allowed_rejects_triage_stop() -> None:
    section_state = SectionState()
    state = GraphState(
        run_id="run-2",
        status="completed",
        current_node="triage_stop",
        section_states={"section_professional_summary": section_state},
    )
    with pytest.raises(ValueError):
        _ensure_regenerate_allowed(state)


def test_mark_sections_for_regeneration_preserves_ai_outputs() -> None:
    state = create_initial_state("run-regen")
    section_state = state.section_states["section_skills_alignment"]
    section_state.selected_variation_id = "A"
    section_state.selected_content = "Skills"
    section_state.variations = [
        Variation(
            id="A",
            score_0_to_100=97,
            ai_reasoning="best",
            content_for_template="Skills",
        )
    ]
    section_state.ai_outputs = [
        {
            "attempt": 1,
            "status": "parsed",
            "raw_response": "{}",
            "parsed_payload": {
                "meta": {
                    "jd_top_keywords": ["python"],
                    "covered_keywords": ["python"],
                    "missing_keywords_not_in_matrix": [],
                },
                "variations": [],
            },
            "normalized_payload": {"variations": []},
            "error_detail": None,
        }
    ]

    _mark_sections_for_regeneration(state, ["section_skills_alignment"], "retry")

    updated = state.section_states["section_skills_alignment"]
    assert updated.status == "retry_requested"
    assert updated.selected_content is None
    assert updated.variations == []
    assert len(updated.ai_outputs) == 1


def test_configure_cache_runtime_context_prefers_explicit_force_flag() -> None:
    context = argparse.Namespace(
        invalidate_role_wide_knowledge_cache=False,
        force_knowledge_reupload=False,
        knowledge_cache_ttl_seconds=0,
        knowledge_cache_registry_path=None,
    )

    _configure_cache_runtime_context(
        context,
        invalidate_cache=True,
        force_knowledge_reupload=True,
    )

    assert context.invalidate_role_wide_knowledge_cache is True
    assert context.force_knowledge_reupload is True


def test_load_existing_run_job_description_migrates_legacy_file() -> None:
    run_dir = make_workspace_temp_dir("legacy-jd-load")
    legacy_path = run_dir / "job_description.txt"
    legacy_path.write_text("Legacy job description", encoding="utf-8")

    jd_path, jd_text = _load_existing_run_job_description(run_dir)

    assert jd_path == run_dir / "job_description.md"
    assert jd_text == "Legacy job description"
    assert jd_path.read_text(encoding="utf-8") == "Legacy job description"


RUN_LOCAL_SCRIPT = Path("tools/run_local.ps1").resolve()


def _ps_string_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _write_fake_runner_project(tmp_dir: Path) -> tuple[Path, Path]:
    project_root = tmp_dir / "runner-project"
    project_root.mkdir(parents=True, exist_ok=False)
    log_path = project_root / "fake_python.log"

    fake_python_path = project_root / "fake_python.cmd"
    fake_python_path.write_text(
        "@echo off\n"
        'echo CALL:%*>>"%FAKE_PYTHON_LOG%"\n'
        'echo ART_OUTPUT_CV_FILENAME=%ART_OUTPUT_CV_FILENAME%>>"%FAKE_PYTHON_LOG%"\n'
        "exit /b 0\n",
        encoding="utf-8",
    )

    (project_root / "requirements.txt").write_text("", encoding="utf-8")
    (project_root / "main.py").write_text("print('stub')\n", encoding="utf-8")
    (project_root / "jd.md").write_text("Example JD\n", encoding="utf-8")
    secrets_dir = project_root / "secrets"
    secrets_dir.mkdir(parents=True, exist_ok=False)
    (secrets_dir / "gemini_api_key.txt").write_text("fake-key\n", encoding="utf-8")

    return project_root, log_path


def _write_runner_config(
    config_path: Path,
    *,
    project_root: Path,
    company_name: str,
    job_title: str,
    output_cv_file_name: str,
) -> None:
    config_path.write_text(
        "\n".join(
            [
                "$RunnerConfig = @{",
                f"    ProjectRoot = {_ps_string_literal(str(project_root))}",
                "    PythonExe = '.\\fake_python.cmd'",
                "    RequirementsFile = 'requirements.txt'",
                "    ApiKeyFile = '.\\secrets\\gemini_api_key.txt'",
                "    JobDescriptionPath = '.\\jd.md'",
                f"    CompanyName = {_ps_string_literal(company_name)}",
                f"    JobTitle = {_ps_string_literal(job_title)}",
                f"    OutputCvFileName = {_ps_string_literal(output_cv_file_name)}",
                "    TierName = 'test_tier'",
                "    InputProfile = 'role_engineer'",
                "    ModelName = ''",
                "    TierProfiles = @{",
                "        test_tier = @{",
                "            ModelName = 'gemini-2.5-flash'",
                "            GenerationMode = 'sequential'",
                "            MinIntervalSeconds = '0'",
                "            Max429Attempts = '1'",
                "            BackoffBaseSeconds = '1'",
                "        }",
                "    }",
                "    TemplatePath = ''",
                "    Debug = $false",
                "    RunHealthCheck = $false",
                "    UseRoleWideKnowledgeCache = $false",
                "    InvalidateRoleWideKnowledgeCache = $false",
                "    ForceKnowledgeReupload = $false",
                "    RequireCachedTokenConfirmation = $false",
                "    TriageDecisionMode = 'always_continue'",
                "    KnowledgeCacheTtlSeconds = 3600",
                "    KnowledgeCacheRegistryPath = '.\\runs\\_cache\\role_wide_knowledge_cache_registry.json'",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    ("output_cv_file_name", "company_name", "job_title", "expected_filename"),
    [
        ("custom.docx", "Acme", "Senior Engineer", "custom.docx"),
        ("custom", "Acme", "Senior Engineer", "custom.docx"),
        ("", "Acme", "Senior Engineer", "Acme - Senior Engineer.docx"),
        ("", "Acme", "", "Acme.docx"),
        ("", "Acme: Corp", "C#/.NET Lead.", "Acme_ Corp - C#_.NET Lead.docx"),
    ],
)
def test_run_local_resolves_output_cv_filename(
    output_cv_file_name: str,
    company_name: str,
    job_title: str,
    expected_filename: str,
) -> None:
    tmp_dir = make_workspace_temp_dir("run-local-ps1")
    project_root, log_path = _write_fake_runner_project(tmp_dir)
    config_path = tmp_dir / "RUNNER.config.ps1"
    _write_runner_config(
        config_path,
        project_root=project_root,
        company_name=company_name,
        job_title=job_title,
        output_cv_file_name=output_cv_file_name,
    )

    env = os.environ.copy()
    env["FAKE_PYTHON_LOG"] = str(log_path.resolve())

    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(RUN_LOCAL_SCRIPT),
            "-ConfigPath",
            str(config_path),
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    log_text = log_path.read_text(encoding="utf-8")
    assert f"ART_OUTPUT_CV_FILENAME={expected_filename}" in log_text


def test_direct_python_flow_keeps_default_output_filename(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ART_OUTPUT_CV_FILENAME", raising=False)
    assert resolve_output_cv_filename() == DEFAULT_OUTPUT_CV_FILENAME
