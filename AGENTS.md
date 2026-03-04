# AGENTS.md

## 📌 Project Context
This is "AI Resume Tailor", a local, platform-agnostic Python automation tool. It uses the `google-genai` API to asynchronously generate tailored CVs and Cover Letters. It features a CLI-based Human-in-the-Loop review system to prevent hallucinations, and compiles the final output into a `.docx` file using `python-docx`.

## 🛠️ Stack & Environment
- **Language:** Python 3.10+
- **Key Libraries:** `google-genai` (API), `python-docx` (Word manipulation), `asyncio` (Concurrency), `rich` (CLI UI), `pytest` (Testing)
- **Environment:** Local virtual environment (`.venv`)

## 💻 Commands
- **Format code:** `black .`
- **Lint code:** `ruff check . --fix`
- **Run tests:** `pytest`
- *Note: Always run the formatter and linter before finalizing a code change.*

## 📐 Coding Conventions & Architecture
- **Type Hinting:** You MUST use strict Python type hints for all function arguments and return types (e.g., `def parse_json(data: str) -> dict:`).
- **Separation of Concerns:** Keep functions short and single-purpose. Separate the codebase into logical modules (e.g., `main.py`, `llm_client.py`, `document_builder.py`, `retrospective_ui.py`).
- **Defensive Parsing:** Always wrap `json.loads()` from AI responses in a `try/except` block. Assume the AI will occasionally return malformed markdown (e.g., ```json...```) and actively strip it before parsing.
- **Logging:** Use Python's built-in `logging` module. Log major workflow steps (INFO), API payloads (DEBUG), and stack traces/parsing failures (ERROR) to both the console and a local `.log` file.

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