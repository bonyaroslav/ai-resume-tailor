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


4. Define initial module layout for the Graph-Based architecture:
* `main.py`: CLI entrypoint, argument parsing, and graph initialization.
* `graph_state.py`: Defines the strictly typed data structure (e.g., Pydantic model) that holds the single persistent session state (JD, triage results, generated drafts, user feedback).
* `graph_nodes.py`: Contains isolated worker functions (Nodes) that take the State, perform tasks (`node_triage`, `node_generate`, `node_assemble`), and return an updated State.
* `graph_router.py`: Contains the conditional logic (Edges) that evaluates the State and determines the next node (handles forward progression and backward loops).
* `prompt_loader.py`: Prompt + YAML frontmatter loading, knowledge file resolution.
* - llm_client.py: Centralized, provider-agnostic LLM interface. Exposes a single generic async generation function. Google/OpenAI SDK imports must remain strictly isolated inside this file and never leak into the Graph Nodes.
* `retrospective_ui.py`: The decoupled Human-in-the-Loop (HITL) interface that reads the State, presents choices, and captures feedback.
* `document_builder.py`: DOCX placeholder mapping and final file export.

### Phase 1: Configuration and Logging Foundation

Goal: ensure traceability and secure runtime configuration.

1. 1. Implement environment/config loading: Require an LLM_PROVIDER variable (e.g., 'gemini', 'openai', 'ollama') alongside the respective API credentials to enable seamless engine swapping.
2. Define CLI input contract for Job Description ingestion:
   - user provides JD as a file path in console
   - accepted input file types: `.txt` and `.docx`
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
   - mask or truncate sensitive user data and long freeform content
6. Define workflow run-folder convention for all artifacts:
   - create one folder per workflow run
   - folder name format: `YY.MM.DD Company` (example: `26.02.27 Microsoft`)
   - all generated outputs, logs, and saved responses for that run live in this folder

### Phase 2: Execution Node 1 (Triage)

Goal: Implement the initial sequential gate to evaluate the job description before spending API credits on generation.

1. Implement `node_triage(state: GraphState) -> GraphState`.
2. Load and parse `00_job_description_analysis.md`, resolving its specific YAML frontmatter to load required `knowledge/` files.
3. Execute the Gemini API call and parse the Go/No-Go JSON response.
4. **Implement Gate 1 (Forward Edge):** Evaluate the updated State. If the triage result is "No-Go", terminate the graph cleanly. If "Go", route the state forward to Node 2.

### Phase 3: Execution Node 2 (Concurrent Generation)

Goal: Generate all required CV section variations simultaneously, while supporting regeneration instructions from previous loops.

1. Implement `node_generate_sections(state: GraphState) -> GraphState`.
2. **Context Injection:** Check the `GraphState` for any existing `user_feedback` (this will exist if the graph has looped backward). If feedback exists for a specific section (e.g., "Summary"), dynamically inject it into that specific prompt.
3. Use `asyncio.gather()` to concurrently execute prompts `01` through `05` (only executing the ones that are currently missing or marked for regeneration).
4. Parse the returned JSON arrays (variations, scores, AI reasoning) and append them to the `GraphState`.

### Phase 4: Execution Node 3 (Human-in-the-Loop & The Backward Edge)

Goal: Pause the system, allow human review, and implement the graph's cyclic routing logic.

1. **Checkpointing:** Before asking for user input, strictly save the `GraphState` to `runs/company/state_checkpoint.json` so the session can be paused/resumed.
2. Display the UI menu showing the generated variations side-by-side.
3. **Implement Gate 2 (The Routing Logic):**
* **Forward Edge (Progression):** If the user selects a specific variation (e.g., "Accept A"), lock it into the `final_selections` of the state. Once all required sections are locked, route forward to the Document Assembly node.
* **Backward Edge (The Loop):** If the user rejects the variations for a section, capture their text input (e.g., "Make the tone more aggressive"). Update the `GraphState.user_feedback` with this string. Route the state **backward** to Node 2 (`node_generate_sections`) to run another cycle just for that section.
### Phase 5: Human-in-the-Loop Retrospective and Selection

Goal: provide explicit review UX for safe user-controlled final content.

1. For each section, display:
   - section name
   - variation id
   - score
   - ai reasoning
   - generated content
2. Allow user actions per section:
   - choose a variation
   - edit selected content
   - retry that section generation
3. Log final user decisions at `INFO`.
4. Persist normalized selected content map for downstream output assembly.
5. Persist every LLM response in readable files inside the run folder:
   - one file per prompt/stage
   - include raw text and normalized JSON for review/debugging

### Phase 6: Output Assembly (CV DOCX and Cover Letter Export)

Goal: produce deterministic artifacts while preserving the base template.

1. Map selected content to supported DOCX placeholders:
   - `{{01_professional_summary}}`
   - `{{02_work_experience_1}}`
   - `{{03_work_experience_2}}`
   - `{{04_work_experience_3}}`
   - `{{05_skills_alignment}}`
2. Export CV from template without modifying the original template file.
3. Handle `06_cover_letter` as separate output file (for example `.md`) unless template placeholders are extended.
4. Define persistence for critique output (`07_constructive_criticism`) when used:
   - store as optional QA artifact
   - do not inject into CV template placeholders
5. Log final output file paths at `INFO` and keep them inside the run folder.

### Phase 7: Tests, Lint, Format, Final Verification

Goal: enforce deterministic quality checks before completion.

1. Implement deterministic tests only (no live LLM quality assertions):
   - JSON parser tests with dirty payload fixtures
   - DOCX placeholder replacement tests with dummy strings
   - prompt frontmatter parser tests (`knowledge_files` success/failure)
   - mapping tests (prompt filename -> output key -> placeholder)
   - Graph Routing tests: Use mock state dictionaries to test that the router correctly triggers the End Node on a 'No-Go' triage, and correctly routes backward when human_feedback is present.
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
 
 
