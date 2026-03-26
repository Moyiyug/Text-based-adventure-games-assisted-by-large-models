"""会话叙事弧线 JSON 契约。与 IMPLEMENTATION_PLAN Phase 11.1、BACKEND_STRUCTURE §1.5 一致。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

NarrativeStatusLiteral = Literal["opening_pending", "in_progress", "completed"]

NARRATIVE_STATUS_VALUES: frozenset[str] = frozenset(
    ("opening_pending", "in_progress", "completed")
)


class NarrativePlan(BaseModel):
    """
    持久化于 sessions.narrative_plan。
    completion_reason / fallback_reason：开场前可为空串；终局时 completion_reason 由 Phase 11.4+ 写入。
    """

    player_intent: str = Field(default="", max_length=8000)
    opening_anchor_event_id: int | None = None
    opening_anchor_order: int = 0
    opening_anchor_summary: str = ""
    arc_end_event_id: int | None = None
    arc_end_order: int = 0
    arc_goal: str = ""
    completion_conditions: list[dict[str, Any]] = Field(default_factory=list)
    current_timeline_order: int = 0
    completion_reason: str = ""
    fallback_reason: str = ""


def parse_narrative_plan(raw: dict[str, Any] | None) -> NarrativePlan:
    if not raw:
        return NarrativePlan()
    return NarrativePlan.model_validate({**NarrativePlan().model_dump(), **raw})


def narrative_plan_to_jsonable(plan: NarrativePlan) -> dict[str, Any]:
    return plan.model_dump(mode="json")
