# TODO: Pre-Implementation Clarifications (Priority Ordered)

## 1) Lock Exact CLI Input Contract
- Risk: input behavior is still ambiguous at implementation time.
- Decide:
  - exact command(s) and flags (`--jd-path`, `--company`, `--mode review`, etc.)
  - which args are required vs optional
  - validation/error messages for missing/invalid values
- Recommended:
  - fail before any prompt loading when contract is violated
  - support JD file types: `.txt`, `.docx`

## 2) Define Safe Run Folder Naming Rules
- Risk: folder name format `YY.MM.DD Company` can fail on Windows with invalid company characters.
- Decide:
  - sanitization policy for company name
  - collision policy for repeated runs on same day
- Recommended:
  - allow only `[A-Za-z0-9 _-]`, replace others with `_`
  - append `-01`, `-02`, ... on collisions

## 3) Replace Free-Text Console Intent Detection With Explicit Commands
- Risk: "recognize review request" via NLP-style parsing is brittle.
- Decide:
  - explicit command grammar for runtime actions
- Recommended:
  - accepted commands: `go`, `close`, `review <cv_path>`
  - unknown input -> help + reprompt

## 4) Resolve Frontmatter Consistency for Prompt 07
- Risk: pipeline says frontmatter-driven loading for prompts, but `07_constructive_criticism.md` has no YAML frontmatter.
- Decide:
  - mandatory frontmatter for all prompts vs optional for critique
- Recommended:
  - make frontmatter mandatory for all prompts (including `07`) or codify deterministic default behavior

## 5) Finalize Triage Rendering Contract
- Risk: prompt enforces JSON-only output, while user requires easy-to-read formatted triage in console.
- Decide:
  - where formatting is applied
- Recommended:
  - keep LLM output JSON-only
  - render formatted CLI view from parsed `content_for_template`

## 6) Fix "Verified Sources" Requirement in Triage Prompt
- Risk: prompt asks for verified sources but no retrieval subsystem is defined.
- Decide:
  - add retrieval/browsing stage or remove this requirement
- Recommended:
  - for current scope, replace with "state assumptions and confidence level"

## 7) Define Missing API Key Behavior (Current Real-World Case)
- Risk: user may run without Google API config and get unclear runtime failures.
- Decide:
  - fail-fast only vs fail-fast + dry-run mode
- Recommended:
  - require `GOOGLE_API_KEY` before Stage 1
  - optional `--dry-run` for non-API validation of parsing/workflow

## 8) Standardize Artifact Layout and Filenames
- Risk: "save readable responses" is defined, but file tree is not deterministic.
- Decide:
  - final run folder structure and naming
- Recommended:
  - `raw/00.txt`
  - `normalized/00.json`
  - `rendered/00.md`
  - `selected_content.json`
  - `cv.docx`
  - `cover_letter.md`
  - `workflow.log`

## 9) Protect Privacy by Ignoring Run Artifacts in Git
- Risk: run outputs contain personal data and may be committed by mistake.
- Decide:
  - whether run artifacts are versioned
- Recommended:
  - store all run outputs under `runs/`
  - add `runs/` to root `.gitignore`
  - keep only safe examples in repo

## 10) Set Retry and Cost-Control Limits
- Risk: retry policy exists conceptually but lacks hard caps.
- Decide:
  - max retries, timeout, abort thresholds
- Recommended:
  - `max_retries_per_section = 2`
  - `request_timeout_seconds = 60`
  - abort when failed sections exceed configured threshold

## 11) Lock JSON Validation Strictness Rules
- Risk: no final policy on coercion vs rejection can cause inconsistent behavior.
- Decide:
  - strict reject vs selective coercion
- Recommended:
  - strict schema validation by default
  - allow only minimal coercion (e.g., numeric string to int) with explicit warning logs

## 12) Define Environment Bootstrap Before Quality Gates
- Risk: formatter/linter/tests currently unavailable in environment.
- Decide:
  - dependency/bootstrap workflow (`pip`, `uv`, or `poetry`)
- Recommended:
  - document reproducible setup in README
  - ensure `black`, `ruff`, `pytest` are available in `.venv` before implementation phase
