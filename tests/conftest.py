from __future__ import annotations

import pytest

DEFAULT_TEST_LLM_MIN_INTERVAL_SECONDS = "0"
REAL_GEMINI_E2E_LLM_MIN_INTERVAL_SECONDS = "12"


@pytest.fixture(autouse=True)
def _configure_llm_pacing_for_tests(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if request.node.get_closest_marker("real_gemini_e2e"):
        monkeypatch.setenv(
            "ART_LLM_MIN_INTERVAL_SECONDS",
            REAL_GEMINI_E2E_LLM_MIN_INTERVAL_SECONDS,
        )
        return
    monkeypatch.setenv(
        "ART_LLM_MIN_INTERVAL_SECONDS",
        DEFAULT_TEST_LLM_MIN_INTERVAL_SECONDS,
    )
