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

## 📐 Coding Conventions & Architecture
- **Type Hinting:** You MUST use strict Python type hints for all function arguments and return types (e.g., `def parse_json(data: str) -> dict:`).
- **Separation of Concerns:** Keep functions short and single-purpose. Separate the codebase into logical modules (e.g., `main.py`, `llm_client.py`, `document_builder.py`, `retrospective_ui.py`).
- **Defensive Parsing:** Always wrap `json.loads()` from AI responses in a `try/except` block. Assume the AI will occasionally return malformed markdown (e.g., ```json...```) and actively strip it before parsing.
- **Logging:** Use Python's built-in `logging` module. Log major workflow steps (INFO), API payloads (DEBUG), and stack traces/parsing failures (ERROR) to both the console and a local `.log` file.

## Strict Coding Rules:
1. **No Premature Abstraction:** NEVER create Base Classes, Interfaces (ABCs), or generic wrappers unless I explicitly instruct you to. 
2. **Prefer Functions over Classes:** If a class only has an `__init__` and one other method, rewrite it as a pure function.
3. **No Over-Engineering:** Do not add "future-proofing" logic, excessive parameters, or unused helper functions. Solve ONLY the immediate problem described in the prompt.
4. **Flat is Better than Nested:** Keep directory structures flat. Keep function indentation to a maximum of 2 levels deep. Return early to avoid `else` blocks.
5. **Standard Library First:** Do not introduce third-party dependencies if `itertools`, `collections`, or `json` can do the job natively.
6. **Explicit over Implicit:** Do not use complex metaprogramming, decorators, or magic methods (`__getattr__`) unless absolutely necessary.


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
 1. **Local Semantic RAG Prep:** The `prompt_loader.py` must be written as an isolated function `inject_context(prompt, context_files)`. In V2, we will simply swap the file-reader inside this function with a Vector DB similarity search, leaving the rest of the application completely untouched.
 2. **Multi-Agent Critic Prep:** The `graph_router.py` must use strict `if/elif` logic based on the `GraphState`. In V2, we will easily insert the Critic by adding a `node_critic` function and one new `elif` routing edge, without changing the core execution loop.
 3. **Ollama Local Prep:** Because `llm_client.py` is centralized, adding local air-gapped support in V2 will only require adding a `_call_ollama()` helper function next to `_call_gemini()`.