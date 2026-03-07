from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path


class _RedactionFilter(logging.Filter):
    _api_key_pattern = re.compile(r"AIza[0-9A-Za-z_-]{20,}")
    _email_pattern = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    _phone_pattern = re.compile(r"\+?\d[\d\-\s()]{7,}\d")
    _url_pattern = re.compile(r"https?://\S+")

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        message = self._api_key_pattern.sub("[REDACTED_API_KEY]", message)
        message = self._email_pattern.sub("[REDACTED_EMAIL]", message)
        message = self._phone_pattern.sub("[REDACTED_PHONE]", message)
        message = self._url_pattern.sub("[REDACTED_URL]", message)
        record.msg = message
        record.args = ()
        return True


def configure_logging(run_dir: Path, debug_mode: bool) -> logging.Logger:
    logger = logging.getLogger("ai_resume_tailor")
    logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    redaction_filter = _RedactionFilter()

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(redaction_filter)

    file_handler = logging.FileHandler(run_dir / "run.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(redaction_filter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger


def sha256_short(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _sanitize_detail(detail: str) -> str:
    normalized = " ".join(detail.split()).strip()
    if not normalized:
        return "-"
    if len(normalized) <= 240:
        return normalized
    return normalized[:237] + "..."


def log_failure(
    logger: logging.Logger,
    *,
    category: str,
    node: str,
    section_id: str | None = None,
    attempt: int | None = None,
    retry_count: int | None = None,
    detail: str = "",
) -> None:
    logger.error(
        "failure category=%s node=%s section_id=%s attempt=%s retry_count=%s detail=%s",
        category,
        node,
        section_id or "-",
        attempt if attempt is not None else "-",
        retry_count if retry_count is not None else "-",
        _sanitize_detail(detail),
    )
