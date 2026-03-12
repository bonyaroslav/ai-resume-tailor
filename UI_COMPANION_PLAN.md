# UI Companion Plan (Non-Intrusive)

## Goal

Build a very basic, local UI with clean minimalist styling that:
- Shows current run status, model, role, and key settings.
- Lets you pick a JD file and start a run.
- Lets you load existing runs from `runs/`.
- Shows colorful live logs.
- Lets you choose next actions using buttons (resume, continue anyway, regenerate, rebuild, switch variation, edit selected text).
- Stays isolated so the current CLI-first application remains safe.

## What I Investigated (Current Reality)

- Core app entry points are CLI commands in `main.py`: `run`, `resume`, `status`, `regenerate`, `rebuild-output`.
- State is persisted in `runs/<slug>/state_checkpoint.json` and metadata in `runs/<slug>/run_metadata.json`.
- Logs are written to `runs/<slug>/run.log`.
- Workflow states and section ids are stable and explicit (`graph_state.py`, `workflow_definition.py`).
- Roles are folder-based:
  - `prompts/role_senior_dotnet_engineer` (has active prompts)
  - `prompts/role_engineering_manager` (currently placeholder only)
- Model pricing/help source already exists in `ai_model_decision_sheet.md`.

Implication: we can build UI around existing files + commands without changing critical core flow.

## Recommended Architecture

## 1) Isolation Boundary

Create a separate companion app under `ui_app/` with its own dependencies and launcher.

- Keep core app files unchanged by default.
- UI reads/writes run artifacts only (`runs/` + read-only model/help docs).
- UI triggers core behavior via subprocess calls to `python main.py ...`.

## 2) Tech Choice (Recommended)

Use **FastAPI + Jinja2 + HTMX + small CSS theme**.

Why:
- Simple local launch, no Node toolchain required.
- Easy button-based interactivity.
- Styling freedom for a minimalist but polished look.
- Easy polling endpoints for status/logs.

Alternative (faster to prototype, less styling control): Streamlit.

## 3) Process Model

- UI server process handles:
  - run discovery
  - JD file discovery
  - role/prompt discovery
  - model help parsing
  - command execution wrappers
  - checkpoint patch helpers
  - log tailing endpoint

- Core resume-tailor process is still `main.py` commands, called by UI backend.

## Minimal-Change Strategy for Interactivity

Main challenge: CLI review/triage can block on `input()`.

Recommended V1 strategy:
- Run generation non-interactively with env defaults from UI:
  - `ART_AUTO_APPROVE_REVIEW=1`
  - `ART_AUTO_APPROVE_TRIAGE=1`
- Then let UI provide review controls by editing checkpoint and re-running existing commands:
  - Switch selected variation (A/B/C) per section.
  - Edit final selected text.
  - Mark sections for regeneration + note.
  - Continue from `triage_stop` by checkpoint state update + `resume`.

This avoids stdin/pty complexity and avoids invasive core refactors.

## V1 UI Requirements

## A) Main Screen Layout

- Header: app name, current run badge, status badge.
- Left panel: controls/settings.
- Right panel: run state + section cards.
- Bottom panel: live colorful logs.

## B) Controls (Left Panel)

- JD selector:
  - list all files in configurable JD directory (default configurable path).
  - manual file picker path input.
- Run selector:
  - list folders from `runs/`.
  - load selected run.
- Settings:
  - model dropdown.
  - role dropdown (`role_senior_dotnet_engineer`, `role_engineering_manager`, etc.).
  - company name input.
  - debug toggle.
- Actions:
  - `Start New Run`
  - `Resume`
  - `Refresh Status`
  - `Rebuild Output`
  - `Continue Anyway` (for triage stop)

## C) Help Near Model

Add a small `?` button near model selector that opens a modal with:
- Model table parsed from `ai_model_decision_sheet.md`.
- Pricing intervals/threshold notes (for long prompts/context thresholds).
- Free-tier caveats and reminders.
- Quick recommendation labels (cheap default, quality default, premium escalation).
- Last updated date from the MD file.

## D) Prompt/Role Visibility

Show:
- Available role folders from `prompts/`.
- For selected role, list active prompt files (`*.md`, excluding `*.example.md`).
- Visual warning if role has no active prompt set (currently engineering manager).

## E) Section Interaction

For each generated section:
- Show current status and retry count.
- Show variations with score and reasoning preview.
- Buttons:
  - `Use A/B/C...`
  - `Edit Selected`
  - `Regenerate Section`
- Regeneration requires note input.

## F) Logs Window

- Auto-refresh tail of `run.log`.
- Color by level:
  - INFO neutral/blue
  - WARNING amber
  - ERROR red
- Filter controls:
  - level filter
  - section id filter
  - text search

## Back-End Contract (UI Companion)

Suggested endpoints/services:
- `GET /api/catalog/jds` -> list JD files.
- `GET /api/catalog/runs` -> list run folders.
- `GET /api/catalog/roles` -> list role folders + prompt health.
- `GET /api/models/help` -> parsed model decision sheet.
- `GET /api/run/{run_id}/status` -> checkpoint + metadata summary.
- `GET /api/run/{run_id}/sections` -> section cards with variations.
- `GET /api/run/{run_id}/logs?offset=N` -> incremental log tail.
- `POST /api/run/start` -> start new run (`main.py run`).
- `POST /api/run/{run_id}/resume` -> `main.py resume`.
- `POST /api/run/{run_id}/rebuild` -> `main.py rebuild-output`.
- `POST /api/run/{run_id}/continue-anyway` -> patch checkpoint triage-stop to generation state.
- `POST /api/run/{run_id}/section/{section_id}/select` -> patch selected variation/content.
- `POST /api/run/{run_id}/section/{section_id}/edit` -> patch selected custom text.
- `POST /api/run/{run_id}/regenerate` -> patch retry_requested + note, then `main.py resume`.

## Data Safety Rules

- Never store new sensitive data outside `runs/`.
- UI uses existing redacted logs; do not display raw payload dumps unless debug is explicitly enabled.
- Keep checkpoint edits schema-aware and minimal.

## UX Flow (V1)

1. User picks JD file + model + role + company.
2. User clicks `Start New Run`.
3. UI shows live status and logs while run executes.
4. When completed, section cards show generated variations.
5. User optionally changes selected variation or edits text.
6. User clicks `Rebuild Output`.
7. If quality is low, user picks sections + note and clicks `Regenerate`.

## Launch & Dev Experience

- Keep separate dependencies in `ui_app/requirements-ui.txt`.
- Add one launcher script: `run_ui.ps1`.
- Keep core startup unchanged (`python main.py ...` still works exactly as today).

## Implementation Phases

## Phase 1 (Safe Dashboard + Actions)

- Build read-only status/dashboard + logs + start/resume/rebuild actions.
- Add model help modal from MD file.
- No checkpoint mutation yet.

## Phase 2 (Interactive Section Controls)

- Add section cards and variation selection/edit controls.
- Add regenerate selected sections with note.
- Add triage stop `Continue Anyway`.

## Phase 3 (Polish)

- Better visual style system (spacing, typography, subtle motion).
- Presets for models and throughput.
- Keyboard shortcuts.

## Decisions You Need To Make

1. UI stack:
   - FastAPI + Jinja + HTMX (recommended)
   - Streamlit (faster, less design freedom)
2. JD source location:
   - fixed folder (for example `job_descriptions/`)
   - configurable path in UI settings file
3. Review mode:
   - run fully non-interactive then edit checkpoint in UI (recommended)
   - build stdin-driven live CLI interaction bridge (more complex)
4. Model help source:
   - parse `ai_model_decision_sheet.md` directly (recommended)
   - maintain separate JSON snapshot for UI
5. Scope of V1:
   - include section variation switching/editing now
   - defer section edits and ship status/actions first
6. Run naming:
   - keep company-slug behavior
   - add optional suffix field in UI for parallel runs

## Constructive Criticism (Design Review Findings)

1. Checkpoint mutation is the highest-risk area.
   - Current plan includes direct state patching for selection/edit/regenerate/continue-anyway.
   - Risk: invalid `GraphState` transitions or partially-updated state.
   - Mitigation: implement one `state_transition.py` helper in UI backend that:
     - validates all updates via `GraphState.model_validate(...)`
     - enforces allowed transitions only
     - writes atomically (temp file then replace), mirroring checkpoint behavior.

2. Missing run-level locking policy.
   - Risk: user clicks multiple actions while subprocess is running; races with checkpoint/log writes.
   - Mitigation: add per-run mutex (`run_id` lock) + `run_busy` flag, disable action buttons while busy.

3. Role readiness must be preflight-blocked.
   - `role_engineering_manager` currently has no active prompt set.
   - Risk: user starts run and fails late.
   - Mitigation: preflight checks before start/resume:
     - all required prompt files exist
     - template path exists
     - role knowledge directory exists.

4. Markdown parsing for model help is brittle by default.
   - Risk: table format changes break UI parser.
   - Mitigation: parser with strict fallback behavior:
     - if parse fails, render plain markdown block
     - show warning badge `Unparsed model sheet`.

5. Acceptance criteria need measurable checks.
   - Risk: “done” is subjective.
   - Mitigation: add concrete success metrics (below).

## Decision Tradeoffs and "Price You Pay"

## 1) UI Stack

- FastAPI + Jinja + HTMX (recommended)
  - Why recommended: best control/maintainability while staying Python-only and local.
  - Price you pay:
    - more engineering effort than Streamlit.
    - you own endpoint and template wiring.
- Streamlit
  - Benefit: fastest prototype.
  - Price you pay:
    - weaker UI layout precision and state-flow control.
    - harder to evolve into richer interaction patterns without rework.

## 2) JD Source Location

- Configurable JD path (recommended)
  - Why recommended: matches your real workflow with external JD files and future flexibility.
  - Price you pay:
    - one settings mechanism + path validation.
- Fixed folder
  - Benefit: very simple implementation.
  - Price you pay:
    - friction when JDs are not in that folder.

## 3) Review Mode

- Non-interactive run + UI state edits (recommended)
  - Why recommended: keeps core CLI untouched; avoids stdin/pty complexity.
  - Price you pay:
    - strict checkpoint safety discipline is mandatory.
- Live stdin bridge into CLI
  - Benefit: closer to existing review loop semantics.
  - Price you pay:
    - high complexity and fragility on Windows.
    - harder debugging and lower maintainability.

## 4) Model Help Source

- Parse `ai_model_decision_sheet.md` directly (recommended for V1)
  - Why recommended: single source of truth, no duplication drift.
  - Price you pay:
    - parser maintenance when markdown structure changes.
- Separate JSON snapshot
  - Benefit: robust UI parsing.
  - Price you pay:
    - duplicated source and sync responsibility.

## 5) V1 Scope

- Status/actions first, section edit/select in Phase 2 (recommended)
  - Why recommended: de-risks architecture and locking before mutation-heavy features.
  - Price you pay:
    - less interactive power in first release.
- Full interaction in V1
  - Benefit: faster feature completeness.
  - Price you pay:
    - higher regression risk and longer stabilization.

## 6) Run Naming

- Keep company slug + optional suffix (recommended)
  - Why recommended: preserves current behavior but allows parallel experiments.
  - Price you pay:
    - slightly more UI complexity.
- Keep company slug only
  - Benefit: simplest.
  - Price you pay:
    - accidental overwrite/reuse confusion for experiments.

## Added Non-Functional Requirements (to reduce hidden cost)

1. State integrity:
   - every mutation path must validate checkpoint schema before save.
2. Idempotent actions:
   - repeated button clicks should not corrupt state.
3. Concurrency control:
   - one run can have only one active write/action at a time.
4. Failure clarity:
   - UI must surface command stderr and actionable recovery hint.
5. Privacy:
   - do not add new raw prompt/response persistence outside existing debug behavior.

## Go/No-Go Metrics per Phase

## Phase 1 Go Criteria

- Start run success rate >= 95% over 20 local attempts (mixed roles/models).
- Status refresh reflects checkpoint updates within <= 2 seconds.
- Log tail latency <= 2 seconds.
- No core files modified outside UI app and launcher files.

## Phase 2 Go Criteria

- 100% checkpoint edits pass schema validation before write.
- No invalid transition incidents in 20 interaction scenarios:
  - select/edit/regenerate/continue-anyway while idle/busy states.
- Regenerate flow preserves retry notes and queue consistency.

## Phase 3 Go Criteria

- Visual polish does not introduce functional regressions from Phase 2.
- Keyboard shortcuts are optional and non-blocking.

## Acceptance Criteria (V1)

- Core CLI behavior is unchanged.
- UI launches with one local command.
- User can start a run from JD picker.
- User can load existing runs and see status/settings.
- User can view colorful logs.
- User can trigger next actions with buttons.
- Model help modal shows prices/interval notes from your MD sheet.

