<div align="center">
  <h1>AI Resume Tailor Setup Runbook</h1>
  <p>Fast onboarding for new users: <b>offline smoke run</b> then <b>real Gemini run</b>.</p>
</div>

## 1. Prerequisites

- Windows PowerShell (project commands below use PowerShell).
- Python 3.10+ installed.
- Repo cloned locally.

## 2. Project bootstrap

```powershell
cd C:\Projects\ai-resume-tailor
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 3. Google AI Studio registration and API key

1. Open Google AI Studio: `https://aistudio.google.com/`
2. Sign in and accept terms.
3. Open `Dashboard -> Projects`.
4. Create a project or import an existing Google Cloud project.
5. Open `Dashboard -> API Keys`.
6. Create an API key and copy it.

## 4. Free-tier guardrails (recommended)

1. Keep testing on `gemini-2.5-flash` unless you explicitly need another model.
2. Check current rate limits before load testing.
3. Keep early smoke runs small (1 JD at a time).
4. Do not enable Cloud Billing unless you intentionally want paid tier.

## 5. Offline smoke run (no network)

Use this first to validate workflow, logs, checkpointing, and DOCX output end-to-end.

```powershell
$env:ART_OFFLINE_MODE="1"
$env:ART_AUTO_APPROVE_REVIEW="1"
.\.venv\Scripts\python.exe main.py run --jd-path .\inputs\job_description.txt --company "Offline Smoke"
```

`--jd-path` supports `.txt` and `.docx`.

Expected artifacts under `runs/<run_id>/`:

- `run.log`
- `state_checkpoint.json`
- `tailored_cv.docx`
- `cover_letter.txt`

## 6. Real Gemini run (AI Studio key)

```powershell
$env:GEMINI_API_KEY="PASTE_YOUR_KEY"
Remove-Item Env:ART_OFFLINE_MODE -ErrorAction SilentlyContinue
Remove-Item Env:ART_AUTO_APPROVE_REVIEW -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe main.py run --jd-path .\inputs\job_description.txt --company "Target Company"
```

### One-command local runner (recommended)

Use the built-in runner so you do not re-enter API key, company, or JD path every time.

1. Copy `secrets\gemini_api_key.example.txt` to `secrets\gemini_api_key.txt`.
2. Put your real Gemini API key in `secrets\gemini_api_key.txt` (this path is gitignored).
3. Edit `runner.config.ps1` once:
   - `JobDescriptionPath`
   - `CompanyName`
   - `ModelName` (optional, default shown is `gemini-2.5-flash`)
4. Run:

```powershell
.\run_local.ps1
```

This executes: project cd, dependency install, API key load from file, optional Gemini health check, and `main.py run`.

### Model selection (where to change)

You can choose model in your local app, not only in Google AI Studio:

- `runner.config.ps1` -> `ModelName`
- CLI -> `--model`
- env var -> `$env:GEMINI_MODEL="..."`
- code default -> `DEFAULT_MODEL` in `main.py`

Google AI Studio controls account access, quotas, and billing, but model choice is set by this project.

## 7. Resume a paused run

```powershell
.\.venv\Scripts\python.exe main.py resume --run-path .\runs\<company-slug>
# or
.\.venv\Scripts\python.exe main.py resume --checkpoint-path .\runs\<company-slug>\state_checkpoint.json
```

Run folders are reused by company slug (example: `runs\mindera`).
If you want a separate run, use a unique company value, for example `"Mindera-v2"`.

## 8. Status, targeted regenerate, and rebuild

```powershell
.\.venv\Scripts\python.exe main.py status --run-path .\runs\<company-slug>
.\.venv\Scripts\python.exe main.py regenerate --run-path .\runs\<company-slug> --sections section_professional_summary,doc_cover_letter --note "add clearer measurable outcomes"
.\.venv\Scripts\python.exe main.py rebuild-output --run-path .\runs\<company-slug>
```

## 9. Troubleshooting quick checks

- `Missing GEMINI_API_KEY`: set `$env:GEMINI_API_KEY` in current shell.
- Prompt loading fails: check `knowledge_files` names exist in `knowledge/`.
- Rate-limit errors:
  - Free tier default is already safer now: sequential generation + `12s` pacing.
  - Tune with env vars:
    - `$env:ART_GENERATION_MODE="sequential"` or `"concurrent"`
    - `$env:ART_LLM_MIN_INTERVAL_SECONDS="12"`
    - `$env:ART_LLM_MAX_429_ATTEMPTS="5"`
    - `$env:ART_LLM_BACKOFF_BASE_SECONDS="2"`
  - For paid tier high speed: switch to `concurrent` and lower pacing (for example `0` to disable spacing).
- Template errors: verify default template exists at `knowledge/Default Template - Senior Software Engineer.docx`.

## 10. Console UI tuning

The terminal prompt and AI response preview is enabled by default.

```powershell
$env:ART_UI_ENABLED="1"
$env:ART_UI_SHOW_PROMPTS="1"
$env:ART_UI_SHOW_RESPONSES="1"
$env:ART_UI_PROMPT_BORDER_STYLE="bright_cyan"
$env:ART_UI_RESPONSE_BORDER_STYLE="bright_green"
$env:ART_UI_SCORE_STYLE="bold bright_magenta"
```

## 11. Security basics

- Never commit API keys to git.
- Never log raw secrets or full private content.
- Prefer server-side key usage only.

## Verified sources

- API key setup: https://ai.google.dev/tutorials/setup
- Gemini quickstart: https://ai.google.dev/gemini-api/docs/quickstart
- API reference/auth header behavior: https://ai.google.dev/api
- Rate limits and tiers: https://ai.google.dev/gemini-api/docs/quota
- Billing model (free vs paid): https://ai.google.dev/gemini-api/docs/billing/
- Pricing and model availability: https://ai.google.dev/pricing
- Regional availability: https://ai.google.dev/gemini-api/docs/available-regions
