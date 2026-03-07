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

When starting the next implementation phase, keep focus on production hardening only:

1. Improve review UX without changing the review action contract.
2. Add state migration utility when `state_version` changes from `1.0`.
3. Add optional richer diagnostics around failure categories without logging raw sensitive content.

## Review UX subtasks (next)

1. Add a per-section review header in `graph_nodes.py` showing:
   - `section_id`
   - progress index/total
   - current `retry_count` and max retry limit
2. Strengthen action parsing for `choose/edit/retry/save_and_exit`:
   - support short aliases (`c/e/r/s`)
   - re-prompt with explicit valid options on invalid input
3. Improve variation selection validation:
   - show valid variation IDs before prompt
   - re-prompt when ID is missing/unknown
4. Improve `edit` flow safety:
   - keep default variation ID behavior
   - reject empty edited content with clear retry prompt
   - confirm final content was captured before marking approved
5. Add concise decision feedback after each section action:
   - approved variation ID
   - retry requested with updated retry count
   - save-and-exit checkpoint intent
6. Add deterministic tests for review UX behavior with mocked `input()`:
   - invalid action then valid action
   - alias actions path
   - invalid variation ID then valid ID
   - retry limit reached path
7. Run required quality gates and record evidence:
   - `black .`
   - `ruff check . --fix`
   - `pytest`
