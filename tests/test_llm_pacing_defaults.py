from __future__ import annotations

import os

import pytest


def test_default_test_pacing_is_zero_seconds() -> None:
    assert os.getenv("ART_LLM_MIN_INTERVAL_SECONDS") == "0"


@pytest.mark.real_gemini_e2e
def test_real_gemini_e2e_marker_restores_safe_pacing() -> None:
    assert os.getenv("ART_LLM_MIN_INTERVAL_SECONDS") == "12"
