from __future__ import annotations

import asyncio
from typing import Any


class LlmClientError(RuntimeError):
    pass


def _extract_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text

    candidates = getattr(response, "candidates", None)
    if not candidates:
        return ""

    parts: list[str] = []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        if content is None:
            continue
        candidate_parts = getattr(content, "parts", None)
        if not candidate_parts:
            continue
        for part in candidate_parts:
            piece = getattr(part, "text", None)
            if isinstance(piece, str):
                parts.append(piece)
    return "\n".join(parts).strip()


def _generate_sync(prompt: str, api_key: str, model: str) -> str:
    try:
        from google import genai
    except ImportError as exc:
        raise LlmClientError("google-genai is not installed.") from exc

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(model=model, contents=prompt)
    text = _extract_text(response)
    if not text:
        raise LlmClientError("Gemini response did not include text output.")
    return text


async def generate_with_gemini(prompt: str, api_key: str, model: str) -> str:
    return await asyncio.to_thread(_generate_sync, prompt, api_key, model)
