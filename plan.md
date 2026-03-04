## Implementation Plan: AI Resume Tailor

This plan defines the build sequence, safety controls, workflow gates, and verification criteria.

### Phase 0: Repo Safety and Scaffolding

Goal: establish privacy and module boundaries before implementation work.

1. Add and verify privacy guardrails for personal data in `knowledge/`.
2. Keep personal knowledge files out of version control using `knowledge/.gitignore`:
   - ignore `knowledge/*.md`
   - allow only `knowledge/*.example.md` templates for shareable setup
3. Document sensitive-data handling requirements:
   - do not log API keys or raw secrets
   - redact personally sensitive fields in logs when feasible
4. Define initial module layout and responsibilities:
   - `main.py`: CLI entrypoint and argument parsing
   - `workflow.py`: orchestration across all stages
   - `prompt_loader.py`: prompt + frontmatter loading, knowledge resolution
   - `llm_client.py`: Gemini API wrapper and async request execution
   - `json_parser.py`: response cleanup, normalization, and schema validation
   - `retrospective_ui.py`: Human-in-the-Loop review and user decisions
   - `document_builder.py`: DOCX placeholder replacement and export

### Phase 1: Configuration and Logging Foundation

Goal: ensure traceability and secure runtime configuration.

1. Implement environment/config loading for API credentials and runtime settings.
2. Define CLI input contract for Job Description ingestion:
   - user provides JD as a file path in console
   - accepted input file types: `.txt` and `.docx`
   - input may include links and all relevant context inline in the JD file
3. Implement dual logging sink:
   - console output for live workflow progress
   - local `.log` file for diagnostics and post-mortem analysis
4. Enforce log levels:
   - `INFO`: phase/stage start, completion, user decisions, output files
   - `DEBUG`: prompt metadata, referenced knowledge files, request/response metadata
   - `ERROR`: parse/validation failures with stack traces and payload snippets
5. Add log redaction policy:
   - never log API keys
   - mask or truncate sensitive user data and long freeform content
6. Define workflow run-folder convention for all artifacts:
   - create one folder per workflow run
   - folder name format: `YY.MM.DD Company` (example: `26.02.27 Microsoft`)
   - all generated outputs, logs, and saved responses for that run live in this folder

### Phase 2: Prompt and Context Ingestion (Frontmatter)

Goal: replace generic prompt loading with explicit frontmatter-driven context isolation.

1. Load prompts as Markdown files with YAML frontmatter.
2. Parse `knowledge_files` from each prompt frontmatter.
3. Load only files referenced by `knowledge_files` for that specific prompt.
4. Fail fast with actionable errors for:
   - missing prompt files
   - malformed YAML frontmatter
   - missing referenced knowledge files
5. Add mapping rules for prompt file -> output section key.

### Phase 3: AI Client and Response Normalization/Validation

Goal: make API interaction robust and deterministic even with malformed model output.

1. Implement async Gemini wrapper that returns raw response text plus metadata.
2. Normalize every model response before `json.loads()`:
   - strip markdown fences (for example ```json ... ```)
   - trim stray leading/trailing text around JSON
   - sanitize common malformed JSON patterns
3. Validate universal response envelope for every prompt:
   - root contains `variations`
   - each variation contains:
     - `id`
     - `score_0_to_5`
     - `ai_reasoning`
     - `content_for_template`
4. On malformed payload:
   - log parsing/validation failure at `ERROR` with traceback and snippet
   - return a controlled section-level failure object (no process crash)
   - allow targeted retry policy per section

### Phase 4: Orchestration With Stage Gates

Goal: implement explicit staged execution with a required user gate.

1. Stage 1 (sequential triage):
   - run only `00_job_description_analysis.md`
   - present formatted triage response in console (easy to scan and decide)
   - require explicit user input to continue
2. Gate behavior:
   - continue only when user enters exact confirmation (`Go`)
   - close workflow gracefully on any non-`Go` input
3. Stage 2 (parallel generation):
   - run `01` to `06` concurrently with `asyncio`
4. Failure policy for Stage 2:
   - parser/validation failure in one section does not automatically crash other sections
   - failed sections surface retry choice to user
   - define when to abort full pipeline (for example repeated hard failures)
5. Stage 3 (optional critique loop):
   - `07_constructive_criticism.md` is not required for default pipeline completion
   - support as optional post-generation QA mode:
     - user provides file path to the newly created CV
     - critique selected draft
     - user decides whether to apply critique
     - regenerate only targeted sections when requested
   - console should recognize critique/review request and route it to this mode

### Phase 5: Human-in-the-Loop Retrospective and Selection

Goal: provide explicit review UX for safe user-controlled final content.

1. For each section, display:
   - section name
   - variation id
   - score
   - ai reasoning
   - generated content
2. Allow user actions per section:
   - choose a variation
   - edit selected content
   - retry that section generation
3. Log final user decisions at `INFO`.
4. Persist normalized selected content map for downstream output assembly.
5. Persist every LLM response in readable files inside the run folder:
   - one file per prompt/stage
   - include raw text and normalized JSON for review/debugging

### Phase 6: Output Assembly (CV DOCX and Cover Letter Export)

Goal: produce deterministic artifacts while preserving the base template.

1. Map selected content to supported DOCX placeholders:
   - `{{01_professional_summary}}`
   - `{{02_work_experience_1}}`
   - `{{03_work_experience_2}}`
   - `{{04_work_experience_3}}`
   - `{{05_skills_alignment}}`
2. Export CV from template without modifying the original template file.
3. Handle `06_cover_letter` as separate output file (for example `.md`) unless template placeholders are extended.
4. Define persistence for critique output (`07_constructive_criticism`) when used:
   - store as optional QA artifact
   - do not inject into CV template placeholders
5. Log final output file paths at `INFO` and keep them inside the run folder.

### Phase 7: Tests, Lint, Format, Final Verification

Goal: enforce deterministic quality checks before completion.

1. Implement deterministic tests only (no live LLM quality assertions):
   - JSON parser tests with dirty payload fixtures
   - DOCX placeholder replacement tests with dummy strings
   - prompt frontmatter parser tests (`knowledge_files` success/failure)
   - mapping tests (prompt filename -> output key -> placeholder)
2. Run required quality gate commands in strict order:
   1. `black .`
   2. `ruff check . --fix`
   3. `pytest`
3. Completion criteria:
   - all required stages pass
   - selected content map is complete for expected sections
   - output files are generated successfully
   - base template remains unchanged
   - failures are traceable in logs with actionable context
