from __future__ import annotations

from graph_nodes import MAX_USER_RETRIES_PER_SECTION, _review_single_section
from graph_state import SectionState, Variation


def _make_section_state() -> SectionState:
    return SectionState(
        status="generated",
        variations=[
            Variation(
                id="A",
                score_0_to_5=5,
                ai_reasoning="Best option",
                content_for_template="Content A",
            ),
            Variation(
                id="B",
                score_0_to_5=3,
                ai_reasoning="Alternative",
                content_for_template="Content B",
            ),
        ],
    )


def test_review_reprompts_invalid_action_then_chooses(
    monkeypatch: object, capsys: object
) -> None:
    section_state = _make_section_state()
    answers = iter(["wrong", "choose", "A"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    should_exit = _review_single_section(
        "section_professional_summary", section_state, position=1, total=6
    )

    captured = capsys.readouterr()
    assert should_exit is False
    assert "Invalid action." in captured.out
    assert section_state.status == "approved"
    assert section_state.selected_variation_id == "A"


def test_review_accepts_alias_action_for_choose(monkeypatch: object) -> None:
    section_state = _make_section_state()
    answers = iter(["c", "A"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    should_exit = _review_single_section(
        "section_professional_summary", section_state, position=1, total=6
    )

    assert should_exit is False
    assert section_state.status == "approved"
    assert section_state.selected_variation_id == "A"


def test_review_reprompts_invalid_variation_id_then_accepts_valid(
    monkeypatch: object, capsys: object
) -> None:
    section_state = _make_section_state()
    answers = iter(["choose", "Z", "A"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    should_exit = _review_single_section(
        "section_professional_summary", section_state, position=1, total=6
    )

    captured = capsys.readouterr()
    assert should_exit is False
    assert "Invalid variation id. Try again." in captured.out
    assert section_state.selected_variation_id == "A"


def test_review_retry_limit_reached_then_choose(
    monkeypatch: object, capsys: object
) -> None:
    section_state = _make_section_state()
    section_state.retry_count = MAX_USER_RETRIES_PER_SECTION
    answers = iter(["retry", "choose", "A"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    should_exit = _review_single_section(
        "section_professional_summary", section_state, position=1, total=6
    )

    captured = capsys.readouterr()
    assert should_exit is False
    assert "Retry limit reached." in captured.out
    assert section_state.retry_count == MAX_USER_RETRIES_PER_SECTION
    assert section_state.selected_variation_id == "A"
