## Skills Prompt Plan

Status: completed

### Intentions

- Update `section_skills_alignment` handling to support the new JSON contract:
  - top-level `meta`
  - `variations[].text`
- Normalize the best skills variation into the existing CV placeholder flow so the DOCX builder still receives plain text for `section_skills_alignment`.
- Preserve all AI output data for crash recovery, debugging, and later analysis.
  - Keep raw model responses for every generation attempt.
  - Keep parsed payloads when parsing succeeds.
  - Keep parse/schema failure details when parsing fails.
  - Keep these artifacts in checkpoint state by default.
- Keep regenerate behavior correct for the skills section.
  - A regenerate request clears the active selection.
  - Newly generated skills variations parse correctly from the new schema.
  - Best-variation auto-approval and manual review still work.
- Add tests that fail when the skills prompt contract drifts.
  - Prompt contract test for `meta` and `variations[].text`
  - Parser tests for valid and invalid skills payloads
  - Regenerate flow coverage for skills

### Implemented Changes

- Added skills-specific response normalization in `json_parser.py`.
- Added checkpoint-persisted `ai_outputs` retention in `graph_state.py` and `checkpoint.py`.
- Preserved AI outputs across generation, review, triage, and regenerate flows in `graph_nodes.py` and `main.py`.
- Updated Gemini JSON schema generation for `section_skills_alignment` in `llm_client.py`.
- Updated offline fixture data for the skills section.
- Added and updated tests covering parser behavior, prompt contract enforcement, checkpoint migration, regenerate retention, LLM schema generation, and mocked graph integration.

### Validation

- `ruff check . --fix`: passed
- `pytest`: passed (`95 passed`)
- `black .`: completed reformatting touched files, but the command did not exit before the timeout in this environment. The final state includes Black-applied formatting on the touched files.
