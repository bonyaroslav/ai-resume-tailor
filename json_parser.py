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
    text = text.lstrip("\ufeff")

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


def _extract_first_json_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaping = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaping:
                escaping = False
            elif char == "\\":
                escaping = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
            continue
        if char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def parse_response_envelope(raw_text: str) -> ResponseEnvelope:
    cleaned = clean_llm_json(raw_text)
    raw_candidates = [cleaned]
    extracted = _extract_first_json_object(cleaned)
    if extracted:
        raw_candidates.append(extracted)

    candidates: list[str] = []
    for candidate in raw_candidates:
        for variant in (candidate, _remove_trailing_commas(candidate)):
            if variant not in candidates:
                candidates.append(variant)

    last_error: JSONDecodeError | None = None

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            break
        except JSONDecodeError as exc:
            last_error = exc
    else:
        line = last_error.lineno if last_error else "?"
        column = last_error.colno if last_error else "?"
        char = last_error.pos if last_error else "?"
        raise ResponseParseError(
            f"Malformed JSON in LLM response at line={line} column={column} char={char}."
        ) from last_error

    try:
        return ResponseEnvelope.model_validate(parsed)
    except ValidationError as exc:
        raise ResponseSchemaError(
            "LLM response does not match expected envelope schema."
        ) from exc
