"""方案 C：DeepSeek 抽实体名 + DB 结构化查询 + Chroma 文本补充。参照 IMPLEMENTATION_PLAN 3.4。"""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import TextChunk
from app.models.knowledge import Entity, Relationship, TimelineEvent
from app.services.llm.deepseek import deepseek_chat
from app.services.rag.base import BaseRetriever, RetrievedChunk, RetrievalResult, StructuredHit
from app.services.rag.chroma_query import chroma_query_chunk_ids


def _parse_entity_json(raw: str) -> list[str]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text, flags=re.DOTALL)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    names = data.get("entity_names") if isinstance(data, dict) else None
    if not isinstance(names, list):
        return []
    out: list[str] = []
    for x in names:
        if isinstance(x, str) and len(x.strip()) >= 1:
            out.append(x.strip())
    return list(dict.fromkeys(out))


async def extract_query_entity_names(query: str) -> list[str]:
    prompt = (
        "从用户问题中提取可能的小说人物、地点、组织名。"
        '严格只输出 JSON：{"entity_names":["名称1","名称2"]}。没有则 entity_names 为空数组。不要 Markdown。'
        f"\n\n问题：\n{query[:1200]}"
    )
    try:
        raw = await deepseek_chat([{"role": "user", "content": prompt}], temperature=0.1)
        return _parse_entity_json(raw)
    except Exception:  # noqa: BLE001
        return []


class StructuredRetriever(BaseRetriever):
    async def retrieve(
        self,
        db: AsyncSession,
        query: str,
        story_version_id: int,
        config: dict,
    ) -> RetrievalResult:
        text_top_k = int(config.get("text_top_k", 3))
        event_top_k = int(config.get("event_top_k", 5))

        names = await extract_query_entity_names(query)
        if len(query.strip()) >= 2 and query.strip() not in names:
            names.append(query.strip()[:80])

        structured: list[StructuredHit] = []
        entity_ids: set[int] = set()
        seen_entity_row: set[int] = set()

        for name in names:
            if len(name) < 2:
                continue
            eres = await db.execute(
                select(Entity).where(
                    Entity.story_version_id == story_version_id,
                    or_(
                        Entity.name.contains(name),
                        Entity.canonical_name.contains(name),
                    ),
                ).limit(20)
            )
            for ent in eres.scalars().all():
                entity_ids.add(ent.id)
                if ent.id in seen_entity_row:
                    continue
                seen_entity_row.add(ent.id)
                structured.append(
                    StructuredHit(
                        kind="entity",
                        payload={
                            "id": ent.id,
                            "name": ent.name,
                            "canonical_name": ent.canonical_name,
                            "entity_type": ent.entity_type,
                            "description": ent.description,
                        },
                    )
                )

        seen_rel: set[int] = set()
        if entity_ids:
            rel_res = await db.execute(
                select(Relationship).where(
                    Relationship.story_version_id == story_version_id,
                    or_(
                        Relationship.entity_a_id.in_(entity_ids),
                        Relationship.entity_b_id.in_(entity_ids),
                    ),
                ).limit(30)
            )
            for rel in rel_res.scalars().all():
                if rel.id in seen_rel:
                    continue
                seen_rel.add(rel.id)
                structured.append(
                    StructuredHit(
                        kind="relationship",
                        payload={
                            "id": rel.id,
                            "entity_a_id": rel.entity_a_id,
                            "entity_b_id": rel.entity_b_id,
                            "relationship_type": rel.relationship_type,
                            "description": rel.description,
                        },
                    )
                )

        tl_conditions: list[Any] = []
        for name in names:
            if len(name) >= 2:
                tl_conditions.append(TimelineEvent.event_description.contains(name))
        seen_tl: set[int] = set()
        if tl_conditions:
            tq = (
                select(TimelineEvent)
                .where(
                    TimelineEvent.story_version_id == story_version_id,
                    or_(*tl_conditions),
                )
                .order_by(TimelineEvent.order_index)
                .limit(event_top_k)
            )
            tres = await db.execute(tq)
            for ev in tres.scalars().all():
                if ev.id in seen_tl:
                    continue
                seen_tl.add(ev.id)
                structured.append(
                    StructuredHit(
                        kind="timeline",
                        payload={
                            "id": ev.id,
                            "event_description": ev.event_description,
                            "order_index": ev.order_index,
                            "chapter_id": ev.chapter_id,
                            "scene_id": ev.scene_id,
                            "participants": list(ev.participants or []),
                        },
                    )
                )

        vec_pairs = await chroma_query_chunk_ids(query, story_version_id, text_top_k)
        vec_sorted = sorted(vec_pairs, key=lambda x: x[1])
        hit_ids = [p[0] for p in vec_sorted]
        chunks: list[RetrievedChunk] = []
        if hit_ids:
            res = await db.execute(select(TextChunk).where(TextChunk.id.in_(hit_ids)))
            by_id = {c.id: c for c in res.scalars().all()}
            for rank, cid in enumerate(hit_ids, start=1):
                tc = by_id.get(cid)
                if tc is None:
                    continue
                chunks.append(
                    RetrievedChunk(
                        text_chunk_id=tc.id,
                        content=tc.content,
                        score=1.0 / float(rank),
                        source="text",
                        chapter_id=tc.chapter_id,
                        scene_id=tc.scene_id,
                    )
                )

        return RetrievalResult(
            chunks=chunks,
            structured=structured,
            variant_type="structured",
        )
