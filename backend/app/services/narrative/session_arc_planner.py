"""会话弧线规划（时间线锚点优先）。Phase 11.2 — 确定性规则，无 LLM。"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Chapter, Scene
from app.models.knowledge import TimelineEvent
from app.models.session import Session as NarrativeSession
from app.schemas.narrative_plan import (
    NarrativePlan,
    narrative_plan_to_jsonable,
    parse_narrative_plan,
)
from app.services.narrative.turn_context import word_jaccard_similarity
from app.services.rag.base import TimelineRetrievalBias

_OPENING_QUERY_MAX_CHARS = 2800
_TURN_QUERY_MAX_CHARS = 2800


def _word_set(s: str) -> set[str]:
    return {w for w in re.findall(r"[\w\u4e00-\u9fff]+", s) if len(w) > 1}


def _intent_related_to_event(intent: str, event_description: str) -> bool:
    if not intent.strip():
        return False
    if word_jaccard_similarity(intent, event_description) >= 0.06:
        return True
    return bool(_word_set(intent) & _word_set(event_description))


async def _anchor_summary_async(
    db: AsyncSession, ev: TimelineEvent
) -> str:
    base = ev.event_description.strip()
    if ev.chapter_id is None:
        return base[:800]
    ch = await db.get(Chapter, ev.chapter_id)
    if ch is None:
        return base[:800]
    title = (ch.title or "").strip() or f"第{ch.chapter_number}章"
    return f"{title}｜{base}"[:800]


async def _plan_from_timeline(
    db: AsyncSession,
    *,
    story_version_id: int,
    player_intent: str,
    events: list[TimelineEvent],
) -> NarrativePlan:
    related = [e for e in events if _intent_related_to_event(player_intent, e.event_description)]
    if related:
        anchor = min(related, key=lambda e: (e.order_index, e.id))
        fallback_reason = ""
    else:
        anchor = min(events, key=lambda e: (e.order_index, e.id))
        fallback_reason = "no_intent_match_used_earliest_timeline_event"

    last_ev = max(events, key=lambda e: (e.order_index, e.id))
    opening_summary = await _anchor_summary_async(db, anchor)
    completion_conditions: list[dict] = [
        {
            "type": "timeline_reached",
            "order": last_ev.order_index,
            "event_id": last_ev.id,
        }
    ]
    return NarrativePlan(
        player_intent=player_intent,
        opening_anchor_event_id=anchor.id,
        opening_anchor_order=anchor.order_index,
        opening_anchor_summary=opening_summary,
        arc_end_event_id=last_ev.id,
        arc_end_order=last_ev.order_index,
        arc_goal=f"沿时间线推进至次序 {last_ev.order_index} 附近并收束本会话弧线",
        completion_conditions=completion_conditions,
        current_timeline_order=anchor.order_index,
        completion_reason="",
        fallback_reason=fallback_reason,
    )


async def _plan_fallback_chapters(
    db: AsyncSession,
    *,
    story_version_id: int,
    player_intent: str,
    reason: str,
) -> NarrativePlan:
    res = await db.execute(
        select(Chapter)
        .where(Chapter.story_version_id == story_version_id)
        .order_by(Chapter.chapter_number.asc(), Chapter.id.asc())
    )
    chapters = list(res.scalars().all())
    if not chapters:
        return NarrativePlan(
            player_intent=player_intent,
            opening_anchor_order=0,
            opening_anchor_summary="（无章节与时间线元数据，检索与叙事将依赖通用证据）",
            arc_end_order=0,
            arc_goal="在可用证据下完成可玩的短弧线",
            completion_conditions=[
                {"type": "fallback_no_structure", "description": "无章节/时间线时的宽松条件"}
            ],
            current_timeline_order=0,
            fallback_reason=f"{reason}_no_chapters",
        )
    ch = chapters[0]
    title = (ch.title or "").strip() or f"第{ch.chapter_number}章"
    excerpt = (ch.raw_text or "").strip()[:500]
    summary = f"{title}：{excerpt}"
    last_ch = chapters[-1]
    return NarrativePlan(
        player_intent=player_intent,
        opening_anchor_order=0,
        opening_anchor_summary=summary[:800],
        arc_end_order=0,
        arc_goal=f"从 {title} 切入，可向作品后部（第{last_ch.chapter_number}章）方向推进至收束",
        completion_conditions=[
            {"type": "chapter_span", "start_chapter_id": ch.id, "end_chapter_id": last_ch.id}
        ],
        current_timeline_order=0,
        fallback_reason=reason,
    )


async def plan_session_arc(
    db: AsyncSession,
    session: NarrativeSession,
) -> NarrativePlan:
    """
    根据玩家意图与时间线事件规划弧线，写入应通过 apply_narrative_plan_to_session。
    """
    sv_id = session.story_version_id
    player_intent = (session.opening_goal or "").strip()

    res = await db.execute(
        select(TimelineEvent)
        .where(TimelineEvent.story_version_id == sv_id)
        .order_by(TimelineEvent.order_index.asc(), TimelineEvent.id.asc())
    )
    events = list(res.scalars().all())

    if not events:
        plan = await _plan_fallback_chapters(
            db,
            story_version_id=sv_id,
            player_intent=player_intent,
            reason="no_timeline_events",
        )
    else:
        plan = await _plan_from_timeline(
            db, story_version_id=sv_id, player_intent=player_intent, events=events
        )
    return plan


def apply_narrative_plan_to_session(
    session: NarrativeSession,
    plan: NarrativePlan,
    *,
    narrative_status: str = "opening_pending",
) -> None:
    session.narrative_plan = narrative_plan_to_jsonable(plan)
    session.narrative_status = narrative_status


def narrative_plan_needs_replan(session: NarrativeSession) -> bool:
    """迁移后 `{}` 或残缺 plan 需在开场前补算。"""
    if not session.narrative_plan:
        return True
    try:
        p = parse_narrative_plan(session.narrative_plan)
    except Exception:
        return True
    return not (p.opening_anchor_summary.strip() or p.arc_goal.strip())


async def build_opening_retrieval_query_text(
    db: AsyncSession,
    session: NarrativeSession,
) -> str:
    """
    开场 RAG 主 query：锚点摘要 + 相邻时间线事件描述；不以 opening_goal 为唯一依据。
    无可用结构时回退到 opening_goal /「开场」。
    """
    plan = parse_narrative_plan(session.narrative_plan)
    chunks: list[str] = []
    if plan.opening_anchor_summary.strip():
        chunks.append(plan.opening_anchor_summary.strip())

    res = await db.execute(
        select(TimelineEvent)
        .where(TimelineEvent.story_version_id == session.story_version_id)
        .order_by(TimelineEvent.order_index.asc(), TimelineEvent.id.asc())
    )
    events = list(res.scalars().all())
    anchor_order = plan.opening_anchor_order
    if events and plan.opening_anchor_event_id is not None:
        joined = "\n".join(chunks)
        for e in events:
            if abs(e.order_index - anchor_order) <= 1:
                d = e.event_description.strip()
                if d and d not in joined:
                    chunks.append(d)
                    joined = "\n".join(chunks)

    text = "\n".join(chunks).strip()
    if len(text) > _OPENING_QUERY_MAX_CHARS:
        text = text[:_OPENING_QUERY_MAX_CHARS]
    if text:
        return text
    return (session.opening_goal or "").strip() or "开场"


def _participants_for_query(raw: object) -> str:
    if not isinstance(raw, list):
        return ""
    names: list[str] = []
    for p in raw:
        if isinstance(p, str) and p.strip():
            names.append(p.strip())
        elif isinstance(p, dict):
            n = p.get("name") or p.get("entity")
            if isinstance(n, str) and n.strip():
                names.append(n.strip())
    return " ".join(names[:20])[:400]


async def build_turn_retrieval_query_and_bias(
    db: AsyncSession,
    *,
    story_version_id: int,
    plan: NarrativePlan,
    state: dict[str, object],
    user_input: str,
    neighbor_span: int = 1,
) -> tuple[str, TimelineRetrievalBias | None]:
    """
    回合 RAG：用户输入 + 当前时间线窗口内事件/章节/场景/参与者，并产出 TimelineRetrievalBias 供 naive_hybrid 加分。
    无时间线事件时降级为仅用户输入 + 锚点摘要，bias 为 None。
    """
    span = max(0, neighbor_span)
    res = await db.execute(
        select(TimelineEvent)
        .where(TimelineEvent.story_version_id == story_version_id)
        .order_by(TimelineEvent.order_index.asc(), TimelineEvent.id.asc())
    )
    events = list(res.scalars().all())
    user = (user_input or "").strip()

    if not events:
        tail = plan.opening_anchor_summary.strip()
        q = f"{user}\n{tail}".strip() if tail else user
        return (q[:_TURN_QUERY_MAX_CHARS] if q else user), None

    cur = plan.current_timeline_order
    exact = [e for e in events if e.order_index == cur]
    if exact:
        primary = min(exact, key=lambda e: e.id)
    else:
        primary = min(events, key=lambda e: (abs(e.order_index - cur), e.id))

    lo = primary.order_index - span
    hi = primary.order_index + span
    window = [e for e in events if lo <= e.order_index <= hi]

    all_cids = {e.chapter_id for e in window if e.chapter_id is not None}
    all_sids = {e.scene_id for e in window if e.scene_id is not None}
    pch, psc = primary.chapter_id, primary.scene_id
    nch = frozenset(c for c in all_cids if c != pch) if pch is not None else frozenset(all_cids)
    nsc = frozenset(s for s in all_sids if s != psc) if psc is not None else frozenset(all_sids)

    bias = TimelineRetrievalBias(
        primary_chapter_id=pch,
        primary_scene_id=psc,
        neighbor_chapter_ids=nch,
        neighbor_scene_ids=nsc,
    )

    parts: list[str] = [user]
    if plan.opening_anchor_summary.strip():
        parts.append(f"[弧线锚点摘要]\n{plan.opening_anchor_summary.strip()}"[:600])

    loc = state.get("current_location")
    if isinstance(loc, str) and loc.strip():
        parts.append(f"[当前地点]\n{loc.strip()[:200]}")
    npc = state.get("npc_relations")
    if isinstance(npc, dict) and npc:
        keys = " ".join(str(k) for k in list(npc.keys())[:15])
        if keys:
            parts.append(f"[涉及人物]\n{keys[:300]}")

    for e in window:
        line = e.event_description.strip()
        if line:
            parts.append(line[:500])
        if e.chapter_id is not None:
            ch = await db.get(Chapter, e.chapter_id)
            if ch is not None:
                title = (ch.title or "").strip() or f"第{ch.chapter_number}章"
                sm = (ch.summary or "").strip()[:200]
                parts.append(f"[章节]{title}{('｜' + sm) if sm else ''}"[:400])
        if e.scene_id is not None:
            sc = await db.get(Scene, e.scene_id)
            if sc is not None:
                sm = (sc.summary or "").strip()[:200]
                parts.append(f"[场景]{sm}"[:300])
        ps = _participants_for_query(e.participants)
        if ps:
            parts.append(f"[参与者]{ps}")

    text = "\n".join(parts).strip()
    if len(text) > _TURN_QUERY_MAX_CHARS:
        text = text[:_TURN_QUERY_MAX_CHARS]
    return text, bias
