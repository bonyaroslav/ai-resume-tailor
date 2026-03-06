Here is the fully updated, comprehensive `TODO.md` file. It removes the outdated linear-pipeline assumptions and replaces them with strict architectural decisions required to build your **Graph-Based (LangGraph-style) State Machine**.

You can copy and paste this directly to replace your entire `TODO.md` file.

---

# TODO: Pre-Implementation Architectural Decisions (Priority Ordered)

## 1) Define Graph State Object Structure (The Memory)

* **Risk:** If the state object is poorly structured, routing backward during the generation loop will overwrite data or lose context.
* **Decide:** Data structure for `GraphState` (Dict vs. Pydantic).
* **Recommended:** - Use a strict `Pydantic` model.
* Required fields: `job_description`, `triage_result` (Go/No-Go), `draft_variations` (dict mapping section names to arrays of generated drafts), `user_feedback` (dict tracking regeneration requests), and `final_selections`.



## 2) Design the Checkpoint / Resume Mechanism

* **Risk:** The script might crash during concurrent generation, or the user might want to review variations tomorrow, losing API context.
* **Decide:** How to pause and resume the graph execution.
* **Recommended:** - Serialize the `GraphState` to `runs/company_name/state_checkpoint.json` right before triggering the Human-in-the-Loop (HITL) node.
* Allow the graph to cleanly re-hydrate from this file.



## 3) Lock Exact CLI Input Contract

* **Risk:** Input behavior is ambiguous for starting vs. resuming a session.
* **Decide:** Exact `argparse` commands and flags.
* **Recommended:**
* `python main.py new --jd-path ./inputs/jd.txt --company "Stripe"` (Starts a fresh graph).
* `python main.py resume --state-path ./runs/stripe-01/state_checkpoint.json` (Reloads state and resumes at the HITL node).



## 4) Define HITL Node Interface Actions

* **Risk:** The system needs a strict contract for the human user to trigger forward vs. backward graph edges.
* **Decide:** CLI menu navigation commands.
* **Recommended:**
* For each generated section (Summary, Skills, Exp 1-3), present variations.
* Accept `1`, `2`, `3` to approve a variation (Forward Edge).
* Accept `R` to prompt for a custom string ("What should be changed?") to trigger a regeneration (Backward Edge).



## 5) Define Feedback Injection Strategy (The Backward Loop)

* **Risk:** How do we pass human feedback back to the LLM without creating a completely separate `07_constructive_criticism.md` prompt?
* **Decide:** Prompt injection strategy for the regeneration loop.
* **Recommended:** - Do not use a dedicated prompt file for criticism.
* Dynamically append a system message or text block to the original prompt (e.g., `"USER FEEDBACK FOR REVISION: {user_feedback}"`) during the backward loop.



## 6) Define the Assembly Node's Trigger

* **Risk:** `document_builder.py` might attempt to map placeholders before all sections are fully approved, resulting in a broken `.docx`.
* **Decide:** Condition for the final forward edge.
* **Recommended:** - The graph only routes to the `node_assemble` function when `GraphState.is_fully_approved == True` (meaning all 5 required sections have a locked selection).

## 7) Define State Persistence File Structure

* **Risk:** Cluttering the `runs/` directory with too many intermediate text files makes debugging difficult.
* **Decide:** Final output folder contents.
* **Recommended:**
* `runs/company-01/jd_original.txt`
* `runs/company-01/state_checkpoint.json` (Contains all raw API responses, reasoning, and scores)
* `runs/company-01/CV_Final.docx`
* `runs/company-01/workflow.log`



## 8) Define Safe Run Folder Naming Rules

* **Risk:** Folder name format `YY.MM.DD Company` can fail on Windows with invalid company characters.
* **Decide:** Sanitization and collision policy for company names.
* **Recommended:**
* Allow only `[A-Za-z0-9 _-]`, replace others with `_`.
* Append `-01`, `-02`, ... on collisions for the same company.



## 9) Protect Privacy by Ignoring Run Artifacts in Git

* **Risk:** Run outputs contain personal data and targeted CVs that may be committed by mistake.
* **Decide:** Versioning of run artifacts.
* **Recommended:**
* Store all run outputs under `runs/`.
* Add `runs/` to root `.gitignore`.



## 10) Set Retry and Cost-Control Limits

* **Risk:** Concurrency and loops can cause runaway API calls if validation repeatedly fails.
* **Decide:** Max retries, timeout, and abort thresholds.
* **Recommended:**
* `max_retries_per_section = 2` (for JSON validation failures).
* Abort pipeline if validation fails consecutively.



## 11) Lock JSON Validation Strictness Rules

* **Risk:** Malformed markdown wrappers (e.g., `json...`) from the LLM will break `json.loads()`.
* **Decide:** Parsing defense strategy.
* **Recommended:**
* Aggressively strip markdown code blocks before parsing.
* Validate strictly against the expected Pydantic schema (Variations list, IDs, Scores, Reasoning, Content).



## 12) Define Environment Bootstrap Before Quality Gates

* **Risk:** Formatter/linter/tests currently unavailable in the baseline environment.
* **Decide:** Dependency management workflow.
* **Recommended:**
* Provide a `requirements.txt` or `pyproject.toml` including `pytest`, `ruff`, `black`, `google-genai`, `python-docx`, and `pydantic`.