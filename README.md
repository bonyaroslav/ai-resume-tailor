# AI Resume Tailor

Local Python CLI to tailor a CV and cover letter from a job description with Gemini, explicit routing, checkpointed human review, and deterministic DOCX assembly.

## What V1 does

- Runs a fixed workflow with canonical `section_id` values:
  - `triage_job_fit_and_risks`
  - `section_professional_summary`
  - `section_skills_alignment`
  - `section_experience_1`
  - `section_experience_2`
  - `section_experience_3`
  - `doc_cover_letter`
- Uses one `GraphState` checkpoint contract (`state_version=1.0`) for run/resume.
- Parses prompt frontmatter with exactly one supported key: `knowledge_files`.
- Enforces one JSON envelope for every LLM response:
  - `{"variations":[{"id","score_0_to_5","ai_reasoning","content_for_template"}]}`
- Supports review actions per section: `choose`, `edit`, `retry`.
- Supports global review action: `save_and_exit`.
- Exports:
  - `tailored_cv.docx` from template placeholder injection
  - `cover_letter.txt` as separate output

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Set environment variables:

```powershell
$env:GEMINI_API_KEY="your_api_key"
# optional
$env:GEMINI_MODEL="gemini-2.5-flash"
```

## Usage

Start a new run:

```powershell
python main.py run --jd-path .\inputs\job_description.txt --company "Stripe"
```

Resume a run:

```powershell
python main.py resume --run-path .\runs\26.03.06-stripe
# or
python main.py resume --checkpoint-path .\runs\26.03.06-stripe\state_checkpoint.json
```

Optional flags:

- `run`: `--template-path`, `--model`, `--debug`
- `resume`: `--model`

## Prompt and template rules

- Active prompts are discovered from `prompts/*.md`.
- If a section has no `.md`, `.example.md` is used as fallback.
- Experience prompt names may include a suffix (for example `section_experience_2_previous.md`), but canonical ID is normalized to `section_experience_2`.
- DOCX placeholders use the same normalization rule for experience sections.
- Duplicate canonical prompt IDs or duplicate normalized placeholder IDs fail fast.

## Run artifacts

Each run creates `runs/YY.MM.DD-company-slug[-N]/` containing:

- `run_metadata.json`
- `job_description.txt`
- `state_checkpoint.json`
- `run.log`
- `tailored_cv.docx` (on completion)
- `cover_letter.txt` (on completion)
- `debug/*` raw responses only when `--debug` is enabled

## Quality gates

```powershell
black .
ruff check . --fix
pytest
```
