# Plan: Role-Wide Knowledge Cache

## Goal

Reduce repeated Gemini input spend by creating one explicit cache per active role and reusing it across all requests in a run.

Scope for this plan:
- cache only `knowledge_files` referenced by active non-`.example` prompt files
- create or reuse the cache before triage
- remove inlined knowledge text from request prompts when cache is active
- require observable proof in logs that the cache exists and is actually used

Out of scope for this plan:
- JD caching
- per-section caches
- Batch API
- prompt body caching

## Constructive Criticism Of The Earlier Plan

### What was good

- It identified the correct cost problem: repeated shared context is being resent on every request.
- It separated file upload reuse from cache reuse, which is the right mental model.
- It required API-level confirmation instead of trusting local state.

### What was too complex

- It mixed too many concerns into V1:
  - file registry lifecycle
  - cache registry lifecycle
  - prompt fingerprinting
  - model-specific invalidation
  - hard fail policy
  - optional future JD caching
- It suggested broad dependency fingerprints tied to prompt structure. That risks frequent invalidations without proportional value if the cache stores only knowledge files.
- It left room for multiple cache groups. That is unnecessary for the first implementation and makes debugging harder.

### What should be simpler

- Use one role-wide cache, not multiple cache groups.
- Fingerprint only what affects cached content:
  - role name
  - model name
  - sorted unique knowledge file paths
  - content hashes of those files
- Keep prompt body changes out of cache invalidation unless they change `knowledge_files`.
- Start with one local registry file and one remote cache per role/model/knowledge-set.
- Do not try to optimize JD reuse in the same change.

### Main tradeoff of the simpler plan

One role-wide cache may be slightly larger than some individual section requests need. That is acceptable for V1 because:
- the role has only 8 unique knowledge files
- the unique total is about 81K chars, which is manageable
- the operational simplicity is much more important than marginal over-optimization

## Simplified Design

### High-level behavior

When the app launches for a role such as `role_senior_dotnet_engineer`:

1. Discover all active prompt templates for the role.
2. Read all `knowledge_files` from non-`.example` prompt files.
3. Build one sorted unique set of knowledge files.
4. Compute a role-wide cache fingerprint from those files.
5. Before triage, either:
   - reuse an existing valid cache, or
   - upload missing files and create a fresh cache.
6. Confirm the cache exists through the API.
7. Use that cache on every Gemini request in the run.
8. Do not inline knowledge file contents into prompts while cache mode is enabled.
9. Log both:
   - cache creation/reuse events
   - per-request `usage_metadata`, especially cached token counts

## Operator Controls

Use `runner.config.ps1` as the main place to control behavior.

Add settings:
- `UseRoleWideKnowledgeCache = $true`
- `InvalidateRoleWideKnowledgeCache = $false`
- `RequireCachedTokenConfirmation = $true`
- `KnowledgeCacheTtlSeconds = 3600`
- `KnowledgeCacheRegistryPath = ".\\runs\\_cache\\role_wide_knowledge_cache_registry.json"`

`run_local.ps1` should map these into env vars or CLI flags.

Recommended runtime controls:
- env: `ART_USE_ROLE_WIDE_KNOWLEDGE_CACHE=1`
- env: `ART_REQUIRE_CACHED_TOKEN_CONFIRMATION=1`
- env: `ART_KNOWLEDGE_CACHE_TTL_SECONDS=3600`
- CLI flag: `--invalidate-cache`

The invalidate flag should be off by default.

## Data Model

Create one small local registry file under `runs/_cache/`.

Suggested stored fields:
- `role_name`
- `model_name`
- `fingerprint`
- `knowledge_files`
  - `path`
  - `sha256`
  - `remote_file_name`
  - `remote_file_uri`
  - `uploaded_at`
- `cache`
  - `remote_cache_name`
  - `created_at`
  - `expires_at`
  - `model_name`
  - `fingerprint`

## Cache Fingerprint

Use a stable fingerprint built from:
- role name
- model name
- sorted unique knowledge file relative paths
- sha256 of each knowledge file content

Do not include:
- prompt body text
- JD text
- company name
- run id

Reason:
- this cache is only for role-wide knowledge files
- prompt wording can change without changing cached knowledge content

## Execution Flow

### Step 1: Discover active knowledge files

Before triage:
- call existing prompt discovery
- collect all `knowledge_files` from active non-example prompts
- deduplicate and sort them

Expected current result for `role_senior_dotnet_engineer`:
- 8 unique files

### Step 2: Resolve reuse vs rebuild

If `--invalidate-cache` is passed:
- ignore any reusable local cache metadata
- create a fresh cache

Otherwise:
- load registry
- look for matching `role_name`, `model_name`, and `fingerprint`
- if present, confirm through Gemini API that:
  - cache exists
  - cache is not expired
- if valid, reuse it

If invalid:
- rebuild

### Step 3: Upload missing files

For each knowledge file in the unique set:
- if registry has a reusable remote file object for the same path and hash, reuse it
- otherwise upload the file

This avoids reuploading files on repeated launches within their reuse window.

### Step 4: Create the role-wide cache

Create one explicit cache from the uploaded file references.

Set TTL from configuration.

Then immediately fetch the cache from API and log:
- cache name
- model
- create time
- expire time

### Step 5: Store/update registry

Persist:
- remote uploaded file references
- cache metadata
- fingerprint used

### Step 6: Use cache for all requests

Every Gemini request in the run should receive the same `cached_content` reference:
- triage
- professional summary
- skills alignment
- all experience sections
- cover letter

### Step 7: Stop inlining knowledge files into prompts

When role-wide cache mode is enabled:
- do not append knowledge file contents to the prompt text
- prompt should only contain:
  - prompt body
  - runtime input
  - retry note if present

This is the main functional behavior change that actually reduces repeated input tokens.

## Logging Requirements

### Prewarm logs

Log once per run:
- role name
- model name
- active prompt file count
- unique knowledge file count
- knowledge file names and hashes
- cache fingerprint
- cache mode enabled/disabled
- cache reuse or cache rebuild
- per-file upload reused or uploaded fresh
- remote cache name
- cache expiry

### Request logs

For every Gemini request, log:
- section id
- cached content name used
- prompt chars sent
- `prompt_token_count`
- `cached_content_token_count`
- `candidates_token_count`
- `thoughts_token_count`
- `total_token_count`

If cached token confirmation is required and `cached_content_token_count <= 0`:
- fail fast with a clear error

## Failure Policy

Recommended behavior:
- if cache mode is enabled and prewarm fails, abort before triage
- if cache exists but request usage metadata does not confirm cache use, abort when confirmation is required
- do not silently fall back to inline knowledge prompts unless the operator explicitly disables cache mode

Reason:
- silent fallback would hide spend regressions

## Files To Change

Likely code areas:
- `runner.config.ps1`
- `run_local.ps1`
- `main.py`
- `prompt_loader.py`
- `llm_client.py`
- `graph_nodes.py`
- new module: `knowledge_cache.py`

Recommended separation:
- `knowledge_cache.py`
  - discover unique role knowledge files
  - compute fingerprint
  - registry read/write
  - upload/reuse remote files
  - create/reuse remote cache
  - confirm cache exists

## Test Plan

### Unit tests

1. Active prompt discovery excludes `.example.md` files.
2. Unique role-wide knowledge file collection is deduplicated and sorted.
3. Fingerprint changes when a knowledge file content changes.
4. Fingerprint changes when `knowledge_files` frontmatter changes.
5. Fingerprint does not change when prompt body text changes without changing knowledge references.
6. Prompt building skips inline knowledge text when cache mode is enabled.
7. Prompt building keeps current behavior when cache mode is disabled.
8. Registry reuse works when fingerprint and expiry are valid.
9. Registry is ignored when `--invalidate-cache` is set.

### Mocked integration tests

1. Cache prewarm runs before triage.
2. Unique files are uploaded once, not once per section.
3. One remote cache is created for the role and reused across all section requests.
4. All Gemini requests receive `cached_content`.
5. No request inlines knowledge file content when cache mode is enabled.
6. Usage metadata is logged for every request.
7. Run fails if cached token confirmation is required and API reports zero cached tokens.
8. Repeated launches reuse existing valid cache without reuploading files.

## Implementation Order

### Phase 1: Configuration and discovery

- add config/env/CLI switches
- add unique role-wide knowledge-file discovery
- add fingerprint computation

### Phase 2: Registry and prewarm

- add local registry
- add file upload reuse
- add cache creation/reuse
- add API confirmation logging

### Phase 3: Request integration

- pass cache reference through runtime context
- stop inlining knowledge in prompts when cache mode is enabled
- attach cached content to all Gemini requests

### Phase 4: Token confirmation

- read `usage_metadata`
- add request token logs
- fail fast when configured and cache is not actually used

### Phase 5: Tests and operator verification

- unit tests
- mocked integration tests
- manual verification against logs for:
  - cache creation
  - cache reuse
  - nonzero cached token count

## Recommendation

Proceed with the simplified one-role-wide-cache plan.

This is the best balance of:
- simplicity
- operational reliability
- immediate cost reduction
- future extensibility

Do not add JD caching or per-section caches in the same implementation. Those are separate optimizations and would make the first version harder to validate.
