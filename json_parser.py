from __future__ import annotations

import json
import re
from json import JSONDecodeError

from pydantic import ValidationError

from graph_state import ResponseEnvelope

_TRAILING_COMMA_PATTERN = re.compile(r",(\s*[}\]])")


class ResponseParseError(ValueError):
    pass


class ResponseSchemaError(ValueError):
    pass


def clean_llm_json(raw_text: str) -> str:
    text = raw_text.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    if text.lower().startswith("json"):
        text = text[4:].lstrip(" \t\r\n:")

    return text.strip()


def _remove_trailing_commas(text: str) -> str:
    return _TRAILING_COMMA_PATTERN.sub(r"\1", text)


def parse_response_envelope(raw_text: str) -> ResponseEnvelope:
    cleaned = clean_llm_json(raw_text)
    candidates = [cleaned, _remove_trailing_commas(cleaned)]
    last_error: JSONDecodeError | None = None

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            break
        except JSONDecodeError as exc:
            last_error = exc
    else:
        raise ResponseParseError("Malformed JSON in LLM response.") from last_error

    try:
        return ResponseEnvelope.model_validate(parsed)
    except ValidationError as exc:
        raise ResponseSchemaError(
            "LLM response does not match expected envelope schema."
        ) from exc
