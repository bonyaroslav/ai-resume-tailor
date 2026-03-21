from __future__ import annotations

import json
import re
from dataclasses import dataclass
from json import JSONDecodeError
from statistics import mean

from pydantic import ValidationError

from graph_state import ResponseEnvelope, TriageResult
from section_ids import is_experience_section

_TRAILING_COMMA_PATTERN = re.compile(r",(\s*[}\]])")
_LEADING_BULLET_PATTERN = re.compile(r"^\s*(?:[-*]+|\d+[.)])\s*")
_EXPERIENCE_VARIATION_SUFFIX_PATTERN = re.compile(r"^[A-Za-z0-9_-]*?([A-Za-z])$")
_SKILLS_SECTION_ID = "section_skills_alignment"
_DEFAULT_SKILLS_CATEGORY_COUNT = 4


class ResponseParseError(ValueError):
    pass


class ResponseSchemaError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedResponsePayload:
    parsed_payload: dict[str, object]
    normalized_payload: dict[str, object]


def _format_experience_bullet(text: str) -> str:
    parts = [line.strip() for line in text.splitlines() if line.strip()]
    collapsed = " ".join(parts).strip()
    normalized = _LEADING_BULLET_PATTERN.sub("", collapsed).strip()
    return f"- {normalized}"


def _canonicalize_experience_variation_id(variation_id: str) -> str:
    normalized_id = variation_id.strip()
    match = _EXPERIENCE_VARIATION_SUFFIX_PATTERN.match(normalized_id)
    if not match:
        return normalized_id
    return match.group(1).upper()


def _normalize_experience_envelope(parsed: dict[str, object]) -> dict[str, object]:
    bullets = parsed.get("bullets")
    if not isinstance(bullets, list) or not bullets:
        raise ResponseSchemaError(
            "Experience payload must include a non-empty bullets array."
        )

    bullet_variation_ids: list[list[str]] = []
    per_variation_text: dict[str, list[str]] = {}
    per_variation_scores: dict[str, list[int]] = {}
    per_variation_reasoning: dict[str, list[str]] = {}

    for bullet_index, bullet in enumerate(bullets, start=1):
        if not isinstance(bullet, dict):
            raise ResponseSchemaError(
                f"Experience bullet at index {bullet_index} must be an object."
            )
        variations = bullet.get("variations")
        if not isinstance(variations, list) or not variations:
            raise ResponseSchemaError(
                f"Experience bullet at index {bullet_index} must contain non-empty variations."
            )

        variation_ids_for_bullet: list[str] = []
        for variation_index, variation in enumerate(variations, start=1):
            if not isinstance(variation, dict):
                raise ResponseSchemaError(
                    "Experience variation must be an object "
                    f"(bullet={bullet_index}, variation={variation_index})."
                )

            variation_id = variation.get("id")
            score = variation.get("score_0_to_100")
            ai_reasoning = variation.get("ai_reasoning")
            text = variation.get("text")
            if not isinstance(variation_id, str) or not variation_id.strip():
                raise ResponseSchemaError(
                    "Experience variation.id must be a non-empty string "
                    f"(bullet={bullet_index}, variation={variation_index})."
                )
            if not isinstance(score, int) or score < 0 or score > 100:
                raise ResponseSchemaError(
                    "Experience variation.score_0_to_100 must be an integer between 0 and 100 "
                    f"(bullet={bullet_index}, variation={variation_index})."
                )
            if not isinstance(ai_reasoning, str):
                raise ResponseSchemaError(
                    "Experience variation.ai_reasoning must be a string "
                    f"(bullet={bullet_index}, variation={variation_index})."
                )
            if not isinstance(text, str) or not text.strip():
                raise ResponseSchemaError(
                    "Experience variation.text must be a non-empty string "
                    f"(bullet={bullet_index}, variation={variation_index})."
                )

            normalized_id = _canonicalize_experience_variation_id(variation_id)
            variation_ids_for_bullet.append(normalized_id)
            per_variation_text.setdefault(normalized_id, []).append(
                _format_experience_bullet(text)
            )
            per_variation_scores.setdefault(normalized_id, []).append(score)
            per_variation_reasoning.setdefault(normalized_id, []).append(
                ai_reasoning.strip()
            )

        bullet_variation_ids.append(variation_ids_for_bullet)

    expected_ids = bullet_variation_ids[0]
    for variation_ids in bullet_variation_ids[1:]:
        if variation_ids != expected_ids:
            raise ResponseSchemaError(
                "Experience bullets must contain the same ordered variation ids."
            )

    normalized_variations: list[dict[str, object]] = []
    for variation_id in expected_ids:
        normalized_variations.append(
            {
                "id": variation_id,
                "score_0_to_100": int(round(mean(per_variation_scores[variation_id]))),
                "ai_reasoning": " ".join(
                    reason for reason in per_variation_reasoning[variation_id] if reason
                ).strip()
                or "Aggregated bullet-level rationale.",
                "content_for_template": "\n".join(
                    per_variation_text[variation_id]
                ).strip(),
            }
        )

    return {"variations": normalized_variations}


def _normalize_skills_envelope(parsed: dict[str, object]) -> dict[str, object]:
    meta = parsed.get("meta")
    if not isinstance(meta, dict):
        raise ResponseSchemaError("Skills payload must contain a meta object.")

    for key in (
        "jd_top_keywords",
        "covered_keywords",
        "missing_keywords_not_in_matrix",
    ):
        values = meta.get(key)
        if not isinstance(values, list) or not all(
            isinstance(item, str) for item in values
        ):
            raise ResponseSchemaError(f"Skills meta.{key} must be an array of strings.")

    variations = parsed.get("variations")
    if not isinstance(variations, list) or not variations:
        raise ResponseSchemaError(
            "Skills payload must contain a non-empty variations array."
        )

    normalized_variations: list[dict[str, object]] = []
    for variation_index, variation in enumerate(variations, start=1):
        if not isinstance(variation, dict):
            raise ResponseSchemaError(
                f"Skills variation at index {variation_index} must be an object."
            )
        variation_id = variation.get("id")
        score = variation.get("score_0_to_100")
        ai_reasoning = variation.get("ai_reasoning")
        text = variation.get("text")
        if not isinstance(variation_id, str) or not variation_id.strip():
            raise ResponseSchemaError(
                f"Skills variation.id must be a non-empty string (variation={variation_index})."
            )
        if not isinstance(score, int) or score < 0 or score > 100:
            raise ResponseSchemaError(
                "Skills variation.score_0_to_100 must be an integer between 0 and 100 "
                f"(variation={variation_index})."
            )
        if not isinstance(ai_reasoning, str):
            raise ResponseSchemaError(
                f"Skills variation.ai_reasoning must be a string (variation={variation_index})."
            )
        if not isinstance(text, str) or not text.strip():
            raise ResponseSchemaError(
                f"Skills variation.text must be a non-empty string (variation={variation_index})."
            )
        normalized_variations.append(
            {
                "id": variation_id.strip(),
                "score_0_to_100": score,
                "ai_reasoning": ai_reasoning,
                "content_for_template": text.strip(),
            }
        )

    return {"variations": normalized_variations}


def _validate_skill_category(
    category: object, *, variation_index: int, category_index: int
) -> tuple[str, str]:
    if not isinstance(category, dict):
        raise ResponseSchemaError(
            "Skills category must be an object "
            f"(variation={variation_index}, category={category_index})."
        )

    category_name = category.get("category_name")
    category_text = category.get("category_text")
    if not isinstance(category_name, str) or not category_name.strip():
        raise ResponseSchemaError(
            "Skills category.category_name must be a non-empty string "
            f"(variation={variation_index}, category={category_index})."
        )
    if not isinstance(category_text, str) or not category_text.strip():
        raise ResponseSchemaError(
            "Skills category.category_text must be a non-empty string "
            f"(variation={variation_index}, category={category_index})."
        )
    return category_name.strip(), category_text.strip()


def _normalize_skills_envelope_with_categories(
    parsed: dict[str, object], *, category_count: int
) -> dict[str, object]:
    meta = parsed.get("meta")
    if not isinstance(meta, dict):
        raise ResponseSchemaError("Skills payload must contain a meta object.")

    for key in (
        "jd_top_keywords",
        "covered_keywords",
        "missing_keywords_not_in_matrix",
    ):
        values = meta.get(key)
        if not isinstance(values, list) or not all(
            isinstance(item, str) for item in values
        ):
            raise ResponseSchemaError(f"Skills meta.{key} must be an array of strings.")

    variations = parsed.get("variations")
    if not isinstance(variations, list) or not variations:
        raise ResponseSchemaError(
            "Skills payload must contain a non-empty variations array."
        )

    normalized_variations: list[dict[str, object]] = []
    for variation_index, variation in enumerate(variations, start=1):
        if not isinstance(variation, dict):
            raise ResponseSchemaError(
                f"Skills variation at index {variation_index} must be an object."
            )
        variation_id = variation.get("id")
        score = variation.get("score_0_to_100")
        ai_reasoning = variation.get("ai_reasoning")
        categories = variation.get("categories")
        if not isinstance(variation_id, str) or not variation_id.strip():
            raise ResponseSchemaError(
                f"Skills variation.id must be a non-empty string (variation={variation_index})."
            )
        if not isinstance(score, int) or score < 0 or score > 100:
            raise ResponseSchemaError(
                "Skills variation.score_0_to_100 must be an integer between 0 and 100 "
                f"(variation={variation_index})."
            )
        if not isinstance(ai_reasoning, str):
            raise ResponseSchemaError(
                f"Skills variation.ai_reasoning must be a string (variation={variation_index})."
            )
        if not isinstance(categories, list):
            raise ResponseSchemaError(
                f"Skills variation.categories must be an array (variation={variation_index})."
            )
        if len(categories) != category_count:
            raise ResponseSchemaError(
                "Skills variation.categories must contain exactly "
                f"{category_count} items (variation={variation_index})."
            )

        category_lines: list[str] = []
        for category_index, category in enumerate(categories, start=1):
            category_name, category_text = _validate_skill_category(
                category,
                variation_index=variation_index,
                category_index=category_index,
            )
            category_lines.append(f"{category_name}: {category_text}")

        normalized_variations.append(
            {
                "id": variation_id.strip(),
                "score_0_to_100": score,
                "ai_reasoning": ai_reasoning,
                "content_for_template": "\n\n".join(category_lines),
            }
        )

    return {"variations": normalized_variations}


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


def parse_response_payload(raw_text: str) -> dict[str, object]:
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
        except JSONDecodeError as exc:
            last_error = exc
            continue
        if not isinstance(parsed, dict):
            raise ResponseSchemaError("LLM response must be a JSON object.")
        return parsed

    line = last_error.lineno if last_error else "?"
    column = last_error.colno if last_error else "?"
    char = last_error.pos if last_error else "?"
    raise ResponseParseError(
        f"Malformed JSON in LLM response at line={line} column={column} char={char}."
    ) from last_error


def normalize_response_payload(
    parsed: dict[str, object],
    *,
    section_id: str | None = None,
    skills_category_count: int = _DEFAULT_SKILLS_CATEGORY_COUNT,
) -> dict[str, object]:
    if section_id == _SKILLS_SECTION_ID:
        variations = parsed.get("variations")
        if isinstance(variations, list) and any(
            isinstance(variation, dict) and "categories" in variation
            for variation in variations
        ):
            return _normalize_skills_envelope_with_categories(
                parsed,
                category_count=skills_category_count,
            )
        return _normalize_skills_envelope(parsed)
    if (
        section_id is not None
        and is_experience_section(section_id)
        and "bullets" in parsed
    ):
        return _normalize_experience_envelope(parsed)
    return parsed


def parse_response_envelope_payload(
    raw_text: str,
    *,
    section_id: str | None = None,
    skills_category_count: int = _DEFAULT_SKILLS_CATEGORY_COUNT,
) -> ParsedResponsePayload:
    parsed_payload = parse_response_payload(raw_text)
    normalized_payload = normalize_response_payload(
        parsed_payload,
        section_id=section_id,
        skills_category_count=skills_category_count,
    )
    return ParsedResponsePayload(
        parsed_payload=parsed_payload,
        normalized_payload=normalized_payload,
    )


def parse_response_envelope(
    raw_text: str,
    *,
    section_id: str | None = None,
    skills_category_count: int = _DEFAULT_SKILLS_CATEGORY_COUNT,
) -> ResponseEnvelope:
    payload = parse_response_envelope_payload(
        raw_text,
        section_id=section_id,
        skills_category_count=skills_category_count,
    )
    try:
        return ResponseEnvelope.model_validate(payload.normalized_payload)
    except ValidationError as exc:
        raise ResponseSchemaError(
            "LLM response does not match expected envelope schema."
        ) from exc


def parse_triage_result(raw_text: str) -> TriageResult:
    parsed = parse_response_payload(raw_text)
    triage_result = parsed.get("triage_result")
    if not isinstance(triage_result, dict):
        raise ResponseSchemaError(
            "LLM triage response must contain a triage_result object."
        )

    try:
        return TriageResult.model_validate(triage_result)
    except ValidationError as exc:
        raise ResponseSchemaError(
            "LLM triage response does not match expected triage_result schema."
        ) from exc
