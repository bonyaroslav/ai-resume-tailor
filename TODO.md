# TODO: `plan.md` Upgrade Checklist

## 1) Add Phase 0: Repo Safety and Scaffolding
- Add a first phase for repository safety before implementation work.
- Include privacy guardrails:
  - Ensure personal data handling is explicit.
  - Add/confirm `knowledge/` exclusion in `.gitignore`.
  - Add `knowledge/*.example.md` template strategy for shareable repo setup.
- Define initial module layout to match AGENTS guidance:
  - `main.py`
  - `llm_client.py`
  - `document_builder.py`
  - `retrospective_ui.py`
  - `prompt_loader.py`
  - `json_parser.py`
  - `workflow.py`

## 2) Replace Generic Prompt Ingestion With Frontmatter-Driven Loading
- Update plan steps to use Markdown prompts with YAML frontmatter.
- Explicitly parse `knowledge_files` from each prompt file.
- Load only referenced files per prompt for context isolation.
- Add fail-fast/error behavior for:
  - missing prompt files
  - malformed YAML frontmatter
  - missing referenced knowledge files

## 3) Make the Pipeline Explicitly Two-Stage With a Go Gate
- Stage 1 (Sequential): run `00_job_description_analysis.md` only.
- Display triage result and require explicit user decision to continue.
- Stage 2 (Parallel): run `01` to `06` concurrently with `asyncio` only when user enters "Go".
- Add retry/failure handling policy per section (continue vs abort).

## 4) Define Optional Stage 3: Post-Generation Critique Loop
- Clarify handling of `07_constructive_criticism.md`:
  - optional QA step after first draft selection, or
  - separate command/mode not in default pipeline.
- If included, define loop behavior:
  - critique -> user decision -> targeted regenerate.

## 5) Add a Strict Response Normalization + Validation Layer
- Add explicit step before `json.loads()`:
  - strip markdown code fences
  - trim stray leading/trailing text
  - sanitize common malformed JSON patterns
- Validate universal envelope for every prompt response:
  - root key: `variations`
  - each item includes: `id`, `score_0_to_5`, `ai_reasoning`, `content_for_template`
- Define graceful error behavior:
  - log malformed payload at `ERROR`
  - include payload snippet/context
  - allow section retry without crashing full workflow

## 6) Expand Human-in-the-Loop Retrospective Details
- Add concrete review UX flow:
  - show section name, variation id, score, reasoning, content
  - allow choose, edit, retry per section
- Log user final selection/edit decisions at `INFO`.
- Persist a final normalized "selected content" map for output assembly.

## 7) Split Output Strategy: CV Template vs Cover Letter
- Document that current DOCX template placeholders map only to:
  - `{{01_professional_summary}}`
  - `{{02_work_experience_1}}`
  - `{{03_work_experience_2}}`
  - `{{04_work_experience_3}}`
  - `{{05_skills_alignment}}`
- Add explicit plan rule for `06_cover_letter` output:
  - export as separate file (`.md`, `.txt`, or separate `.docx`) unless template is extended.
- State whether `07_constructive_criticism` is persisted and where.

## 8) Strengthen Observability in the Plan
- Keep dual logging target (console + local log file).
- Include concrete log events:
  - phase/stage start and completion
  - prompt load + knowledge files used
  - API request/response metadata
  - parse/validation failures with stack traces
  - final output file paths
- Define log redaction policy for sensitive data/API keys.

## 9) Add Deterministic Testing Phase to the Plan
- Add a dedicated test phase aligned with project rules:
  - JSON parser tests with dirty payload fixtures.
  - DOCX placeholder injection tests using dummy content.
  - Prompt frontmatter parser tests (`knowledge_files` extraction + failures).
  - Mapping tests for prompt filename -> output key -> placeholder.
- Keep explicit "no live LLM quality tests" rule.

## 10) Add Final Quality Gate Before Completion
- Run in this order:
  - `black .`
  - `ruff check . --fix`
  - `pytest`
- Add completion criteria to plan:
  - all required stages pass
  - selected content fully mapped
  - output files generated without modifying base template
  - errors are traceable via logs

## 11) Suggested `plan.md` Structure Rewrite (High Level)
- Phase 0: Repo Safety and Scaffolding
- Phase 1: Configuration and Logging Foundation
- Phase 2: Prompt and Context Ingestion (Frontmatter)
- Phase 3: AI Client + Response Normalization/Validation
- Phase 4: Orchestration (Stage 1 Triage, Stage 2 Parallel Generation)
- Phase 5: Human-in-the-Loop Retrospective and Selection
- Phase 6: Output Assembly (CV DOCX + Cover Letter Export)
- Phase 7: Tests, Lint, Format, Final Verification

