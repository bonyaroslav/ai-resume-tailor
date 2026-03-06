## Implementation Plan: AI Resume Tailor

This plan defines the build sequence, safety controls, workflow gates, and verification criteria.


### Phase 0: Repo Safety and Graph Scaffolding

Goal: establish privacy, module boundaries, and the core State Machine architecture before implementation work.

1. Add and verify privacy guardrails for personal data in `knowledge/`.
2. Keep personal knowledge files out of version control using `knowledge/.gitignore`:
* ignore `knowledge/*.md`
* allow only `knowledge/*.example.md` templates for shareable setup


3. Document sensitive-data handling requirements:
* do not log API keys or raw secrets
* redact personally sensitive fields in logs when feasible


4. Define the minimal module layout for the Graph-Based architecture. Create each file only when its first function is implemented:
* `main.py`: CLI entrypoint and graph start/resume wiring.
* `graph_state.py`: Pydantic models for persisted session state and validated AI envelopes.
* `graph_nodes.py`: Small worker functions (`node_triage`, `node_generate_sections`, `node_review`, `node_assemble`).
* `graph_router.py`: Explicit `if/elif` routing based on the current `GraphState`.
* `prompt_loader.py`: Prompt loading, frontmatter parsing, and `inject_context(prompt, context_files)`.
* `llm_client.py`: Centralized Gemini-only API call function for V1.
* `document_builder.py`: DOCX placeholder replacement and final export.
5. Define one canonical `section_id` per generated section. Use that same string across prompt stems, state keys, review keys, saved JSON, output filenames, and DOCX placeholders.
6. Keep graph changes simple: if a new workflow step is added later, update one explicit router function and one small ordered workflow definition. Do not design a generic DAG engine.

### Phase 1: Configuration and Logging Foundation

Goal: ensure traceability and secure runtime configuration.

1. Implement minimal V1 environment/config loading:
   - require `GEMINI_API_KEY`
   - optionally allow `GEMINI_MODEL`
   - do not implement `LLM_PROVIDER` switching in V1
2. Define CLI input contract for Job Description ingestion:
   - user provides JD as a file path in console
   - accepted input file type for V1: `.txt`
   - input may include links and all relevant context inline in the JD file
3. Implement dual logging sink:
   - console output for live workflow progress
   - local `.log` file for diagnostics and post-mortem analysis
4. Enforce log levels:
   - `INFO`: phase/stage start, completion, user decisions, output files
   - `DEBUG`: prompt metadata, referenced knowledge files, request/response metadata
   - `ERROR`: parse/validation failures with stack traces and payload snippets
5. Add log redaction policy:
   - never log API keys
   - do not log full JD text, full knowledge files, or raw LLM payloads by default
   - mask or truncate sensitive user data and long freeform content
6. Define workflow run-folder convention for all artifacts:
   - create one folder per workflow run
   - folder name format: `YY.MM.DD Company` (example: `26.02.27 Microsoft`)
   - sanitize unsafe filename characters
   - all generated outputs and logs for that run live in this folder
7. Define checkpoint policy:
   - checkpoint only the normalized `GraphState` required to resume
   - save raw prompt/response text only when an explicit debug flag is enabled

### Phase 2: Execution Node 1 (Triage)

Goal: Implement the initial sequential gate to evaluate the job description before spending API credits on generation.

1. Implement `node_triage(state: GraphState) -> GraphState`.
2. Load and parse `triage_job_fit_and_risks.md`, resolving its specific YAML frontmatter to load required `knowledge/` files.
3. Execute the Gemini API call and parse the Go/No-Go JSON response.
4. **Implement Gate 1 (Forward Edge):** Evaluate the updated State. If the triage result is "No-Go", terminate the graph cleanly. If "Go", route the state forward to Node 2.

### Phase 3: Execution Node 2 (Concurrent Generation)

Goal: Generate all required CV section variations simultaneously, while supporting regeneration instructions from previous loops.

1. Implement `node_generate_sections(state: GraphState) -> GraphState`.
2. **Context Injection:** Check the `GraphState` for any existing `user_feedback` (this will exist if the graph has looped backward). If feedback exists for a specific section (e.g., "Summary"), dynamically inject it into that specific prompt.
3. Use one small ordered list of active generation steps keyed by `section_id`. This list is the only place that defines which prompt-driven sections run in V1.
4. Use `asyncio.gather()` to concurrently execute only the sections that are currently missing or marked for regeneration.
5. Parse each returned JSON envelope and store the normalized variations under its matching `section_id`.
6. Apply a small retry limit for parse/validation failures. Abort cleanly when the limit is exceeded.

### Phase 4: Review Node (Human-in-the-Loop)

Goal: pause the system, allow human review, and implement the forward/backward routing logic.

1. **Checkpointing:** Before asking for user input, strictly save the `GraphState` to `runs/company/state_checkpoint.json` so the session can be paused/resumed.
2. For each section, display:
   - section name
   - variation id
   - score
   - ai reasoning
   - generated content
3. Allow exactly three user actions per section:
   - choose a variation
   - edit selected content
   - retry that section generation
4. **Implement Gate 2 (The Routing Logic):**
* **Forward Edge (Progression):** If all required sections have a final approved value, route forward to the Document Assembly node.
* **Backward Edge (The Loop):** If the user retries a section, capture their feedback string, update `GraphState.user_feedback[section_id]`, and route backward to `node_generate_sections` for only that section.
5. Log final user decisions at `INFO`.
6. Persist the normalized selected content map for downstream output assembly.

### Phase 5: Output Assembly (CV DOCX and Cover Letter Export)

Goal: produce deterministic artifacts while preserving the base template.

1. Map selected content to DOCX placeholders using the canonical `section_id` naming rule.
2. Export CV from template without modifying the original template file.
3. Handle the cover letter as a separate output file unless the template explicitly includes a matching placeholder.
4. Log final output file paths at `INFO` and keep them inside the run folder.

### Phase 6: Tests, Lint, Format, Final Verification

Goal: enforce deterministic quality checks before completion.

1. Implement deterministic tests only (no live LLM quality assertions):
   - JSON parser tests with dirty payload fixtures
   - DOCX placeholder replacement tests with dummy strings
   - prompt frontmatter parser tests (`knowledge_files` success/failure)
   - mapping tests (`section_id` -> state key -> placeholder)
   - Graph routing tests: use mock states to verify `No-Go` termination, review-to-assembly progression, and single-section regeneration routing
2. Run required quality gate commands in strict order:
   1. `black .`
   2. `ruff check . --fix`
   3. `pytest`
3. Completion criteria:
   - all required stages pass
   - selected content map is complete for expected sections
   - output files are generated successfully
   - base template remains unchanged
   - failures are traceable in logs with actionable context
 
 
