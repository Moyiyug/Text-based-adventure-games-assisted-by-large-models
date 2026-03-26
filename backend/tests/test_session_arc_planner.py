"""Session arc planner：时间线锚点优先、fallback 与开场检索 query。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.schemas.narrative_plan import NarrativePlan, narrative_plan_to_jsonable
from app.services.narrative.session_arc_planner import (
    _plan_fallback_chapters,
    _plan_from_timeline,
    build_opening_retrieval_query_text,
    narrative_plan_needs_replan,
)


class _Ev:
    __slots__ = ("id", "order_index", "event_description", "chapter_id")

    def __init__(
        self,
        id: int,
        order_index: int,
        event_description: str,
        chapter_id: int | None = None,
    ) -> None:
        self.id = id
        self.order_index = order_index
        self.event_description = event_description
        self.chapter_id = chapter_id


def test_early_related_event_wins_over_later() -> None:
    async def _run() -> None:
        db = AsyncMock()
        db.get = AsyncMock(return_value=None)
        # 英文分词保证「dragon」「king」在两段中均为独立词，Jaccard 可同时命中早/晚事件
        events = [
            _Ev(1, 50, "final battle with the dragon king at the castle"),
            _Ev(2, 5, "village rumors about the dragon king awakening"),
        ]
        plan = await _plan_from_timeline(
            db, story_version_id=1, player_intent="dragon king legend", events=events
        )
        assert plan.opening_anchor_order == 5
        assert plan.opening_anchor_event_id == 2
        assert plan.fallback_reason == ""

    asyncio.run(_run())


def test_no_intent_match_picks_earliest_timeline() -> None:
    async def _run() -> None:
        db = AsyncMock()
        db.get = AsyncMock(return_value=None)
        events = [
            _Ev(1, 10, "完全无关的后期事件"),
            _Ev(2, 1, "更早的起始事件"),
        ]
        plan = await _plan_from_timeline(
            db, story_version_id=1, player_intent="量子力学", events=events
        )
        assert plan.opening_anchor_order == 1
        assert plan.fallback_reason == "no_intent_match_used_earliest_timeline_event"

    asyncio.run(_run())


def test_no_timeline_events_chapter_fallback() -> None:
    async def _run() -> None:
        db = AsyncMock()
        ch = SimpleNamespace(
            id=7, chapter_number=1, title="序章", raw_text="开端段落" * 20
        )
        res = MagicMock()
        res.scalars.return_value.all.return_value = [ch]
        db.execute = AsyncMock(return_value=res)

        plan = await _plan_fallback_chapters(
            db,
            story_version_id=1,
            player_intent="探索",
            reason="no_timeline_events",
        )
        assert plan.fallback_reason == "no_timeline_events"
        assert "序章" in plan.opening_anchor_summary

    asyncio.run(_run())


def test_narrative_plan_needs_replan_empty() -> None:
    s = SimpleNamespace(narrative_plan={})
    assert narrative_plan_needs_replan(s) is True


def test_narrative_plan_needs_replan_ok() -> None:
    p = NarrativePlan(
        player_intent="x",
        opening_anchor_summary="有摘要",
        arc_goal="目标",
    )
    s = SimpleNamespace(narrative_plan=narrative_plan_to_jsonable(p))
    assert narrative_plan_needs_replan(s) is False


def test_build_opening_retrieval_query_includes_neighbors() -> None:
    async def _run() -> None:
        plan = NarrativePlan(
            player_intent="t",
            opening_anchor_event_id=2,
            opening_anchor_order=5,
            opening_anchor_summary="锚点摘要",
            arc_end_order=10,
            arc_goal="g",
            current_timeline_order=5,
        )
        sess = SimpleNamespace(
            story_version_id=1,
            opening_goal="意图",
            narrative_plan=narrative_plan_to_jsonable(plan),
        )
        evs = [
            _Ev(1, 4, "邻居前"),
            _Ev(2, 5, "锚点事件正文"),
            _Ev(3, 6, "邻居后"),
        ]
        res = MagicMock()
        res.scalars.return_value.all.return_value = evs
        db = AsyncMock()
        db.execute = AsyncMock(return_value=res)

        q = await build_opening_retrieval_query_text(db, sess)
        assert "锚点摘要" in q
        assert "邻居前" in q
        assert "锚点事件正文" in q
        assert "邻居后" in q

    asyncio.run(_run())


def test_narrative_plan_model_fields() -> None:
    p = NarrativePlan(
        player_intent="a",
        opening_anchor_event_id=1,
        opening_anchor_order=2,
        opening_anchor_summary="s",
        arc_end_event_id=9,
        arc_end_order=9,
        arc_goal="g",
        completion_conditions=[{"type": "t"}],
        current_timeline_order=2,
        completion_reason="",
        fallback_reason="",
    )
    d = narrative_plan_to_jsonable(p)
    for k in (
        "player_intent",
        "opening_anchor_event_id",
        "opening_anchor_order",
        "opening_anchor_summary",
        "arc_end_event_id",
        "arc_end_order",
        "arc_goal",
        "completion_conditions",
        "current_timeline_order",
        "completion_reason",
        "fallback_reason",
    ):
        assert k in d
