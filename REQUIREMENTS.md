# AI Resume Tailor (Platform-Agnostic CV Pipeline)

## 📌 Project Overview
A local, platform-agnostic Python automation tool that transforms a generic CV into a highly targeted application package. It utilizes a two-stage asynchronous pipeline via the Google Gemini API: first analyzing the job for risks/fit (Triage), and then generating tailored CV sections in parallel. It ensures high quality via a Human-in-the-Loop CLI retrospective and assembles the final `.docx` locally.

## 🏗️ Core Features & Workflow

### 1. Data Privacy & Reusability
* **Agnostic Architecture:** The repository must contain NO personal data. 
* **Knowledge Directory:** All personal receipts, skills, and cover letter facts live in a local `knowledge/` directory, which is strictly excluded via `.gitignore`. 
* **Templates:** The repository provides empty `knowledge/*.example.md` files for new users to clone and populate with their own data.

### 2. Context Isolation (YAML Frontmatter)
* Prompts are stored as Markdown files in the `prompts/` directory.
* To prevent AI hallucinations, prompts do NOT load all user data at once. Instead, they use YAML Frontmatter at the top of the file to explicitly declare which specific `knowledge/` files they need.
* *Example:* `section_experience_2_previous.md` will only load the knowledge files declared in its frontmatter.

### 3. Two-Stage Execution Pipeline
* **Stage 1: Triage (Sequential):** The system runs `triage_job_fit_and_risks.md`, cross-referencing the JD against skill gaps and employment risks. It prints a concise Go/No-Go recommendation to the CLI and asks the user for permission to proceed.
* **Stage 2: Document Generation (Parallel):** If the user inputs "Go", the system uses `asyncio` to execute the active section prompts concurrently to generate CV sections and the cover letter.

### 4. Structured Output & Retrospective (Human-in-the-Loop)
* **Universal JSON Envelope:** The AI is strictly prompted to return responses in a universal JSON schema: `{"variations": [{"id": "A", "score_0_to_5": 5, "ai_reasoning": "...", "content_for_template": "..."}]}`.
* **Interactive Review:** The system displays the variations, scores, and AI reasoning in the CLI. The user selects the best variation for each section to prevent hallucinations from making it into the final document.

### 5. Document Assembly
* The system reads a base `Default Template.docx`.
* It utilizes a 1-to-1 mapping strategy: each generated section uses one canonical `section_id`, and that same identifier maps directly to the placeholder in the Word document.
* The populated document is saved securely to the local machine without modifying the original template.

---

## ⚙️ Technical Requirements & Stack

* **OS/Environment:** Platform-agnostic (Python 3.10+). Local execution only.
* **AI Provider:** `google-genai` library utilizing Gemini (Flash/Pro).
* **Concurrency:** Python native `asyncio` for non-blocking API requests.
* **Document Manipulation:** `python-docx` for parsing and generating the final Word document.
* **Data Parsing:** `PyYAML` to parse prompt frontmatter; native `json` with robust error handling for API responses.
* **CLI Interface:** `rich` or standard `print`/`input` for the interactive Retrospective menu.

## 📐 Development Rules (Lightweight TDD)
* **Do not write tests for LLM quality.** Focus testing strictly on deterministic logic.
* Write tests for the JSON parsing layer (ensuring it can strip markdown and handle bad JSON).
* Write tests for the `python-docx` injection layer (ensuring it finds and replaces `{{Placeholders}}` correctly using dummy strings).
