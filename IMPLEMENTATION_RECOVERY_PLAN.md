## Pending Implementation Snapshot

Date: 2026-03-15

Requested changes queued for implementation:

1. Google cache API usage
- Keep explicit Gemini context caching enabled.
- Tighten SDK calls to the typed config forms documented by Google.
- Preserve the existing cached token confirmation check.

2. Forced knowledge reupload
- Add a separate flag to force re-upload of all role-wide knowledge files.
- Default must remain off.
- Keep this separate from cache invalidation because they solve different problems.

3. Triage interaction reduction
- Add an explicit triage decision mode instead of another boolean.
- Support `prompt`, `follow_ai`, and `always_continue`.
- Switch the local runner to `always_continue` for now.

4. Runner wiring
- Expose the new settings in `runner.config.ps1` and `run_local.ps1`.
- Keep defaults safe: cache reuse on, forced reupload off.

5. Validation
- Add targeted tests for forced reupload and triage mode behavior.
- Run `black .`, `ruff check . --fix`, and `pytest` before finishing.
