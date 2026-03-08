# Implementation Plan Status

This plan is now aligned to the implemented V1 baseline and TODO decisions.

## Next Phase: Auto-First Flow + 0-100 Scoring (Decisions Locked)

Goal: minimize human interaction to one triage decision, complete generation automatically, then support targeted regeneration/rebuild at any later time for the same company run.

### Architecture Rule (Locked)

Use exactly one persisted workflow state source:

1. Canonical persisted state: `state_checkpoint.json` only.
2. No second persisted decision state/file as workflow input.
3. Any summary/report must be derived from checkpoint + logs and treated as disposable output.

### Product Behavior Targets

1. Human gate only at triage
   - Show triage analysis and recommendation.
   - User chooses `continue` or `stop`.
2. Full auto after triage continue
   - Generate all sections.
   - Auto-select highest-scored variation per section.
   - Assemble CV DOCX + cover letter automatically.
3. Post-completion lifecycle
   - Re-open same company run days later.
   - Regenerate selected section(s) with explicit user note.
   - Rebuild outputs with updated approved content.
4. Auditability
   - Log decisions, scores, selected variation IDs, rejected alternatives.
   - Keep checkpoint resumability and deterministic run artifacts under `runs/`.

### Implementation Steps

1. Prompt and scoring contract migration
   - Prompt schema changed to `score_0_to_100`.
   - Enforce distinct ranking instructions (no ties, minimum score gap, sorted high->low).
   - Update all prompt files under `prompts/` and examples.
2. Runtime schema migration
   - Update envelope validation models/parser/client schema from `score_0_to_5` to `score_0_to_100`.
   - Add deterministic tie-break guard if model still returns duplicate scores.
   - Keep parser defensive behavior for malformed JSON wrappers.
3. Review mode defaults
   - Add explicit review mode control (`auto` default, `manual` optional).
   - In auto mode, skip interactive per-section review.
   - Keep triage confirmation interactive by default.
4. Automatic best-variation selection
   - Select max score per section in auto mode.
   - Persist selected variation and metadata in checkpoint state.
   - Log concise decision lines for each section.
5. Regeneration after completion
   - Preserve and polish existing completed-run actions:
     - regenerate specific sections
     - inject user comment into prompt (`retry_note`)
     - rebuild outputs
   - Ensure completed runs remain re-openable without creating new run folder.
6. Derived status/report view (non-authoritative)
   - Add a status view/command that reads checkpoint and logs.
   - Print triage decision, selected variation IDs/scores, pending/retry sections.
   - Optional export is allowed, but must be regenerated and never read by workflow logic.
7. Validation and docs
   - Update tests for schema migration and auto review flow.
   - Update README/RUNBOOK usage with triage-first + auto-run + regenerate-later path.
   - Run `black .`, `ruff check . --fix`, `pytest`.

### Risks and Mitigations

1. Risk: prompt/schema mismatch during migration
   - Mitigation: migrate prompt + parser + model + tests in one change set.
2. Risk: model still outputs tied scores
   - Mitigation: deterministic runtime tie-break + warning log.
3. Risk: reduced human quality control
   - Mitigation: strong audit logs + easy regenerate/rebuild loop.
4. Risk: dual source of truth drift
   - Mitigation: keep checkpoint as the only persisted workflow authority.

## Completed

1. Locked canonical `section_id` strategy and workflow inventory.
2. Implemented minimal `GraphState` + checkpoint contract (`state_version=1.0`).
3. Implemented explicit router (`if/elif`) and node flow:
   - triage
   - concurrent generation
   - review (HITL)
   - assembly
4. Implemented review contract:
   - per-section: choose/edit/retry
   - global: save_and_exit
5. Implemented frontmatter/prompt contract:
   - markdown + optional YAML
   - only `knowledge_files`
   - strict validation
6. Implemented LLM envelope parsing with defensive cleanup and schema validation.
7. Implemented retry strategy:
   - one automatic parse/schema retry
   - max two user retries per section with note injection
8. Implemented template preflight and DOCX output assembly with canonical placeholder matching.
9. Implemented run artifact structure under `runs/` with metadata, logs, checkpoint, outputs.
10. Added deterministic tests for parser, prompt loading, routing, mapping, and DOCX handling.
11. Ran required quality gates:
    - `black .`
    - `ruff check . --fix`
    - `pytest`
12. Added targeted integration coverage with mocked LLM responses:
    - end-to-end graph run (`triage -> generate -> review -> assemble`)
    - deterministic review selection path without live API calls
13. Improved review UX without changing action contract:
    - per-section progress/retry header
    - action aliases (`c/e/r/s`) and explicit invalid-action re-prompt
    - variation ID validation with re-prompt and valid-ID hint
    - safer edit/retry feedback and save-and-exit checkpoint feedback
    - deterministic review UX tests with mocked input paths
14. Added MVP offline execution support and fixed prompt/knowledge alignment:
    - moved default template under `knowledge/` and updated default CLI path
    - added offline LLM emulation mode via deterministic fixture envelopes
    - added offline auto-approve review mode for unattended smoke runs
    - added CLI-level offline E2E test validating logs/checkpoint/docx/txt outputs
    - fixed prompt example frontmatter references to existing `knowledge/` files
15. Executed offline CLI smoke run (non-test) and validated generated run artifacts:
    - `run.log`, `state_checkpoint.json`, `tailored_cv.docx`, `cover_letter.txt`
    - status reached `completed` in runtime logs
16. Added extension-based JD ingestion for `.txt` and `.docx`:
    - extracted `.docx` paragraph and table content for runtime input
    - added deterministic tests for supported and unsupported extensions

## Current module map

- `main.py`: CLI `run`/`resume`, run bootstrap, graph execution loop
- `graph_state.py`: state/envelope models, state versioning helpers
- `checkpoint.py`: atomic checkpoint persistence and strict load validation
- `workflow_definition.py`: locked section inventory
- `section_ids.py`: canonical ID normalization
- `prompt_loader.py`: prompt discovery, frontmatter validation, `inject_context`
- `json_parser.py`: envelope cleanup and validation
- `llm_client.py`: Gemini-only client path (V1)
- `graph_router.py`: explicit routing
- `graph_nodes.py`: triage/generation/review/assembly nodes
- `document_builder.py`: template preflight + replacement + cover-letter export
- `logging_utils.py`: console/file logging + redaction helpers
- `run_artifacts.py`: run-folder naming and metadata persistence

## Next plan.md execution scope

When starting the next implementation phase, keep focus on MVP execution readiness:

1. Move default template into `knowledge/` and update default CLI path.
2. Add an offline emulation run mode for deterministic end-to-end execution.
3. Add a non-interactive review mode for offline smoke runs only.
4. Add one offline E2E test that validates run logs, checkpoint, CV DOCX, and cover letter outputs.
5. Run one real Gemini smoke run and capture concise run notes for prompt tuning.

## Actionable subtasks

1. Template path alignment
   - Move `Default Template - Senior Software Engineer.docx` to `knowledge/`.
   - Update `DEFAULT_TEMPLATE_PATH` and README examples.
   - Verify `run` works without `--template-path`.
2. Offline emulation mode
   - Add one explicit toggle (env var or CLI flag) to bypass network Gemini calls.
   - Load deterministic section responses from a local fixture file.
   - Keep the same universal envelope schema as production.
3. Offline review shortcut
   - Add one explicit toggle to auto-choose variation `A` for every section.
   - Keep current HITL behavior as default.
4. Offline E2E validation
   - Execute full graph offline against real prompts/knowledge files.
   - Assert output artifacts exist and placeholders are replaced.
   - Assert logs/checkpoint show `completed` status.
5. Real Gemini smoke run
   - Run a single real JD through AI Studio key flow.
   - Record only metadata findings (no raw sensitive content).
6. Quality gate and plan update
   - Run `black .`, `ruff check . --fix`, `pytest`.
   - Mark completed items and unresolved blockers in this plan.

## Gap handling policy (flexible by design)

1. If a blocker appears, add it under a `Gaps Found` section with:
   - impact (`blocker|high|medium|low`)
   - affected module
   - smallest viable fix
2. If the fix is small and local, implement it in the same cycle.
3. If the fix is broad, defer it with a one-line rationale and continue MVP path.
4. Do not add abstractions or new architecture unless a real blocker requires it.

## Gaps Found

1. impact: blocker
   affected module: `prompts/*.example.md`
   smallest viable fix: align `knowledge_files` entries to existing `knowledge/accomplishments_work_*.md` files
   status: fixed

## Next Phase: Resume-First UX And Run Reuse

Goal: make human interaction explicit, resumable, and actionable without forcing users to restart or guess next commands.

### Decisions Required Before Implementation

1. Folder naming + reuse policy
   - Option A: one stable folder per company slug (example: `runs/mindera`)
   - Option B: dated folder naming, but always reuse the latest matching run for that company
2. Behavior when `run` finds an existing completed run
   - Option A: show summary and prompt user: `resume / view outputs / start fresh`
   - Option B: do nothing unless an explicit `--force-new` flag is passed
3. Control surface for post-run operations
   - Option A: add explicit commands (`status`, `regenerate`, `rebuild-output`)
   - Option B: keep existing commands and print instructions only
4. History policy inside reused run folders
   - Option A: single current checkpoint/state only
   - Option B: keep lightweight snapshots/backups per major transition

### Step-By-Step Implementation Plan

1. Run discovery and state summary
   - On `run`, detect existing run folder for the selected company.
   - If found, load checkpoint and print concise stage status:
     - triage
     - generation
     - review
     - assembly
     - current node + overall status
2. Human guidance at every interaction point
   - Add concise "What you can do next" output for:
     - triage stop
     - awaiting review
     - retry requested
     - failed state
     - completed state
   - Include exact next command examples.
3. Remove forced incremental run folder suffixing
   - Replace incremented naming behavior with run reuse behavior per chosen decision.
   - Keep ability to create a separate run by using a unique company name/suffix.
4. Resume current JD flow by default
   - Make resume path first-class when existing state is detected.
   - Avoid overwriting progress silently.
5. Post-run operation support
   - Implement selected approach:
     - explicit subcommands (`status`, `regenerate`, `rebuild-output`), or
     - instruction-only guidance with current command surface.
6. Regeneration and output guidance
   - Ensure user is told:
     - how to regenerate specific section(s)
     - how to rebuild/reprint cover letter and CV outputs
     - how to continue from checkpoint.
7. Tests and docs
   - Add/adjust tests for:
     - existing run detection and summary rendering
     - run reuse behavior (no auto increment)
     - guidance output coverage per major state
   - Update `README.md` and `RUNBOOK_SETUP.md` with the final UX flow.
8. Quality gate
   - Run `black .`
   - Run `ruff check . --fix`
   - Run `pytest`

### Acceptance Criteria

1. User always sees clear next-step instructions at every human-interaction checkpoint.
2. Existing run folders are detected and state is summarized before actions proceed.
3. Users can continue current JD processing without manually hunting for run/checkpoint paths.
4. Auto-increment folder strategy is removed in favor of explicit reuse policy.
5. Documentation matches implemented CLI behavior.
