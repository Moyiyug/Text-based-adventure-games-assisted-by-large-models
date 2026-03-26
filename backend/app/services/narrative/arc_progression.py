"""弧线时间线推进与终局判定。Phase 11.4 — RULES §5.12–§5.13。"""

from __future__ import annotations

from typing import Any

from app.schemas.narrative_plan import NarrativePlan


def split_state_update_for_arc(raw: dict[str, Any] | None) -> tuple[dict[str, Any], int | None, bool]:
    """
    从模型 META 的 state_update 剥离仅服务端消费的键，再交给 validate_state_update。
    返回：(净 state_update, 时间线次序提示, 是否显式声明弧线收束)。
    """
    if not raw:
        return {}, None, False
    d = dict(raw)
    order_hint: int | None = None
    for key in ("narrative_timeline_order", "timeline_order"):
        if key in d:
            v = d.pop(key, None)
            if order_hint is None and v is not None:
                try:
                    order_hint = int(v)
                except (TypeError, ValueError):
                    pass
    arc_complete = bool(d.pop("narrative_arc_complete", False))
    return d, order_hint, arc_complete


def advance_timeline_order(plan: NarrativePlan, proposed: int | None) -> int:
    """
    单调不后退；每回合相对前一有效值最多前进 1；不超过 arc_end_order（>0 时）。
    无 proposed 时保持 current_timeline_order。
    """
    prev = plan.current_timeline_order
    if proposed is None:
        return prev
    if proposed < prev:
        return prev
    step = min(proposed, prev + 1)
    ae = plan.arc_end_order
    if ae > 0:
        step = min(step, ae)
    return max(step, prev)


def evaluate_arc_completion(
    plan: NarrativePlan,
    new_order: int,
    *,
    arc_complete_hint: bool,
    session_turn_count_before: int,
) -> tuple[bool, str]:
    """
    是否本回合结束后进入 completed。
    session_turn_count_before：本回合开始时 sessions.turn_count（含开场 assistant 记 1）。
    """
    degenerate = (
        plan.arc_end_order > 0
        and plan.opening_anchor_order >= plan.arc_end_order
    )

    if arc_complete_hint and new_order >= plan.opening_anchor_order:
        return True, "model_narrative_arc_complete"

    if plan.arc_end_order > 0 and new_order >= plan.arc_end_order:
        if degenerate and session_turn_count_before < 2:
            return False, ""
        return True, "timeline_reached_arc_end"

    for cond in plan.completion_conditions:
        t = cond.get("type")
        if t == "timeline_reached":
            ord_req = int(cond.get("order", 0))
            if new_order >= ord_req:
                if degenerate and session_turn_count_before < 2:
                    return False, ""
                return True, "completion_condition_timeline_reached"

    return False, ""
