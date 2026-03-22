# Refactor Plan 2 Implementation

## Summary
Use the balanced modularization direction, but keep the refactor behavior-preserving and flat.

Chosen decisions:
- Keep checkpoint schema unchanged in this pass: `state_version` stays `1.2`.
- Prioritize `main.py` and `graph_nodes.py` seams first.
- Split workflow code into exactly three phase modules.
- Add or preserve characterization coverage while moving code.

Target module shape:
- `main.py`: CLI parsing, command handlers, runtime loading, graph execution.
- `graph_generation.py`: `RuntimeContext`, triage generation, section generation, LLM pacing/request helpers, AI output bookkeeping.
- `graph_review.py`: review loop and choose/edit/retry/save-and-exit behavior.
- `graph_output.py`: assemble and audit nodes.
- `graph_nodes.py`: thin compatibility facade that re-exports workflow entrypoints.

## Implementation Changes
### 1. Stabilize behavior with tests first
- Lock command setup and execution paths for `run`, `resume`, `regenerate`, and `rebuild-output`.
- Lock `_run_graph(...)` happy path and stop/retry/review branches.
- Lock review UI actions and retry limits.
- Lock triage stop vs continue routing.
- Preserve current raw-response persistence behavior.

### 2. Refactor `main.py` into explicit runtime seams
- Centralize existing-run loading into one helper.
- Centralize repeated `RuntimeContext` construction into one helper.
- Keep `_handle_run(...)`, `_handle_resume(...)`, `_handle_regenerate(...)`, and `_handle_rebuild_output(...)` explicit and short.
- Preserve CLI flags, command names, and user-facing flow.

### 3. Split `graph_nodes.py` by workflow phase
`graph_generation.py`
- `RuntimeContext`
- triage helpers and `node_triage(...)`
- section generation helpers and `node_generate_sections(...)`
- LLM pacing/request functions
- AI output record creation and persistence helpers

`graph_review.py`
- review interaction helpers
- variation selection, edit, retry, save-and-exit logic
- `node_review(...)`

`graph_output.py`
- document assembly helpers and `node_assemble(...)`
- audit markdown normalization and `node_audit(...)`

### 4. Keep contract boundaries stable
- Leave `llm_client.py`, `json_parser.py`, and `graph_state.py` responsibilities intact.
- Only adjust imports needed by the workflow split.

## Interfaces and Constraints
- Public CLI remains unchanged.
- Checkpoint contract remains unchanged.
- Existing node names remain unchanged: `node_triage`, `node_generate_sections`, `node_review`, `node_assemble`, `node_audit`.
- Avoid registries, base classes, command frameworks, or generic workflow engines.

## Verification
- `black .`
- `ruff check . --fix`
- `pytest`
