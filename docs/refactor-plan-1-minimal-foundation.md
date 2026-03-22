# Refactor Plan 1: Minimal Foundation, Detailed

## Summary
This first refactor pass will stay conservative: preserve current runtime behavior, keep the repo mostly flat, and focus on three high-value seams only.

Chosen architectural direction:

- Keep `main.py` and `graph_nodes.py` as the primary entrypoint files in pass 1.
- Allow one small supporting module only if it materially reduces duplication without scattering logic.
- Do not change the checkpoint schema in pass 1.
- Enforce the new privacy rule in normal runs by omitting true raw payloads and storing a sentinel string in checkpoint `raw_response`.
- Add characterization tests before moving logic so the refactor is behavior-preserving.

Recommendation:

- This is the right first pass for the repo. It improves readability and policy compliance without creating a "half-architecture" that is bigger than the problem.
- I do not recommend splitting into several workflow modules yet. The codebase is not large enough to justify that in pass 1, and the current tests are stronger at the behavior level than at the seam level.

Tradeoffs:

- Pro: lowest regression risk, easiest review, minimal file growth, aligned with AGENTS minimalism.
- Pro: creates clean follow-up seams for a second pass if you later want a phase-based split.
- Con: `main.py` and `graph_nodes.py` will still remain somewhat large after pass 1.
- Con: because checkpoint schema stays unchanged, privacy cleanup is intentionally partial: the raw field remains structurally present, but real raw text is removed from non-debug checkpoints via sentinel content instead of a true schema removal.

## Architectural Decisions
### 1. Command architecture
Keep explicit command handlers in `main.py`. Do not introduce a command framework, registry, or generic dispatcher.

Implementation direction:

- Extract shared command preparation into one narrow runtime-loading seam.
- Each command handler remains explicit and short.
- Shared responsibilities to centralize:
  - resolve run/checkpoint paths
  - load metadata
  - resolve `input_profile`
  - load/persist job description
  - resolve model/template/output filename
  - build `RuntimeContext`
  - apply cache-related runtime flags

Result:

- `run`, `resume`, `regenerate`, and `rebuild-output` still read clearly as top-level workflows.
- The duplicated setup code moves behind one or two focused helpers instead of many ad hoc private functions.

### 2. Workflow node architecture
Keep `node_triage`, `node_generate_sections`, `node_review`, `node_assemble`, and `node_audit` as explicit functions. Do not split into multiple files in pass 1 unless one tiny helper module becomes necessary for privacy/artifact handling.

Implementation direction:

- Keep node entrypoints where they are.
- Extract only repeated or mixed-responsibility private helpers:
  - response persistence and AI output record creation
  - generation-result parsing/validation bookkeeping
  - review queue calculation and completion checks
- Do not move review UI semantics out into a generic interface.

Result:

- The workflow remains easy to scan from one file.
- Internal complexity is reduced without increasing navigation overhead.

### 3. Privacy boundary
Normal non-debug runs must not persist real raw LLM payloads.

Implementation direction:

- Response artifact files under `runs/.../responses` become debug-only.
- `AiOutputRecord.raw_response` remains required in pass 1 for compatibility, but non-debug runs store a constant sentinel such as `[omitted_non_debug]`.
- Parsed and normalized payloads remain stored only where they are already needed for resumability and tests.
- Debug mode continues to keep the current richer diagnostics.

Result:

- Pass 1 becomes materially closer to AGENTS privacy expectations without requiring a checkpoint version bump.

## Implementation Changes
### Main workflow cleanup
Refactor `main.py` around three behavior-level helpers:

- `load_command_runtime(...)`
  - returns resolved run directory, checkpoint path, metadata, JD path/text, and resolved runtime options
- `build_runtime_context(...)`
  - wraps the current context construction and template/prompt discovery
- `execute_graph_command(...)`
  - runs `_run_graph(...)` and prints final status/next steps

Command handler targets:

- `_handle_run(...)` keeps unique "new run" behavior only.
- `_handle_resume(...)`, `_handle_regenerate(...)`, and `_handle_rebuild_output(...)` become thin wrappers over shared loading/setup.
- `_handle_status(...)` remains separate and simple.

Acceptance target:

- Command handlers become short enough that their unique behavior is obvious in one screenful.
- No command behavior, CLI flags, or user-facing messages change unless needed for privacy messaging.

### Graph/node cleanup
Refactor `graph_nodes.py` around two narrow seams.

Seam A: response persistence and bookkeeping

- Centralize:
  - whether raw response files are written
  - what `raw_response` value is stored in `AiOutputRecord`
  - appending records and setting parse/schema failure metadata
- Keep the node code focused on workflow decisions.

Seam B: generation/review flow helpers

- Extract helper(s) for:
  - target section selection for generation
  - post-generation state update
  - review queue recomputation
  - approval-completion checks

Acceptance target:

- `_generate_section_variations(...)` and `node_review(...)` become shorter and easier to reason about.
- No changes to selection rules, retry limits, or review prompts.

### Checkpoint/privacy compatibility
Keep current state version and model shape in pass 1.

Implementation direction:

- No `state_version` bump.
- No migration changes.
- Update save-time behavior so non-debug runs write compatibility-safe sentinel content instead of real raw payload text.
- Preserve existing ability to load old checkpoints.

Acceptance target:

- Existing checkpoints continue to load.
- New normal-mode checkpoints stop carrying real raw LLM text.
- Debug-mode checkpoints preserve current troubleshooting value.

## Public Types and Interfaces
No user-facing CLI interface changes are planned.

Internal behavior changes to lock:

- `AiOutputRecord.raw_response` remains present in pass 1, but may contain sentinel text in non-debug runs.
- Response artifact directory creation becomes conditional on debug mode.
- Existing command handlers remain named and callable as they are now.

## Test Plan
### Characterization tests to add before refactor
Add or extend tests to lock current behavior before moving logic:

- command setup path for `resume`, `regenerate`, and `rebuild-output`
- `_run_graph(...)` end-to-end completion with mocked LLM and checkpoint persistence
- review queue and retry path behavior

### New tests required for pass 1
Privacy tests:

- non-debug run does not create raw response files
- debug run still creates raw response files
- non-debug checkpoint stores sentinel `raw_response`, not the real payload
- debug checkpoint stores the real payload
- old checkpoints with real raw payloads still load unchanged

Main orchestration tests:

- shared runtime-loading helper preserves current metadata/input-profile/model/template resolution
- each command handler still triggers the same workflow path and same user-facing exit/error behavior
- `run` still persists JD and metadata correctly
- `resume` still loads the existing JD correctly, including legacy fallback path

Graph behavior tests:

- generation success path still records parsed and normalized payloads
- parse/schema failure paths still populate `error_detail` and status correctly
- review flow still supports choose/edit/retry/save-and-exit exactly as before

Regression suite to run after implementation:

- `python -m pytest`
- `black --check .`
- `ruff check .`

### Test acceptance rule
No refactor step should remove an existing passing behavioral test without replacing it with an equally strong or better one. For this pass, tests are the safety rail and should be expanded before any meaningful function movement.

## Assumptions and Defaults
- "Whatever is needed" for structure is interpreted as: allow modest helper extraction, but avoid multi-file decomposition unless clearly necessary.
- "Do not change checkpoint schema yet" is taken as a hard constraint for pass 1.
- The accepted temporary privacy compromise is sentinel `raw_response` content in non-debug checkpoints.
- Follow-up refactor pass can revisit a true checkpoint schema cleanup with a `state_version` bump once pass 1 is stable.

## Recommendation
Implement this pass exactly as above.

Reason:

- It solves the most important issue first, privacy behavior, while reducing duplication in `main.py` and mixed responsibilities in `graph_nodes.py`.
- It stays aligned with the repo's stated values: readable, minimal, easy to support, no excessive files, no premature abstractions.
- It creates a clean baseline for a later second pass if you decide the remaining file sizes still justify a phase-based split.
