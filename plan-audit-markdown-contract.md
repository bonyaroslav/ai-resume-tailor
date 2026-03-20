# Audit Markdown Contract Migration Plan

## Objective

Convert the `audit_cv_deep_dive` step from JSON-envelope output to direct Markdown output, save the Markdown to `cv_deep_dive_audit.md`, and keep the rest of the workflow stable.

## Locked Decisions

1. The audit prompt returns Markdown only.
2. The audit step no longer uses the shared JSON envelope.
3. The audit response is written directly to `cv_deep_dive_audit.md`.
4. The audit section remains in workflow state for resumability, but stores the final Markdown as selected content.
5. The rest of the generation sections keep their existing JSON contracts unchanged.

## File Touchpoints

- `prompts/role_engineer/audit_cv_deep_dive.md`
- `llm_client.py`
- `graph_nodes.py`
- `tests/test_prompt_json_contract.py`
- `tests/test_integration_graph_mocked.py`
- `tests/test_offline_e2e.py`

## Implementation Steps

1. Prompt contract
   - Rewrite the audit prompt to request Markdown only.
   - Remove JSON schema instructions from the prompt.
   - Require a stable Markdown heading structure.

2. LLM client
   - Allow audit requests to use plain text output instead of forced JSON MIME type and schema.
   - Keep existing JSON behavior for all non-audit sections.

3. Audit node
   - Treat the audit model response as raw Markdown.
   - Add light validation:
     - response is non-empty
     - response starts with `#`
     - required headings are present
   - Save the Markdown to `cv_deep_dive_audit.md`.
   - Persist the Markdown in the audit section state via `selected_content`.

4. Tests
   - Exempt audit prompt from shared JSON-contract assertions.
   - Update mocked integration responses so audit returns Markdown instead of JSON.
   - Keep end-to-end assertions focused on the generated Markdown file content.

5. Verification
   - Run `black .`
   - Run `ruff check . --fix`
   - Run `pytest`

## Risks

1. Audit becomes an exception to the shared section contract.
   - Mitigation: make audit handling explicit in prompt tests, LLM client, and audit node code.
2. Raw Markdown increases response-format variability.
   - Mitigation: validate a small set of required headings instead of relying on full schema parsing.
3. Existing tests may still assume JSON audit fixtures.
   - Mitigation: update all audit-specific fixtures and integration mocks in the same change.

## Acceptance Criteria

1. `audit_cv_deep_dive` prompt asks for Markdown only.
2. Audit LLM requests do not require JSON schema/config.
3. Audit node accepts Markdown, validates it lightly, and writes it to `cv_deep_dive_audit.md`.
4. Existing non-audit sections continue to use their current JSON flows.
5. Formatter, linter, and test suite pass after the change.

