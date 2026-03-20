# Cleanup Plan

## Objective

Reduce root-level clutter, keep the repository easier to scan, and preserve only files that support day-to-day development or project evaluation.

## Scope

This cleanup keeps runtime code and active assets in place while:

1. removing tracked machine-specific folders
2. moving historical planning/reference documents under `docs/`
3. deleting local cache and temp folders that can be regenerated

## Decisions

1. Keep the Python modules flat at the repository root for now.
2. Keep `README.md`, `RUNBOOK_SETUP.md`, and `AGENTS.md` at the root.
3. Move completed or historical planning docs to `docs/archive/`.
4. Move secondary reference docs to `docs/reference/`.
5. Do not delete role/profile content unless it is clearly unused and explicitly approved.

## Planned Actions

1. Update `.gitignore` to ignore `.idea/` and `.black-cache/`.
2. Create `docs/archive/` and `docs/reference/`.
3. Move these files to `docs/archive/`:
   - `PLAN.MD`
   - `plan-audit-markdown-contract.md`
   - `plan-audit-step.md`
   - `plan-cache.md`
   - `plan-config-impr.md`
   - `plan-prompts-optimization.md`
   - `plan-skills.md`
   - `UI_COMPANION_PLAN.md`
4. Move these files to `docs/reference/`:
   - `ai_model_decision_sheet.md`
   - `REQUIREMENTS.md`
5. Delete tracked local-artifact folders:
   - `.idea/`
   - `.black-cache/`
6. Delete local cache/temp folders if present:
   - `__pycache__/`
   - `.pytest_cache/`
   - `.pytest_tmp/`
   - `.ruff_cache/`
   - `pytest-cache-files-*`
   - `tests/__pycache__/`
   - `tests/_tmp_pytest_run_*`
   - `tests/.tmp/`

## Verification

1. Run `black .`
2. Run `ruff check . --fix`
3. Confirm the new root layout is smaller and that docs were moved as expected.
