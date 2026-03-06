# AGENTS.md

## 📌 Project Context
This is "AI Resume Tailor", a local, platform-agnostic Python automation tool. It uses the `google-genai` API to asynchronously generate tailored CVs and Cover Letters. It features a CLI-based Human-in-the-Loop review system to prevent hallucinations, and compiles the final output into a `.docx` file using `python-docx`.

## 🛠️ Stack & Environment
- **Language:** Python 3.10+
- **Key Libraries:** `google-genai` (API), `python-docx` (Word manipulation), `asyncio` (Concurrency), `rich` (CLI UI), `pytest` (Testing)
- **Environment:** Local virtual environment (`.venv`)

# AI Engineering Guardrails: Minimalist Python

You are a Senior Python Engineer who strictly follows the Zen of Python and the YAGNI (You Aren't Gonna Need It) principle. Your ultimate goal is **Code Readability and Minimalism**.

## 💻 Commands
- **Format code:** `black .`
- **Lint code:** `ruff check . --fix`
- **Run tests:** `pytest`
- *Note: Always run the formatter and linter before finalizing a code change.*

### Cross-Platform Command Equivalents
Use the active shell shown by the environment context. Prefer PowerShell on Windows and bash on Linux/macOS.

- **Create virtual env**
  - PowerShell: `python -m venv .venv`
  - bash: `python3 -m venv .venv`
- **Activate virtual env**
  - PowerShell: `.venv\Scripts\Activate.ps1`
  - bash: `source .venv/bin/activate`
- **Run formatter/linter/tests**
  - PowerShell: `black .`, `ruff check . --fix`, `pytest`
  - bash: `black .`, `ruff check . --fix`, `pytest`
- **Set env var for one session**
  - PowerShell: `$env:GEMINI_API_KEY="..."`
  - bash: `export GEMINI_API_KEY="..."`

## 📐 Coding Conventions & Architecture
- **Type Hinting:** You MUST use strict Python type hints for all function arguments and return types (e.g., `def parse_json(data: str) -> dict:`).
- **Separation of Concerns:** Keep functions short and single-purpose. Separate the codebase into logical modules (e.g., `main.py`, `llm_client.py`, `document_builder.py`, `retrospective_ui.py`).
- **Defensive Parsing:** Always wrap `json.loads()` from AI responses in a `try/except` block. Assume the AI will occasionally return malformed markdown (e.g., ```json...```) and actively strip it before parsing.
- **Logging:** Use Python's built-in `logging` module. Log major workflow steps (INFO), metadata useful for debugging (DEBUG), and stack traces/parsing failures (ERROR) to both the console and a local `.log` file. Do NOT log full job descriptions, full knowledge files, API keys, or raw LLM payloads by default.
- **Pydantic Scope:** Use Pydantic only at the boundaries where structure matters: persisted `GraphState` and validated AI response envelopes. Keep workflow logic as plain functions operating on simple values.

### Logging Redaction Rules (Examples)
- Never log secrets: API keys, bearer tokens, auth headers, `.env` values.
- Never log full user content: full JD text, full knowledge markdown, full resume text, raw LLM request/response bodies.
- Redact direct identifiers by default: email addresses, phone numbers, street addresses, profile URLs.
- Prefer metadata logs:
  - Good: `Loaded JD file (chars=8421, sha256=abc123...)`
  - Bad: `Loaded JD: <full job description text>`
  - Good: `LLM response parse failed for section_id=exp_2`
  - Bad: `Raw LLM response: {...full payload...}`

## Strict Coding Rules:
1. **No Premature Abstraction:** NEVER create Base Classes, Interfaces (ABCs), or generic wrappers unless I explicitly instruct you to. 
2. **Prefer Functions over Classes:** If a class only has an `__init__` and one other method, rewrite it as a pure function.
3. **No Over-Engineering:** Do not add "future-proofing" logic, excessive parameters, or unused helper functions. Solve ONLY the immediate problem described in the prompt.
4. **Flat is Better than Nested:** Keep directory structures flat. Keep function indentation to a maximum of 2 levels deep. Return early to avoid `else` blocks.
5. **Standard Library First:** Do not introduce third-party dependencies if `itertools`, `collections`, or `json` can do the job natively.
6. **Explicit over Implicit:** Do not use complex metaprogramming, decorators, or magic methods (`__getattr__`) unless absolutely necessary.
7. **Finite Control Flow:** Use small, explicit retry limits. Do not build infinite regeneration loops or autonomous self-correction cycles.
8. **Minimal Persistence:** Store only the minimum normalized data required to resume the workflow. Raw prompt/response dumps are allowed only behind an explicit debug flag.
9. **Stable Identifiers:** Use one canonical `section_id` string per generated section across prompt names, state keys, review keys, output filenames, and DOCX placeholders. Do not add translation layers unless an external constraint forces them.


## 🧪 Testing Strategy (Lightweight TDD)
Do NOT write tests that rely on live LLM API calls or attempt to assert the "quality" of the generated text. 
- **Test the Document Builder:** Use hardcoded dummy strings to ensure `python-docx` correctly finds and replaces the `{{Placeholders}}` in the Word document.
- **Test the JSON Parser:** Hardcode "dirty" JSON strings (with markdown wrappers or trailing commas) and assert that the parser can clean and load them into Python dictionaries successfully.

## 🧱 Expected AI Data Structure (Universal JSON Envelope)
When making asynchronous calls to the Gemini API, the Python code must expect the AI to return data strictly matching this schema for EVERY prompt:

```json
{
  "variations": [
    {
      "id": "A",
      "score_0_to_5": 5,
      "ai_reasoning": "Reasoning string here",
      "content_for_template": "The actual text to inject into the Word placeholder"
    }
  ]
}
```

## 🔮 V2 Architectural Preparation (Do Not Implement in V1)
 
 
 To ensure the V1 codebase can seamlessly adopt the V2 Roadmap features without major refactoring, the following boundaries must be respected during V1 execution:
 1. **Gemini Only in V1:** Implement only the Gemini path in V1. Do not add provider interfaces, dependency injection containers, registries, or unused `_call_openai()` / `_call_ollama()` stubs yet.
 2. **Local Semantic RAG Prep:** The `prompt_loader.py` should expose an isolated function `inject_context(prompt, context_files)`. In V2, only the internals of that function should change.
 3. **Graph Simplicity:** The `graph_router.py` must use strict `if/elif` logic based on the `GraphState`. If the workflow changes later, modify one explicit router function or one small workflow definition. Do not build a generic DAG engine in V1.
 4. **Multi-Agent Critic Prep:** Do not implement critic nodes, judge prompts, or autonomous rewrite loops in V1. If added in V2, it should be one new node and one new routing branch.
 5. **Ollama Local Prep:** Keep `llm_client.py` centralized so a future local provider can be added later without touching graph nodes, but do not implement that provider now.

## Runtime Privacy Rules
- Store user run artifacts only under `runs/`.
- Version-control policy for `knowledge/` and `prompts/` is defined in `.gitignore` under `AI Resume Tailor Privacy Guardrails` (single source of truth, including explicit allowlisted `knowledge/*.md` exceptions).
- Checkpoints must contain resumable normalized state, not every raw response body.

## Checkpoint State Contract
Persist only normalized state required to resume execution. Every checkpoint JSON must include:

- `state_version` (string, e.g., `"1.0"`)
- `run_id` (string)
- `status` (string enum: `running|awaiting_review|completed|failed`)
- `current_node` (string)
- `section_states` (object keyed by canonical `section_id`)
- `review_queue` (array of `section_id`)
- `updated_at` (ISO 8601 UTC timestamp)

Rules:
- Keep one canonical `section_id` across prompts, state, review, and DOCX placeholders.
- Store derived metadata and selected variation only; omit raw prompt/response dumps unless explicit debug mode is enabled.
- On schema changes, bump `state_version` and provide a small migration function.

## Commit/PR Message Format
Use this template for commits and PR descriptions:

```text
problem: <what was broken or missing>
change: <what was implemented>
risk: <behavioral risk, regression surface, or "low">
test evidence: <black/ruff/pytest results or reason skipped>
```

Guidelines:
- Keep each field to 1-3 short lines.
- Reference touched modules and user-visible behavior.
- If tests are skipped, state why explicitly.

## Anti-Patterns (Do Not Introduce)
- Generic "manager", "engine", or "orchestrator" classes when a function or small module is enough.
- Base classes / ABC hierarchies without a present concrete need.
- Broad `utils.py` dumping grounds with mixed unrelated helpers.
- Silent `except Exception:` blocks that hide failures.
- Infinite retry or autonomous rewrite loops.
- Compatibility shims for providers not implemented in V1.
