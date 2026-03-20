# Plan: Prompt + Job Description File Optimization

## Objective

Change the prompt and cache flow so the job description is always treated as a run-local Markdown file named `job_description.md`, uploaded fresh at the start of every run, then reused through cached content for all requests in that run.

Keep reusable knowledge files cached across runs and companies unless the operator explicitly asks to refresh them.

## Locked Decisions

1. Operator-facing JD input support is only `.txt` and `.md`.
2. The run-local persisted JD artifact is always `runs/<run_id>/job_description.md`.
3. No inline JD body remains in prompts.
4. All prompts should refer to the same logical file name: `job_description.md`.
5. `job_description.md` must be uploaded fresh at the start of every run.
6. `job_description.md` must not be reused from prior runs, even if content matches.
7. Stable knowledge files should be reused across runs unless the operator explicitly requests refresh.
8. If the remote cached content used by a run has expired, it should be recreated at startup before any model request.
9. Prompt headers should include a short attached-files section and may label `job_description.md` as `Source of truth`.
10. Keep the implementation simple. Do not add provider abstractions, multiple cache group types, or prompt frontmatter changes for the JD.

## Desired Runtime Behavior

### Run start

When `python main.py run --jd-path <file.txt|file.md> ...` starts:

1. Read the supplied JD file as plain text.
2. Persist that exact text into `runs/<run_id>/job_description.md`.
3. Discover active prompt templates and their stable `knowledge_files`.
4. Resolve reusable remote file handles for stable knowledge files from the local registry.
5. Upload a fresh remote file for `runs/<run_id>/job_description.md`.
6. Create one run-scoped cached content object that includes:
   - the stable knowledge files
   - that run's fresh `job_description.md`
7. Confirm the cached content exists and is not expired.
8. Use that cached content for triage and all subsequent generation requests in the run.

### Resume / regenerate / rebuild-output

When resuming an existing run:

1. Load `runs/<run_id>/job_description.md`.
2. At startup, check whether the run-scoped cached content still exists and is unexpired.
3. If valid, reuse it.
4. If expired or missing, recreate it using:
   - reusable stable knowledge file handles where available
   - a fresh upload of the existing run-local `job_description.md`
5. Continue the workflow using the recreated run-scoped cached content.

### Cross-run behavior

For different companies and different job descriptions:

1. Stable knowledge files should be reused across runs when hashes match and the operator did not request refresh.
2. `job_description.md` must always be uploaded fresh for each new run.
3. Each run should get its own cached content object because the JD differs per run.

## Example Prompt Shape

All prompt bodies should effectively start with a runtime-injected header like:

```md
## Attached Files

- `job_description.md` - Source of truth
- `profile_technical_skills_matrix.md`
- `constraints_legal_and_location_blockers.md`

Use `job_description.md` as the primary source of truth for role requirements, responsibilities, constraints, and stated expectations.
```

Then continue with the existing prompt body.

Notes:
- Do not inline the full JD text.
- Do not describe other files as "Candidate background".
- Keep the wording short and consistent across all prompts.

## Why This Design

### Benefits

1. Prompt text becomes smaller and more stable because the JD body is no longer repeated on every request.
2. The JD is treated as a first-class attached source rather than an unbounded inline block.
3. Prompt instructions can consistently refer to one canonical file name: `job_description.md`.
4. Stable knowledge file uploads can still be amortized across runs.
5. Each run gets fresh JD data, which reduces the risk of stale or wrong target context.

### Costs

1. Each run still requires creation of a fresh cached content object because the JD is per-run.
2. There is one extra uploaded file per run for `job_description.md`.
3. Resume must be able to recreate the run cache if the remote cache expires.

### Non-goals

1. Do not support `.docx` JD input in this change.
2. Do not reuse JD uploads across runs.
3. Do not add a generic cache engine.
4. Do not edit every prompt file manually if runtime injection can produce the same behavior.

## Architecture Changes

## 1. JD ingestion and run artifact contract

### Current behavior

- `main.py` reads the JD and persists it as `job_description.txt`.
- resume/regenerate/rebuild read `job_description.txt`.
- the prompt builder injects the full JD body inline.

### New behavior

- `read_job_description()` accepts only `.txt` and `.md`.
- `main.py` writes the loaded text into `runs/<run_id>/job_description.md`.
- resume/regenerate/rebuild read `job_description.md`.
- no prompt builder path should inject the JD body inline.

### Simplicity rule

Treat `.txt` and `.md` the same at load time:
- read the file contents as UTF-8 text
- store the contents into the run-local Markdown file

No conversion logic is needed.

## 2. Prompt construction

### Current behavior

`build_prompt_text()` assembles:
- prompt body
- optionally inline knowledge text
- runtime company name
- runtime JD body
- retry note

### New behavior

`build_prompt_text()` should assemble:
- attached-files header
- prompt body
- company name
- retry note

It should not include:
- inline JD body
- a `Job Description:` block with raw text

### Attached-files header source

The attached-files header should be generated at runtime from:
- fixed JD file name: `job_description.md`
- prompt template `knowledge_files`

This avoids manual duplication across prompt templates and keeps the prompt contract consistent.

### Prompt wording guidance

Use one short line that explicitly assigns meaning to the JD:
- `Use job_description.md as the source of truth for the target role.`

Avoid long explanations or repeated caveats in every prompt.

## 3. Cache model

## Split the current single concept into two practical layers

### Layer A: reusable remote file records for stable knowledge files

Purpose:
- reuse uploaded remote file handles for prompt knowledge files across runs

Properties:
- keyed by file path + content hash
- reused unless operator forces reupload
- independent of company and JD

### Layer B: run-scoped cached content object

Purpose:
- provide one cached content reference for all model requests in a run

Contents:
- stable knowledge file parts
- one fresh `job_description.md` part for the current run

Properties:
- specific to one run
- created at run start if missing or expired
- reused only within that run

### Why this split is necessary

If the JD is included in the same reuse fingerprint as stable knowledge files, cross-run cache reuse collapses. The correct simplification is:

1. reuse stable uploaded knowledge files across runs
2. rebuild the run cache around a fresh JD for each run

That preserves the exact behavior requested.

## 4. Cache lifecycle rules

### Stable knowledge files

Rules:
- discover from active prompt templates only
- deduplicate and sort
- compute file sha256
- reuse prior remote uploads when hash matches
- upload fresh only when:
  - no matching reusable record exists
  - remote file confirmation fails
  - operator explicitly requests knowledge refresh

### Job description file

Rules:
- path is always `runs/<run_id>/job_description.md`
- upload fresh at every run start
- do not attempt cross-run reuse
- on resume, reupload if run cache must be recreated

### Run-scoped cached content

Rules:
- create before triage or any generation request
- store remote cache name in the run context
- confirm existence and expiration at startup
- recreate if expired, deleted, or otherwise unavailable

## 5. Registry design

Keep one local registry file under `runs/_cache/`.

The registry should store enough information for two reuse cases:

### Reusable knowledge-file records

Suggested fields:
- `path`
- `sha256`
- `remote_file_name`
- `remote_file_uri`
- `mime_type`
- `uploaded_at`

These records are reusable across runs.

### Run cache records

Suggested fields:
- `run_id`
- `input_profile`
- `model_name`
- `job_description_path`
- `job_description_sha256`
- `knowledge_files`
- `cache.remote_cache_name`
- `cache.created_at`
- `cache.expires_at`

These records are specific to a run.

### Important design constraint

Do not key run cache reuse off company name alone.
Key it off run identity and actual JD content metadata.

## 6. Startup flow

### New run

1. Create run directory.
2. Read input JD from `.txt` or `.md`.
3. Persist `runs/<run_id>/job_description.md`.
4. Build runtime context.
5. Discover active prompt templates and stable knowledge files.
6. Check whether this run already has a valid cached content record.
7. If not:
   - resolve/reuse stable knowledge file uploads
   - upload fresh `job_description.md`
   - create run-scoped cached content
8. Confirm cached content exists.
9. Proceed to triage.

### Resume existing run

1. Load `runs/<run_id>/job_description.md`.
2. Check the run's cached content record.
3. If valid, reuse it.
4. If invalid or expired:
   - resolve/reuse stable knowledge file uploads
   - upload fresh `job_description.md`
   - recreate the run cache
5. Continue execution.

## 7. Command and operator semantics

### Existing flag

`--force-knowledge-reupload`

### Required behavior after this change

It should affect only stable knowledge files.

It should not change JD behavior because the JD is always uploaded fresh anyway.

### Invalidate-cache behavior

`--invalidate-cache` should mean:
- ignore existing run-scoped cached content for this run
- recreate it before requests

It should not imply forced reupload of stable knowledge files unless combined with `--force-knowledge-reupload`.

## Module-Level Implementation Plan

## `job_description_loader.py`

Change:
- accept `.txt` and `.md`
- reject other suffixes

Keep:
- simple text read behavior
- no normalization beyond reading file text

Tests:
- `.txt` accepted
- `.md` accepted
- `.docx` rejected
- missing file rejected

## `main.py`

Change:
- persist run-local JD as `job_description.md`
- load `job_description.md` on resume/regenerate/rebuild
- update any status/help text that currently says `.docx`

Also:
- trigger run-cache confirmation/recreation at startup for `run`, `resume`, and `regenerate`

## `prompt_loader.py`

Change `build_prompt_text()` so it:
- injects an attached-files header
- always includes `job_description.md`
- labels only `job_description.md` as `Source of truth`
- does not include `Job Description:` raw body

Prefer:
- one helper that builds the attached-files section from the known JD file name and `knowledge_files`

Do not:
- add JD references into prompt frontmatter
- require editing every prompt file by hand

## `knowledge_cache.py`

Refactor responsibilities into explicit steps:

1. discover stable knowledge files from prompts
2. compute reusable stable-file descriptors
3. reuse or upload stable knowledge files
4. upload fresh run-local JD file
5. create or confirm run-scoped cached content
6. persist registry updates

Recommended helper split:
- discover stable knowledge files
- load/write registry
- find reusable stable remote file
- confirm remote file
- upload JD fresh
- find run cache record
- confirm run cache
- create run cache

Keep the code explicit and file-oriented. Do not build a generic cache manager abstraction.

## `graph_nodes.py`

No business logic change is needed for generation itself if the runtime context still exposes a single `cached_content_name`.

Required changes:
- prompt text no longer relies on inline JD
- all requests continue to use the run cache reference

## `README.md` / `RUNBOOK_SETUP.md` / related docs

Update:
- supported JD input types
- stored run artifact name
- high-level explanation that the JD is uploaded as `job_description.md` and reused within the run

## Testing Plan

## Unit tests

### JD loader

1. `.txt` is accepted.
2. `.md` is accepted.
3. `.docx` is rejected.
4. unsupported extension error message is updated accordingly.

### Prompt builder

1. Attached-files header includes `job_description.md`.
2. `job_description.md` is labeled `Source of truth`.
3. knowledge files are listed after it.
4. raw JD body is absent from the prompt.
5. retry note still works.
6. prompt still works when there are no knowledge files.

### Cache registry / file reuse

1. Stable knowledge files are deduplicated and sorted.
2. Stable knowledge file hash changes trigger reupload.
3. Stable knowledge files are reused across runs when hashes match.
4. `--force-knowledge-reupload` bypasses stable-file reuse.
5. JD file is always uploaded fresh.
6. run cache recreation reuses stable knowledge files but uploads a fresh JD.
7. expired run cache is recreated.
8. missing remote cache is recreated.

## Mocked integration tests

1. New run creates `job_description.md` in the run folder.
2. Triaging and generation use cached content without inline JD body.
3. Two different runs with different JDs:
   - reuse stable knowledge remote files
   - create different run-scoped cached content objects
4. Resume recreates expired run cache and continues.
5. `invalidate-cache` recreates the run cache.
6. `force-knowledge-reupload` reuploads stable knowledge files but still follows normal JD fresh upload behavior.

## Logging Requirements

Log enough metadata to prove behavior without logging raw JD text.

### Startup logs

Required:
- JD run path
- JD char count
- JD sha256 short
- stable knowledge file count
- stable knowledge file reuse vs upload decisions
- JD fresh upload event
- run cache create/reuse/recreate decision
- remote cache name
- cache expiry

### Request logs

Keep existing usage logging and include:
- cached content name
- prompt char count
- cached token count if available

Do not log the full JD body.

## Risks and Mitigations

### Risk 1: prompts become weaker after removing inline JD

Mitigation:
- make the attached-files header explicit
- add one short sentence declaring `job_description.md` as source of truth

### Risk 2: run cache recreation path is incomplete

Mitigation:
- centralize startup cache preparation in one place used by `run`, `resume`, and `regenerate`

### Risk 3: stale remote cache survives in registry

Mitigation:
- always confirm remote cache existence and expiration through API before reuse

### Risk 4: stable knowledge reuse accidentally becomes run-specific

Mitigation:
- keep stable file reuse records independent from run cache records

### Risk 5: implementation drifts into unnecessary abstraction

Mitigation:
- keep explicit helper functions in `knowledge_cache.py`
- avoid base classes, registries, or orchestration layers

## Acceptance Criteria

1. JD input supports `.txt` and `.md` only.
2. Every run persists its JD as `runs/<run_id>/job_description.md`.
3. No prompt contains the raw inline JD body.
4. Every prompt references `job_description.md` in an attached-files header.
5. `job_description.md` is uploaded fresh at the start of every run.
6. Stable knowledge files are reused across runs unless explicitly refreshed.
7. One run-scoped cached content object is reused across all model requests in the same run.
8. If that run cache is expired or missing, it is recreated at startup.
9. Resume/regenerate continue to work with the run-local `job_description.md`.
10. Documentation and tests are updated.

## Implementation Order

### Phase 1: JD artifact contract

- update JD loader suffix support
- write/read `job_description.md` in run flows
- update docs and tests for the new contract

### Phase 2: Prompt rewrite

- add runtime attached-files header generation
- remove inline JD body
- update prompt-builder tests

### Phase 3: Cache split

- preserve stable knowledge file reuse across runs
- add explicit fresh JD upload
- create run-scoped cached content from both inputs

### Phase 4: Resume and expiration behavior

- confirm run cache at startup
- recreate expired or missing run cache
- ensure same behavior for `run`, `resume`, and `regenerate`

### Phase 5: Verification

- run `black .`
- run `ruff check . --fix`
- run `pytest`

## Execution Notes For A Separate Session

Start implementation with the smallest contract changes first:

1. switch run artifact path from `job_description.txt` to `job_description.md`
2. update prompt building so inline JD is gone
3. then refactor cache handling

This ordering keeps failures easier to isolate and makes it possible to verify prompt changes before touching cache recreation logic.

