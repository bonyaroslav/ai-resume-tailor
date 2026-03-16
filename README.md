<a name="readme-top"></a>

<div align="center">
  <h2>🚀 AI Resume Tailor</h2>
  <p><b>A Python LLM workflow for evidence-grounded resume tailoring and human-reviewed CV generation</b></p>

  <p align="center">
    <a href="https://github.com/your_username/ai-resume-tailor/issues">Report Bug</a>
    ·
    <a href="https://github.com/your_username/ai-resume-tailor/issues">Request Feature</a>
  </p>

  <p>
    <img src="https://img.shields.io/badge/Python-3.10+-blue.svg?style=for-the-badge&logo=python" alt="Python">
    <img src="https://img.shields.io/badge/Architecture-Workflow_Graph-brightgreen.svg?style=for-the-badge" alt="Architecture">
    <img src="https://img.shields.io/badge/AI-Gemini_API-orange.svg?style=for-the-badge" alt="LLM">
    <img src="https://img.shields.io/badge/Review-Human_in_the_Loop-purple.svg?style=for-the-badge" alt="Review">
    <img src="https://img.shields.io/badge/Google_AI_Studio-Free_Tier_Friendly-4285F4.svg?style=for-the-badge&logo=google" alt="Google AI Studio Free Tier Friendly">
  </p>

  <p><b>Designed to work within Gemini free-tier limits</b> · Cost-aware defaults · Checkpointed runs · Structured LLM outputs · Human review gates</p>
</div>

---

## 📖 The Problem & The Solution

**The Problem:** Resume tailoring is repetitive, easy to get wrong, and one-shot LLM rewrites often miss role-specific language or overstate experience.

**The Solution:** `AI Resume Tailor` is a Python CLI that orchestrates job-description analysis, section-level generation, human review, and final `.docx` assembly through an explicit graph workflow. It uses structured LLM outputs, scoped context injection, and resumable checkpoints to keep generation traceable and grounded in real experience.

---

## ✨ Key Features

* **🎯 Evidence-Grounded Tailoring:** Rewrites resume sections against the target role without inventing experience.
* **🔄 Graph-Orchestrated Workflow:** Uses explicit fan-out/fan-in routing with targeted regeneration for rejected sections.
* **🛑 Human Approval Gates:** Built-in checkpointing pauses execution for choose/edit/retry decisions before final export.
* **🔌 Structured LLM Layer:** Gemini calls are centralized and validated through strict response envelopes.
* **📚 Scoped Context Injection:** Prompt frontmatter loads only the knowledge files each section actually needs.
* **💾 Resumable Run Artifacts:** Checkpoints, logs, outputs, and the source JD are persisted under `runs/`.

---

## 🧠 System Architecture

Instead of relying on heavy third-party agent frameworks, this core engine is built as a native, lightweight **Directed Graph State Machine** with explicit routing and small functions.

```mermaid
graph TD
    A[Start: CLI Input JD] --> B(Node 1: Triage)
    B -->|Cross-reference JD vs Base Skills| C{Is it a fit?}
    C -->|No-Go| D[Terminate Pipeline]
    C -->|Go| E(Node 2: Concurrent Fan-Out)
    
    E --> F[Generate Summary]
    E --> G[Generate Exp 1]
    E --> H[Generate Exp 2]
    
    F --> I(Node 3: Human-in-the-Loop Checkpoint)
    G --> I
    H --> I
    
    I -->|User Rejects a Draft| J[Capture Feedback String]
    J -. Backward Edge .-> E
    
    I -->|User Approves All| K(Node 4: Assembly)
    K --> L["Inject {{Placeholders}}"]
    L --> M[Export CV.docx]

```

### 📐 Architecture Decision Records (ADRs)

1. **Why a Custom State Machine over LangChain?** For a strictly scoped CLI tool, a plain Python state machine is easier to read, easier to test, and harder to over-engineer.
2. **Context Isolation via Frontmatter:**
To reduce hallucination risk and avoid context bloat, prompts do not read the entire knowledge base blindly. Markdown prompts use YAML frontmatter to request *only* the specific files they need.


---

## 🗺️ Roadmap (V2 Enhancements)

V1 focuses on delivering a deterministic, lightweight State Machine. Once the core pipeline is locked, the following architectural upgrades are planned:

* **Multi-Agent Evaluator (LLM-as-a-Judge):** Add one critic node before human review if V1 proves the core workflow first.
* **Alternative Local-Provider Path:** Add **Ollama / vLLM** after the Gemini-only V1 flow is stable.
* **Retrieval-Augmented Context Selection:** Move from static YAML frontmatter toward retrieval-driven context injection when the current workflow is stable.

---

## ✅ V1 Implementation Snapshot (Current)

To complement the vision above, the current shipped V1 behavior is strict and deterministic:

* **Canonical workflow IDs:** `triage_job_fit_and_risks`, `section_professional_summary`, `section_skills_alignment`, `section_experience_1..3`, `doc_cover_letter`
* **Single checkpoint contract:** `GraphState` persisted as `state_version=1.0` for pause/resume consistency
* **Strict AI response envelope:** `{"variations":[{"id","score_0_to_100","ai_reasoning","content_for_template"}]}`
* **Review actions:** per section `choose | edit | retry`, plus global `save_and_exit`
* **Prompt/template safety rules:** canonical section normalization, duplicate ID detection, and fail-fast validation
* **Run outputs:** `tailored_cv.docx`, `cover_letters.md`, `cv_deep_dive_audit.md`, `job_description.md`, checkpoint + metadata + logs under `runs/...`

## 🤖 Why It Is Interesting for GenAI Engineering

* **Structured generation contracts:** Every prompt is expected to return machine-readable variations rather than free-form prose.
* **Human review gates over autonomous loops:** Review happens before final output, keeping control with the operator.
* **Retrieval-ready context design:** Prompt frontmatter already constrains context loading and can evolve into retrieval-based selection later.
* **Deterministic offline validation:** Offline fixtures make it possible to exercise the workflow without live API calls.

Current CLI commands:

```sh
python main.py run --jd-path ./inputs/job_description.md --company "Stripe"
python main.py run --jd-path ./inputs/job_description.md --company "Stripe" --job-title "Senior Backend Engineer"
python main.py resume --run-path ./runs/stripe
# or
python main.py resume --checkpoint-path ./runs/stripe/state_checkpoint.json
python main.py status --run-path ./runs/stripe
python main.py regenerate --run-path ./runs/stripe --sections section_professional_summary --note "make outcomes more specific"
python main.py rebuild-output --run-path ./runs/stripe
```

---

## 🚀 Getting Started

<p><b>New here?</b> Use the concise setup guide: <a href="./RUNBOOK_SETUP.md">RUNBOOK_SETUP.md</a></p>

### Prerequisites

* Python 3.10+
* A Google Gemini API key

### Installation

1. Clone the repo
```sh
git clone [https://github.com/your_username/ai-resume-tailor.git](https://github.com/your_username/ai-resume-tailor.git)

```


2. Set up a virtual environment
```sh
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

```


3. Install dependencies
```sh
pip install -r requirements.txt

```


4. Set your environment variables
```env
# .env
GEMINI_API_KEY=your_api_key_here

```



---

## 💻 Usage

**1. Start a New Tailoring Session:**

```sh
python main.py run --jd-path ./inputs/job_description.md --company "Stripe"
python main.py run --jd-path ./inputs/job_description.md --company "Stripe" --job-title "Senior Backend Engineer"

```

`--jd-path` accepts `.txt` or `.md`. Each run stores the supplied text as `runs/<run_id>/job_description.md` and uploads that file fresh for the run-scoped cached content.

### One-Command Runner (Windows PowerShell)

If you do not want to type API key / JD path / company each run:

1. Copy `secrets\gemini_api_key.example.txt` to `secrets\gemini_api_key.txt`.
2. Put your key inside `secrets\gemini_api_key.txt` (gitignored).
3. Edit `runner.config.ps1` once (`JobDescriptionPath`, `CompanyName`, optional `JobTitle`, optional `ModelName`).
4. Run:

```powershell
.\run_local.ps1
```

### Offline Smoke Run (No Network)

Use deterministic local fixtures to validate end-to-end behavior (logs, checkpoint, DOCX output):

```powershell
$env:ART_OFFLINE_MODE="1"
$env:ART_AUTO_APPROVE_REVIEW="1"
python main.py run --jd-path .\inputs\job_description.md --company "Offline Smoke"
```

Default offline fixture file:

- `offline_fixtures/<role>/offline_responses.example.json`

Optional custom fixture path:

```powershell
$env:ART_OFFLINE_FIXTURES_PATH="C:\path\to\fixtures.json"
```

### Real Gemini Run (Google AI Studio)

```powershell
$env:GEMINI_API_KEY="your_api_key_here"
Remove-Item Env:ART_OFFLINE_MODE -ErrorAction SilentlyContinue
Remove-Item Env:ART_AUTO_APPROVE_REVIEW -ErrorAction SilentlyContinue
python main.py run --jd-path .\inputs\job_description.md --company "Stripe"
```

Model can be changed locally via:

- `runner.config.ps1` (`ModelName`)
- CLI: `--model`
- env: `$env:GEMINI_MODEL="..."`
- code default: `DEFAULT_GEMINI_MODEL` in `settings.py`

### Throughput Tuning

Defaults are now safer for free tier (sequential + pacing + 429 backoff).  
You can tune with env vars:

```powershell
$env:ART_GENERATION_MODE="sequential"   # or "concurrent"
$env:ART_LLM_MIN_INTERVAL_SECONDS="12"  # lower for higher throughput
$env:ART_LLM_MAX_429_ATTEMPTS="5"
$env:ART_LLM_BACKOFF_BASE_SECONDS="2"
```

### Pytest Pacing Defaults (Fast by Default)

`pytest` runs now default to:

- `ART_LLM_MIN_INTERVAL_SECONDS=0`

This keeps local and CI tests fast for mocked/offline flows.

For real Gemini end-to-end tests on free tier, use:

- pytest marker: `@pytest.mark.real_gemini_e2e`

That marker automatically restores pacing to:

- `ART_LLM_MIN_INTERVAL_SECONDS=12`

**2. Resume a Paused Review Session (from JSON Checkpoint):**

```sh
python main.py resume --run-path ./runs/stripe
# or
python main.py resume --checkpoint-path ./runs/stripe/state_checkpoint.json

```

**3. End-to-end flow (triage -> auto generation -> status -> targeted regenerate -> rebuild):**

```sh
# Start run and make triage decision in CLI (continue_anyway/stop)
python main.py run --jd-path ./inputs/job_description.md --company "Stripe"

# Optional: force non-interactive smoke path for triage + review
# ART_TRIAGE_DECISION_MODE=always_continue ART_AUTO_APPROVE_REVIEW=1 python main.py run --jd-path ./inputs/job_description.md --company "Stripe"

# Review current checkpoint state
python main.py status --run-path ./runs/stripe

# Regenerate only specific sections with explicit reviewer note
python main.py regenerate --run-path ./runs/stripe --sections section_professional_summary,doc_cover_letter --note "focus on measurable impact"

# Rebuild final outputs from approved content
python main.py rebuild-output --run-path ./runs/stripe
```

Run folders are now reused by company slug (`runs/<company-slug>`). If you pass `--job-title`, the run folder becomes `runs/<company_slug>_<job_title_slug>`.  
If you want separate runs for multiple roles at one company, use `--job-title` (for example `runs/stripe_senior_backend_engineer`).

*(Optional: Insert a `.gif` here showing your CLI menu in action. Hiring managers love seeing the tool actually working in a terminal).*

---

## 🛡️ Privacy & Security

Knowledge files and run artifacts stay in repo-local directories. During live generation, only scoped prompt context is sent to the Gemini API; outputs, checkpoints, and logs remain under `runs/`.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.



