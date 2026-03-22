# Refactor Plan 2: Balanced Modularization

## Purpose
This plan aims for a stronger structural cleanup while staying aligned with the project's minimalist style. It is intended to improve readability for collaborators without turning the codebase into a framework.

## Problem Description
The application currently has good functional coverage, but its orchestration logic is concentrated in a few oversized files. This creates support friction:

- Contributors need to read large files before making even small changes.
- Related workflow concerns are grouped by historical growth, not by responsibility.
- Some behaviors are duplicated across command handlers and section-processing paths.
- The boundary between workflow policy, UI interaction, and LLM contract handling is not sharp enough.

## Goals
- Make the workflow easier to understand by separating phases cleanly.
- Keep the number of files low and the directory structure flat.
- Reduce repeated code paths in command handling and node execution.
- Make section-specific logic easier to modify safely.
- Preserve explicit control flow and avoid over-abstraction.

## Scope
- Moderate refactor of workflow modules.
- Reorganization by phase, not by technical pattern.
- No behavior redesign unless needed to simplify the structure.

## Proposed Direction
### 1. Split workflow execution by phase
- Keep `graph_router.py` and `graph_state.py` as simple central pieces.
- Split `graph_nodes.py` into a small number of focused modules, for example:
  - `graph_generation.py`
  - `graph_review.py`
  - `graph_output.py`
- Retain explicit `node_*` functions rather than introducing dispatch classes.

### 2. Create a small runtime-loading seam in `main.py`
- Centralize repeated steps for:
  - resolving run and checkpoint paths
  - loading run metadata
  - resolving input profile and model
  - loading the job description
  - creating `RuntimeContext`
- Keep each command handler thin and explicit.

### 3. Separate section contract logic from transport logic
- Move section-specific schema definitions and normalization rules closer together.
- Let `llm_client.py` focus on transport, retries, and API errors.
- Let parser/contract code focus on cleaning, validating, and normalizing responses.

### 4. Tighten artifact boundaries
- Treat checkpoints, response artifacts, and logs as separate concerns.
- Make debug artifacts opt-in.
- Keep persisted state aligned with the resumable state contract in `AGENTS.md`.

## Candidate Target Layout
- `main.py`
- `graph_state.py`
- `graph_router.py`
- `graph_generation.py`
- `graph_review.py`
- `graph_output.py`
- `llm_client.py`
- `response_contracts.py`
- `json_parser.py`

## Non-Goals
- No dependency injection container.
- No provider registry.
- No event bus.
- No generic orchestration engine.

## Expected Outcome
- New contributors can understand the application by reading smaller, phase-oriented modules.
- Workflow changes become easier to localize.
- The codebase stays compact enough to support quickly.

## Risks
- A moderate refactor can create temporary churn in tests and imports.
- Splitting files too aggressively would work against the project's stated preferences.

## Suggested Review Questions
- Which workflow phase boundaries feel natural to current contributors?
- Would three focused workflow modules improve readability, or is two enough?
- Which responsibilities still belong together because they change together?
