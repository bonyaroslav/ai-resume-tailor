# Refactor Plan 3: Contract-First Cleanup

## Purpose
This plan treats LLM response contracts and persisted workflow state as the main architecture seams. It is best if the team expects prompt and schema evolution to continue.

## Problem Description
The application depends on strict section-specific JSON contracts, but the contract knowledge is currently distributed:

- JSON schema building lives in `llm_client.py`.
- Response cleaning and normalization live in `json_parser.py`.
- Validation models live in `graph_state.py`.
- Generation and triage nodes contain additional section-specific checks.

This makes the most change-prone part of the system harder to reason about. When prompts evolve, multiple files may need synchronized edits.

## Goals
- Establish one clear source of truth for section response contracts.
- Reduce contract drift between prompting, API schema configuration, parsing, and validation.
- Keep workflow orchestration simple and explicit.
- Make future prompt changes safer and easier to review.

## Scope
- Refactor around section contracts and state boundaries first.
- Leave most CLI and workflow control flow intact unless simplification naturally follows.
- Keep the solution functional and direct, not framework-oriented.

## Proposed Direction
### 1. Introduce a single contract definition module
- Define section-level expectations in one place:
  - response mode
  - schema shape
  - normalization strategy
  - post-parse invariants
- Use simple functions or plain dictionaries keyed by canonical `section_id`.

### 2. Separate transport from contract handling
- `llm_client.py` should request content, handle retries, and surface transport errors.
- Contract details should be delegated to the contract layer.
- `json_parser.py` should become a narrow parsing and cleaning utility plus contract-driven normalization entrypoint.

### 3. Make state persistence match resumable needs exactly
- Review `GraphState` and checkpoint payload contents against `AGENTS.md`.
- Remove non-essential raw payload persistence from the normal path.
- Keep schema migrations small and explicit when state changes.

### 4. Reduce section-specific branching in nodes
- Replace scattered one-off checks with contract-driven validation where practical.
- Keep only truly workflow-related decisions inside node functions.

## Benefits
- Prompt updates become easier to implement safely.
- Reviewers can inspect schema-impacting changes in one place.
- The most AI-specific part of the system becomes clearer to AI engineers reviewing the code.

## Non-Goals
- No multi-provider architecture.
- No autonomous rewrite loop design.
- No generic plugin system for sections.

## Expected Outcome
- The code reflects a clearer architecture: workflow state, transport, contract, and UI each have a defined role.
- AI-facing behavior becomes easier to modify without hidden coupling.
- The repo still stays small and readable.

## Risks
- Contract centralization can be overdone if it turns into a mini framework.
- Some duplication may remain preferable when it keeps section behavior explicit.

## Suggested Review Questions
- Which contract rules truly belong in one source of truth?
- Which section-specific quirks are acceptable to keep explicit in node code?
- How much contract centralization improves clarity before it starts to feel abstract?
