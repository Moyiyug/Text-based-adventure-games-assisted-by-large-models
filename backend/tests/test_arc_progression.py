"""弧线推进与终局判定单测。Phase 11.4。"""

from app.schemas.narrative_plan import NarrativePlan
from app.services.narrative.arc_progression import (
    advance_timeline_order,
    evaluate_arc_completion,
    split_state_update_for_arc,
)


def test_split_strips_control_keys() -> None:
    raw = {
        "active_goal": "x",
        "narrative_timeline_order": 7,
        "narrative_arc_complete": True,
    }
    clean, hint, arc_done = split_state_update_for_arc(raw)
    assert hint == 7
    assert arc_done is True
    assert "narrative_timeline_order" not in clean
    assert clean["active_goal"] == "x"


def test_advance_no_backwards() -> None:
    p = NarrativePlan(current_timeline_order=5, arc_end_order=10)
    assert advance_timeline_order(p, 3) == 5


def test_advance_max_step_one() -> None:
    p = NarrativePlan(current_timeline_order=5, arc_end_order=10)
    assert advance_timeline_order(p, 9) == 6


def test_advance_respects_arc_end() -> None:
    p = NarrativePlan(current_timeline_order=9, arc_end_order=10)
    assert advance_timeline_order(p, 99) == 10


def test_evaluate_completion_at_arc_end() -> None:
    p = NarrativePlan(
        opening_anchor_order=1,
        arc_end_order=10,
        current_timeline_order=10,
    )
    ok, reason = evaluate_arc_completion(
        p,
        10,
        arc_complete_hint=False,
        session_turn_count_before=2,
    )
    assert ok is True
    assert reason == "timeline_reached_arc_end"


def test_degenerate_arc_requires_turn_count() -> None:
    p = NarrativePlan(
        opening_anchor_order=10,
        arc_end_order=10,
        current_timeline_order=10,
    )
    ok, _ = evaluate_arc_completion(
        p,
        10,
        arc_complete_hint=False,
        session_turn_count_before=1,
    )
    assert ok is False


def test_model_arc_complete_overrides_degenerate_guard() -> None:
    p = NarrativePlan(
        opening_anchor_order=10,
        arc_end_order=10,
        current_timeline_order=10,
    )
    ok, reason = evaluate_arc_completion(
        p,
        10,
        arc_complete_hint=True,
        session_turn_count_before=1,
    )
    assert ok is True
    assert reason == "model_narrative_arc_complete"


def test_timeline_reached_condition() -> None:
    p = NarrativePlan(
        opening_anchor_order=1,
        arc_end_order=0,
        current_timeline_order=8,
        completion_conditions=[{"type": "timeline_reached", "order": 8}],
    )
    ok, reason = evaluate_arc_completion(
        p,
        8,
        arc_complete_hint=False,
        session_turn_count_before=2,
    )
    assert ok is True
    assert reason == "completion_condition_timeline_reached"
