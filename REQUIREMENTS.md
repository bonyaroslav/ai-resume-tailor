# Requirements (V1 Baseline)

## Runtime

- Python `3.10+` (tested on `3.13`)
- Local `.venv`
- Gemini API key via `GEMINI_API_KEY`

## Execution profiles

Two execution profiles are allowed:

1. Real Gemini mode
   - Uses Google AI Studio API key via `GEMINI_API_KEY`.
   - Calls Gemini through `google-genai`.
2. Offline emulation mode
   - Uses deterministic local fixtures.
   - Must preserve the same universal envelope schema as real mode.
   - Must not require network access.

## Dependencies

- `google-genai`
- `python-docx`
- `rich`
- `pydantic`
- `PyYAML`
- `pytest`
- `black`
- `ruff`

## Locked workflow contract

Canonical ordered workflow IDs:

1. `triage_job_fit_and_risks`
2. `section_professional_summary`
3. `section_skills_alignment`
4. `section_experience_1`
5. `section_experience_2`
6. `section_experience_3`
7. `doc_cover_letter`

Rules:

- Experience names normalize with `^section_experience_(\d+)(?:_.+)?$` to `section_experience_<n>`.
- Cover letter is required in review/output but is not a CV template placeholder requirement.
- Prompt files outside the locked workflow are ignored.
- Duplicate normalized prompt IDs fail fast.

## GraphState and checkpoint contract

Persisted checkpoint JSON must include:

- `state_version` (`"1.0"`)
- `run_id`
- `status` (`running|awaiting_review|completed|failed`)
- `current_node`
- `section_states`
- `review_queue`
- `updated_at` (ISO-8601 UTC)

Per-section normalized shape:

- `status`
- `variations`
- `selected_variation_id`
- `selected_content`
- `user_note`
- `retry_count`

Rules:

- Only normalized resumable state is checkpointed.
- Checkpoint writes are atomic (temp + rename).
- Corrupt JSON or unsupported `state_version` must fail clearly.

## Prompt/frontmatter contract

- Prompt format: markdown with optional YAML frontmatter.
- Supported frontmatter keys: only `knowledge_files`.
- `knowledge_files` must be a list of filenames under `knowledge/`.
- Invalid YAML, unsupported keys, and missing files fail fast.
- `inject_context(prompt, context_files)` is the isolated context injection boundary.

## LLM response contract

Universal response envelope for every prompt:

```json
{
  "variations": [
    {
      "id": "A",
      "score_0_to_5": 5,
      "ai_reasoning": "Reasoning string here",
      "content_for_template": "The actual text to inject into the output"
    }
  ]
}
```

Parsing behavior:

- Cleanup before parse: whitespace trim, markdown fence removal, optional leading `json` label removal.
- `json.loads()` is wrapped with explicit parse error handling.
- Envelope schema is validated via Pydantic.
- Parse/schema failures are logged separately.
- Automatic parse retry is capped to one retry per request.

## Review and retry contract

Per-section actions:

- choose variation
- edit selected content
- retry with note

Global action:

- `save_and_exit` (checkpoint and exit cleanly)

Rules:

- Section is approved only when `selected_content` is final.
- User-triggered retries are capped to two per section.
- Retry note is appended back into the same original section prompt.

## Template validation and outputs

- Template preflight runs before generation and at assembly.
- Default template path is expected under `knowledge/` for local consistency.
- Required CV placeholders:
  - `section_professional_summary`
  - `section_skills_alignment`
  - `section_experience_1`
  - `section_experience_2`
  - `section_experience_3`
- Experience placeholders use the same normalization rule as prompt IDs.
- Duplicate normalized template placeholders fail fast.
- Outputs are written under run folder:
  - `tailored_cv.docx`
  - `cover_letter.txt`

## CLI contract

Only two entry commands:

- `run --jd-path <path.txt> --company <name>`
- `resume --run-path <run_dir>` or `resume --checkpoint-path <checkpoint.json>`

`run` supports `.txt` JD input only.

Offline support rules:

- Offline run behavior must be explicitly enabled (toggle/flag/env).
- Default behavior remains interactive HITL and real Gemini mode.

## Privacy and logging

- Artifacts stay under `runs/`.
- Raw prompt/response dumps are stored only with explicit debug mode.
- Logs include metadata (sizes/hash) and redact common identifiers and secrets.
- Full JD/knowledge/raw payload logging is avoided by default.

## Deterministic test scope

- JSON cleanup and envelope validation
- Prompt frontmatter parsing and knowledge file validation failures
- Section-ID mapping and canonical normalization
- Router transitions (triage stop, review retry, review to assembly)
- DOCX placeholder preflight and replacement
- Offline end-to-end workflow test with deterministic local fixtures
- No live LLM API tests
