# Implementation Plan: Triage Single-Result Contract + Console Output Redesign

## Objective

Implement a stable triage decision contract with a single JSON result (no `variations`) and redesign console output so prompts/responses are readable and not duplicated-looking.

## Decisions Locked

1. `triage_job_fit_and_risks` returns one JSON object under `triage_result`.
2. Experience sections (`section_experience_*`) keep the bullets schema already adopted.
3. Non-experience generation sections (except triage) keep the existing `variations` envelope.
4. Prompt display in console should show only first 5 lines and a truncation notice.
5. Triage response display should be compact by default (preview, not full raw dump).

## No-Conflict Contract Matrix

1. `section_experience_*`
   - Prompt output: `{"bullets":[...]}`.
   - Runtime internal representation: normalized to existing `Variation` list.
2. `triage_job_fit_and_risks`
   - Prompt output: `{"triage_result": {...}}`.
   - Runtime internal representation: one selected decision payload + generated markdown summary.
3. Other sections
   - Prompt output: existing universal `{"variations":[...]}`.

This avoids schema overlap and keeps section behavior explicit.

## Step-by-Step Implementation

1. Data model update
   - Add triage-specific Pydantic model(s) in `graph_state.py`:
     - `TriageResult`
     - nested models for subscores, risks, Spain risk, sources.
   - Keep existing `Variation` model unchanged for non-triage sections.

2. Parser update (`json_parser.py`)
   - Add `parse_triage_result(raw_text: str) -> TriageResult`.
   - Preserve defensive cleanup and malformed JSON handling already used in `parse_response_envelope`.
   - Keep section-specific routing explicit:
     - triage -> triage parser
     - experience -> bullets normalization path
     - other sections -> current envelope parser.

3. LLM schema update (`llm_client.py`)
   - Make `_response_json_schema(section_id)` return triage schema for triage section.
   - Keep experience schema for `section_experience_*`.
   - Keep universal variations schema for remaining sections.

4. Node flow update (`graph_nodes.py`)
   - In `node_triage`, parse with triage parser (not `variations` path).
   - Map triage result to:
     - a concise decision summary for user
     - a canonical selected content string for current workflow compatibility.
   - Ensure apply/stop logic keys off `triage_result.verdict`.

5. Console redesign (`console_ui.py`)
   - Prompt rendering:
     - show first 5 lines only.
     - append: `... [truncated; total_lines=N]`.
   - Triage response rendering:
     - one compact panel only (verdict, decision score, confidence, top reasons, top risks).
     - do not print multiple long sections.
   - Keep full content accessible via debug artifact files when debug mode is enabled.

6. Tests update
   - `tests/test_prompt_json_contract.py`
     - enforce triage keys for triage prompt (`triage_result`, `verdict`, `decision_score_0_to_100`, etc.).
     - keep experience and default section contract checks separate.
   - `tests/test_json_parser.py`
     - add hardcoded valid/invalid triage JSON cases.
     - keep current experience bullets normalization tests.
   - `tests/test_llm_client.py`
     - assert triage schema is requested for triage section.
   - `tests/test_integration_graph_mocked.py`
     - add triage mocked payload using `triage_result`.
   - Add UI-focused tests for prompt truncation and single compact triage rendering.

7. Quality gates
   - Run `black .`
   - Run `ruff check . --fix`
   - Run `pytest`

## Migration Notes

1. Backward compatibility for old triage `variations` payload is optional.
2. Recommended: temporary fallback support for 1 release cycle, then remove.
3. If fallback is enabled, log one warning per run when old format is detected.

## Risks and Mitigations

1. Risk: mixed schemas cause parser ambiguity.
   - Mitigation: explicit section-based parser routing, no heuristic guessing.
2. Risk: console still feels truncated/unusable.
   - Mitigation: fixed preview limits + explicit truncation notices + debug artifact path output.
3. Risk: regression in review/assembly flow.
   - Mitigation: keep non-triage `Variation` path untouched and add integration tests.

## Acceptance Criteria

1. Triage prompt contract contains no `variations` key.
2. Runtime triage parsing succeeds with `triage_result` payload and drives continue/stop decision.
3. Console shows only first 5 prompt lines with truncation message.
4. Triage output is rendered once in compact form.
5. Full test suite passes with updated contracts.

---

# Implementation Plan: Role-Based Prompt/Knowledge Sources

## Objective

Support multiple target roles by selecting role-specific `prompts/` and `knowledge/` subfolders while keeping the same workflow and section structure.

## Decisions Locked

1. Existing assets move to:
   - `prompts/role_senior_dotnet_engineer/`
   - `knowledge/role_senior_dotnet_engineer/`
2. New empty role folders are added:
   - `prompts/role_engineering_manager/`
   - `knowledge/role_engineering_manager/`
3. Role resolution priority mirrors model resolution:
   - explicit CLI arg -> run metadata -> env var -> default role
4. Role mismatch on existing runs should fail fast (no silent cross-role resume/regenerate).

## Step-by-Step Implementation

1. Move files and create folders
   - Move all files currently in top-level `prompts/` and `knowledge/` into `role_senior_dotnet_engineer` subfolders.
   - Create empty `role_engineering_manager` folders under both roots.

2. Add role config in `settings.py`
   - Add env constant (`ART_ROLE`) and default role constant.
   - Add helper(s) to resolve role name and role-specific prompts/knowledge/template/offline-fixture paths.

3. Wire role into CLI/runtime (`main.py`)
   - Add `--role` argument.
   - Resolve role using the same precedence style as model config.
   - Persist `role_name` in run metadata.
   - Build runtime prompt/knowledge paths from resolved role.

4. Keep offline mode working (`llm_client.py`)
   - Make default offline fixture path role-aware when `ART_OFFLINE_FIXTURES_PATH` is not set.

5. Update privacy guardrails (`.gitignore`)
   - Switch ignore/allowlist patterns to cover nested role subfolders.

6. Update tests
   - Replace hardcoded top-level `prompts`/`knowledge` references in tests with role-aware defaults.
   - Keep existing behavior assertions for graph flow unchanged.

7. Quality gates
   - Run `black .`
   - Run `ruff check . --fix`
   - Run `pytest`

## Acceptance Criteria

1. App loads prompts/knowledge from role subfolders selected at run start.
2. Existing runs retain and reuse saved `role_name` safely.
3. Offline mode works without manual fixture-path override.
4. Empty new role folders are present and selectable.
5. Formatter, linter, and tests pass.
