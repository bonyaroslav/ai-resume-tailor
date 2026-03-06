# TODO: Pre-Implementation Decisions

## 1) Lock the Minimal `GraphState`

* **Risk:** An oversized state object will become a dumping ground for raw payloads and future features.
* **Decide:** Final V1 `GraphState` fields.
* **Recommended:**
* Use a small Pydantic model.
* Keep only resumable workflow data: `job_description`, `company`, `current_step`, `triage_result`, `draft_variations`, `user_feedback`, `final_selections`, `run_dir`.

## 2) Lock the Review Contract

* **Risk:** Ambiguous review actions create extra routing branches and UI code.
* **Decide:** Allowed user actions during review.
* **Recommended:**
* Allow exactly three actions per section: accept, edit, regenerate with note.
* Route to assembly only when every required section has a final approved value.

## 3) Lock the Workflow Definition

* **Risk:** Hardcoding numbered prompts or implicit ordering will break when new prompt files are inserted later.
* **Decide:** How active generation steps are declared.
* **Recommended:**
* Use one small ordered workflow definition keyed by canonical `section_id` strings.
* Use prompt filename stems as the default `section_id` where possible.
* If the workflow changes later, update that small definition and the explicit router. Do not build a generic DAG engine.

## 4) Lock the Regeneration Strategy

* **Risk:** Regeneration can sprawl into extra prompt files or autonomous loops.
* **Decide:** How user feedback re-enters generation.
* **Recommended:**
* Do not create a separate critique prompt.
* Append the user's revision note to the original section prompt during regeneration.
* Apply a small retry cap.

## 5) Lock Checkpoint Scope

* **Risk:** Checkpoints become privacy-heavy archives instead of resumable state.
* **Decide:** What is stored in `state_checkpoint.json`.
* **Recommended:**
* Store normalized state only.
* Save raw prompt/response bodies only behind an explicit debug flag.

## 6) Lock Run Artifact Rules

* **Risk:** Personal data leaks into version control or gets scattered across the repo.
* **Decide:** Where outputs and logs live.
* **Recommended:**
* Store all run artifacts under `runs/`.
* Keep `runs/` and real `knowledge/` content out of git.
* Use sanitized run-folder names with a simple collision suffix when needed.

## 7) Lock V1 Provider Scope

* **Risk:** Multi-provider abstractions will add dead code before the first working slice exists.
* **Decide:** Which LLM path exists in V1.
* **Recommended:**
* Implement Gemini only.
* Keep `llm_client.py` centralized, but do not add provider registries, interfaces, or unused stubs.

## 8) Lock Deterministic Test Scope

* **Risk:** Tests drift into LLM-quality assertions or integration-heavy fixtures.
* **Decide:** Which behaviors are worth testing in V1.
* **Recommended:**
* Test JSON cleanup and validation.
* Test prompt frontmatter loading.
* Test routing decisions from mock states.
* Test DOCX placeholder replacement with dummy strings.
