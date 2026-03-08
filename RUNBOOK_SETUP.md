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

## 7. Resume a paused run

```powershell
.\.venv\Scripts\python.exe main.py resume --run-path .\runs\<run_id>
# or
.\.venv\Scripts\python.exe main.py resume --checkpoint-path .\runs\<run_id>\state_checkpoint.json
```

## 8. Troubleshooting quick checks

- `Missing GEMINI_API_KEY`: set `$env:GEMINI_API_KEY` in current shell.
- Prompt loading fails: check `knowledge_files` names exist in `knowledge/`.
- Rate-limit errors: reduce run frequency or wait for quota reset.
- Template errors: verify default template exists at `knowledge/Default Template - Senior Software Engineer.docx`.

## 9. Console UI tuning

The terminal prompt and AI response preview is enabled by default.

```powershell
$env:ART_UI_ENABLED="1"
$env:ART_UI_SHOW_PROMPTS="1"
$env:ART_UI_SHOW_RESPONSES="1"
$env:ART_UI_PROMPT_BORDER_STYLE="bright_cyan"
$env:ART_UI_RESPONSE_BORDER_STYLE="bright_green"
$env:ART_UI_SCORE_STYLE="bold bright_magenta"
```

## 10. Security basics

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
