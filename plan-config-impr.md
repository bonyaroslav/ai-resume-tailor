## Config Rename Plan

### Goal

Rename the config field `RoleName` to `InputProfile` and shorten the supported
profile folder values to:

- `role_engineer`
- `role_manager`

`JobTitle` stays unchanged and continues to control run-folder separation under
`runs/`.

### Example

```powershell
$RunnerConfig = @{
    CompanyName = "DotLinkers"
    JobTitle = "SRE"
    InputProfile = "role_engineer"
}
```

### Implementation Plan

1. Rename profile folders in `knowledge/`, `prompts/`, and
   `offline_fixtures/` to the shorter values.
2. Update `runner.config.ps1` and `run_local.ps1` to use `InputProfile`.
3. Rename Python settings/helpers from role-based naming to input-profile
   naming and keep the implementation centered on one canonical internal term:
   `input_profile`.
4. Update CLI plumbing, runtime metadata, cache metadata, and printed labels to
   use `input_profile`.
5. Keep compatibility only at read boundaries where needed to avoid unnecessary
   duplication:
   - optional fallback from old run metadata key `role_name`
   - optional fallback from old cache record key `role_name`
6. Update affected tests and documentation.
7. Run `black .`, `ruff check . --fix`, and `pytest`.

### Files Expected To Change

- `runner.config.ps1`
- `run_local.ps1`
- `settings.py`
- `main.py`
- `llm_client.py`
- `graph_nodes.py`
- `knowledge_cache.py`
- `README.md`
- `RUNBOOK_SETUP.md`
- selected planning docs and tests

### Validation Steps

1. Confirm renamed folders resolve correctly.
2. Confirm config-driven run startup still passes the selected input profile.
3. Confirm prompt and knowledge discovery uses the renamed folders.
4. Confirm existing run metadata and cache records still load when they contain
   the legacy `role_name` key.
5. Confirm formatter, linter, and tests pass.
