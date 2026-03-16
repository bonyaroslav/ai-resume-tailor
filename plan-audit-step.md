# Audit Step Implementation Plan

## Approved Decisions

- Add an automatic audit step after final CV assembly, not after cover letter generation.
- Extract text from the generated CV `.docx` before sending it to Gemini.
- Add a new prompt file for the audit step.
- Save the audit result as Markdown in the same run folder.
- Rename `cover_letter.txt` to `cover_letters.md`.
- Preserve all cover letter variations in Markdown, ordered by score descending.
- Keep the selected cover letter clearly separated at the top of the Markdown output.
- Update tests, offline fixtures, and README references as part of the same change.

## Prompt Decision

- Prompt file name: `audit_cv_deep_dive.md`
- Audit output file name: `cv_deep_dive_audit.md`
- Cover letter output file name: `cover_letters.md`

## Audit Prompt Contract

The audit prompt should request Markdown output with these sections:

1. ATS Match Rate
2. Keyword Gap Analysis
3. Hiring Manager Read
4. Actionable Fixes

Rules:

- keep the response concise and scannable
- stay evidence-based
- do not invent experience or qualifications
- target specific CV sections when suggesting fixes

## Implementation Steps

1. Add the new audit prompt file under the role prompts directory.
2. Extend workflow routing so `assemble` transitions to a new automatic audit node.
3. Add runtime output paths for:
   - `cover_letters.md`
   - `cv_deep_dive_audit.md`
4. Extract text from the generated CV `.docx`.
5. Build and execute the audit prompt using:
   - `job_description.md`
   - extracted final CV text
6. Save the audit result as `cv_deep_dive_audit.md`.
7. Replace single-output cover letter writing with Markdown export containing:
   - final approved version
   - all variations sorted by `score_0_to_100` descending
8. Keep `doc_cover_letter` in the review flow, but change the artifact writer to Markdown.
9. Tighten cover letter validation so the API response must contain multiple variations.
10. Update offline fixtures and automated tests.
11. Update README and setup docs for the new artifact names and audit output.

## Verification Plan

- run `black .`
- run `ruff check . --fix`
- run targeted pytest coverage for:
  - document output helpers
  - mocked graph integration
  - CLI integration
  - offline end-to-end flow

## Compatibility Notes

- Resume, regenerate, and rebuild flows must continue to reuse the saved artifact configuration.
- Rebuild should regenerate both `cover_letters.md` and `cv_deep_dive_audit.md`.
- Existing review behavior should remain unchanged.
