# Implementation Plan Status

This plan is now aligned to the implemented V1 baseline and TODO decisions.

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
