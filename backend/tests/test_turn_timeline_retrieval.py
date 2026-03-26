"""回合检索：时间线 query 拼装与 naive_hybrid 分数加权。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.content import Chapter, Scene
from app.models.knowledge import TimelineEvent
from app.schemas.narrative_plan import NarrativePlan
from app.services.narrative.session_arc_planner import build_turn_retrieval_query_and_bias
from app.services.rag.base import TimelineRetrievalBias
from app.services.rag.variant_a import apply_timeline_boost_to_fused_scores


def test_apply_timeline_boost_primary_chapter_ranks_first() -> None:
    bias = TimelineRetrievalBias(
        primary_chapter_id=10,
        primary_scene_id=None,
        neighbor_chapter_ids=frozenset(),
        neighbor_scene_ids=frozenset(),
    )
    fused = [(1, 2.0), (2, 1.9)]
    by_id = {
        1: SimpleNamespace(chapter_id=99, scene_id=None),
        2: SimpleNamespace(chapter_id=10, scene_id=None),
    }
    out = apply_timeline_boost_to_fused_scores(
        fused, by_id, bias, boost_primary=2.0, boost_neighbor=1.1
    )
    assert out[0][0] == 2
    assert out[0][1] > out[1][1]


def test_apply_timeline_boost_none_unchanged_order() -> None:
    fused = [(1, 1.0), (2, 0.5)]
    by_id = {
        1: SimpleNamespace(chapter_id=10, scene_id=None),
        2: SimpleNamespace(chapter_id=20, scene_id=None),
    }
    out = apply_timeline_boost_to_fused_scores(fused, by_id, None, 2.0, 1.1)
    assert out == fused


def test_build_turn_retrieval_no_events_fallback() -> None:
    async def _run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with SessionLocal() as db:
            plan = NarrativePlan(
                opening_anchor_summary="序章摘要",
                current_timeline_order=1,
            )
            q, bias = await build_turn_retrieval_query_and_bias(
                db,
                story_version_id=1,
                plan=plan,
                state={},
                user_input="调查",
                neighbor_span=1,
            )
            assert "调查" in q
            assert "序章摘要" in q
            assert bias is None
        await engine.dispose()

    asyncio.run(_run())


def test_build_turn_retrieval_with_events_chapter_and_bias() -> None:
    async def _run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with SessionLocal() as db:
            db.add(
                Chapter(
                    story_version_id=1,
                    chapter_number=1,
                    title="雾港",
                    raw_text="x",
                    summary="港口夜雾",
                )
            )
            await db.flush()
            ch_id = 1
            db.add(Scene(chapter_id=ch_id, scene_number=1, raw_text="y", summary="码头"))
            await db.flush()
            sc_id = 1
            db.add(
                TimelineEvent(
                    story_version_id=1,
                    event_description="主角抵达码头",
                    chapter_id=ch_id,
                    scene_id=sc_id,
                    order_index=100,
                    participants=["阿兰"],
                )
            )
            await db.commit()

            plan = NarrativePlan(
                opening_anchor_summary="锚点",
                current_timeline_order=100,
            )
            q, bias = await build_turn_retrieval_query_and_bias(
                db,
                story_version_id=1,
                plan=plan,
                state={"current_location": "码头", "npc_relations": {"老者": "初遇"}},
                user_input="环顾四周",
                neighbor_span=0,
            )
            assert "环顾四周" in q
            assert "主角抵达码头" in q
            assert "雾港" in q
            assert "码头" in q
            assert "阿兰" in q
            assert "老者" in q
            assert bias is not None
            assert bias.primary_chapter_id == ch_id
            assert bias.primary_scene_id == sc_id
        await engine.dispose()

    asyncio.run(_run())
