# TODO: Pre-Implementation Decisions

## 1) Lock Canonical `section_id` Source and V1 Section Inventory

* **Risk:** Alias mapping between prompts, state, and DOCX placeholders will create avoidable bugs.
* **Decide:** Where `section_id` comes from and which sections exist in V1.
* **Recommended:**
* Use the DOCX placeholder name as the canonical `section_id`.
* Require the prompt filename stem to match the canonical `section_id` exactly for non-experience sections.
* For experience prompts and DOCX placeholders, normalize names with the same regex: `^section_experience_(\d+)(?:_.+)?$`.
* Examples of valid experience prompt stems: `section_experience_1_oldest`, `section_experience_2_previous`, `section_experience_3_latest`, `section_experience_4_company_x`.
* The canonical `section_id` for every experience entry is only the prefix: `section_experience_<n>`.
* Lock the V1 workflow section list now: `triage_job_fit_and_risks`, `section_professional_summary`, `section_skills_alignment`, `section_experience_1`, `section_experience_2`, `section_experience_3`, `doc_cover_letter`.
* Treat `doc_cover_letter` as a non-template output section. It is needed for the application flow, but it is not injected into the CV DOCX.
* Ignore any prompt file that is not listed in that ordered workflow definition.
* Treat any suffix after `section_experience_<n>` as display-only metadata for the user. The code must ignore it in both prompt files and DOCX placeholders.
* Fail fast if two prompt files or two DOCX placeholders normalize to the same canonical `section_id`.

## 2) Lock the Minimal `GraphState`

* **Risk:** An oversized state object will become a dumping ground for raw payloads and future features.
* **Decide:** Final V1 `GraphState` fields.
* **Recommended:**
* Use a small Pydantic model.
* Keep only normalized resumable state required by the checkpoint contract: `state_version`, `run_id`, `status`, `current_node`, `section_states`, `review_queue`, `updated_at`.
* Keep triage output inside `section_states["triage_job_fit_and_risks"]`. For a triage `No-Go`, set `status` to `completed` and `current_node` to `triage_stop`.
* Keep section-specific data inside `section_states[section_id]` instead of adding top-level fields for each workflow concern.
* Use one normalized per-section shape in `section_states`: `status`, `variations`, `selected_variation_id`, `selected_content`, `user_note`, `retry_count`.
* Keep one canonical `section_id` across prompts, `section_states`, review keys, output files, and DOCX placeholders.

## 3) Lock the Review Contract

* **Risk:** Ambiguous review actions create extra routing branches and UI code.
* **Decide:** Allowed user actions during review.
* **Recommended:**
* Allow exactly three actions per section: choose variation, edit selected content, retry with note.
* Treat a section as approved only when it has one final selected content value.
* Add one global review action: `save_and_exit`. It is not a section action and only writes a checkpoint then exits cleanly.
* Route to assembly only when every required section has a final approved value.

## 4) Lock the Workflow Definition

* **Risk:** Hardcoding numbered prompts or implicit ordering will break when new prompt files are inserted later.
* **Decide:** How active generation steps are declared.
* **Recommended:**
* Use one small ordered workflow definition keyed by canonical `section_id` strings.
* Keep triage as one explicit node before generation.
* Build the experience portion of the workflow from canonical IDs such as `section_experience_1`, `section_experience_2`, `section_experience_3`. Higher numbers represent newer experiences.
* Keep cover letter generation as one explicit output step. It always produces a separate file for the job application and is not part of CV template injection in V1.
* If the workflow changes later, update that small definition and the explicit router. Do not build a generic DAG engine.

## 5) Lock the Prompt and Frontmatter Contract

* **Risk:** Loose prompt metadata will create parsing branches and hidden configuration rules.
* **Decide:** Which prompt file structure is supported in V1.
* **Recommended:**
* Prompt files are Markdown with optional YAML frontmatter.
* Support only one frontmatter key in V1: `knowledge_files`.
* Require `knowledge_files` to be a list of file names under `knowledge/`.
* For experience prompts, parse the canonical `section_id` from the filename stem using the locked regex rule and ignore any remaining suffix.
* Fail fast on invalid YAML, unsupported frontmatter keys, or missing `knowledge/` files.

## 6) Lock the AI Response Parsing Contract

* **Risk:** Ad hoc cleanup logic will grow into a fragile recovery layer.
* **Decide:** What cleanup and validation are allowed before parsing AI output.
* **Recommended:**
* Always expect the universal JSON envelope from `AGENTS.md`.
* Apply only small cleanup steps before `json.loads()`: trim whitespace, strip Markdown code fences, and remove a single leading `json` fence label if present.
* Wrap `json.loads()` in `try/except` and validate required keys and value types after parsing.
* Treat malformed JSON and schema mismatch as separate errors in logs and retry at most once automatically.

## 7) Lock the Regeneration Strategy

* **Risk:** Regeneration can sprawl into extra prompt files or autonomous loops.
* **Decide:** How user feedback re-enters generation and where retry limits stop.
* **Recommended:**
* Do not create a separate critique prompt.
* Append the user's retry note to the original section prompt during regeneration.
* Allow at most two user-triggered regenerations per section in V1.
* If the retry cap is reached, require the user to either edit a chosen variation or accept an existing one.

## 8) Lock Checkpoint Behavior

* **Risk:** Checkpoints become privacy-heavy archives or fail unreliably during resume.
* **Decide:** How `state_checkpoint.json` is written, resumed, and versioned.
* **Recommended:**
* Store normalized state only. Keep raw prompt/response dumps out of the checkpoint.
* Write checkpoints atomically using a temp file and rename.
* Save a checkpoint at node boundaries and immediately before waiting for review input.
* If a checkpoint is corrupt or has an unsupported `state_version`, fail with a clear error instead of trying to guess recovery behavior.

## 9) Lock the CLI Contract

* **Risk:** A vague CLI will slow down implementation and make resume behavior inconsistent.
* **Decide:** What commands and inputs exist in V1.
* **Recommended:**
* Keep only two entry paths in V1: `run` and `resume`.
* `run` should require the JD file path and company name.
* `resume` should require the run folder path or checkpoint path.
* Use simple review commands in the terminal, including `save_and_exit` during review. Do not build a richer TUI than needed for MVP.

## 10) Lock Template Validation Rules

* **Risk:** Placeholder mismatches will surface late after API calls and manual review.
* **Decide:** What must be validated against the DOCX template before generation starts.
* **Recommended:**
* Preflight the template once before generation.
* Require every workflow `section_id` that targets the CV template to exist as a DOCX placeholder.
* For experience sections, normalize DOCX placeholders with the same locked regex rule and ignore any suffix after `section_experience_<n>`.
* Allow extra DOCX placeholders that are not used by V1.
* Fail fast if any required placeholder is missing.

## 11) Lock Run Artifact and Debug Rules

* **Risk:** Run outputs become hard to inspect or leak outside the run directory.
* **Decide:** Where artifacts live and how verbose debug evidence is stored.
* **Recommended:**
* Store all run artifacts under `runs/`.
* Use a simple sanitized folder format such as `YY.MM.DD-company-slug` with a numeric suffix on collision.
* Keep verbose raw JD, prompt, and response dumps only when an explicit debug mode is enabled.
* Never log API keys, auth headers, or secrets.

## 12) Lock V1 Provider and Runtime Baseline

* **Risk:** Environment drift and provider abstractions will slow down the first working slice.
* **Decide:** Which runtime and dependency assumptions are fixed for MVP.
* **Recommended:**
* Implement Gemini only in V1.
* Target Python 3.10+ in a local `.venv`.
* Keep dependencies limited to the current project scope: `google-genai`, `python-docx`, `rich`, `pydantic`, `pytest`, and only the smallest extra parsing dependency if it proves necessary.
* Do not run live LLM calls in tests.

## 13) Lock Deterministic Test Scope

* **Risk:** Tests drift into LLM-quality assertions or integration-heavy fixtures.
* **Decide:** Which behaviors are worth testing in V1.
* **Recommended:**
* Test JSON cleanup and envelope validation.
* Test prompt frontmatter loading and missing `knowledge_files` failures.
* Test routing decisions from mock states.
* Test DOCX placeholder replacement and template preflight with dummy strings.
* Skip tests that require live API access or subjective text-quality evaluation.

## 14) Lock the MVP Definition of Done

* **Risk:** Implementation keeps expanding because "done" is not concrete.
* **Decide:** What must work before V1 is considered usable.
* **Recommended:**
* One happy-path run can go from JD file to triage, section generation, review, and final CV output.
* Resume from a saved checkpoint works for at least one interrupted review flow.
* Required deterministic tests pass.
* `black .`, `ruff check . --fix`, and `pytest` are the only required quality gates.
* Do not block MVP on extra providers, autonomous loops, advanced logging systems, or non-essential UI polish.
