"""方案 B：子块向量命中 + 父级 Scene/Chapter 摘要与邻块扩展。参照 IMPLEMENTATION_PLAN 3.3。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Chapter, Scene, TextChunk
from app.services.rag.base import BaseRetriever, RetrievedChunk, RetrievalResult
from app.services.rag.chroma_query import chroma_query_chunk_ids


def _clip(s: str | None, n: int = 500) -> str:
    if not s:
        return ""
    s = s.strip()
    return s if len(s) <= n else s[: n - 1] + "…"


class ParentChildRetriever(BaseRetriever):
    async def retrieve(
        self,
        db: AsyncSession,
        query: str,
        story_version_id: int,
        config: dict,
    ) -> RetrievalResult:
        child_top_k = int(config.get("child_top_k", 5))
        parent_expand = int(config.get("parent_expand", 2))

        vec_pairs = await chroma_query_chunk_ids(query, story_version_id, child_top_k)
        vec_pairs_sorted = sorted(vec_pairs, key=lambda x: x[1])
        hit_ids = [p[0] for p in vec_pairs_sorted]
        if not hit_ids:
            return RetrievalResult(chunks=[], structured=[], variant_type="parent_child")

        res = await db.execute(select(TextChunk).where(TextChunk.id.in_(hit_ids)))
        by_id = {c.id: c for c in res.scalars().all()}
        chunks: list[RetrievedChunk] = []
        for rank, cid in enumerate(hit_ids, start=1):
            tc = by_id.get(cid)
            if tc is None:
                continue
            parent_ctx = await self._build_parent_context(
                db, story_version_id, tc, parent_expand
            )
            # 分数：用排名倒数模拟，与距离序一致
            score = 1.0 / float(rank)
            chunks.append(
                RetrievedChunk(
                    text_chunk_id=tc.id,
                    content=tc.content,
                    score=score,
                    source="parent_child",
                    chapter_id=tc.chapter_id,
                    scene_id=tc.scene_id,
                    parent_context=parent_ctx or None,
                )
            )
        return RetrievalResult(chunks=chunks, structured=[], variant_type="parent_child")

    async def _build_parent_context(
        self,
        db: AsyncSession,
        story_version_id: int,
        tc: TextChunk,
        parent_expand: int,
    ) -> str:
        parts: list[str] = []
        ch: Chapter | None = None
        if tc.chapter_id:
            ch = await db.get(Chapter, tc.chapter_id)
            if ch:
                line = ch.summary or _clip(ch.raw_text, 600)
                if line:
                    parts.append(f"【章】{line}")
        sc: Scene | None = None
        if tc.scene_id:
            sc = await db.get(Scene, tc.scene_id)
            if sc:
                line = sc.summary or _clip(sc.raw_text, 600)
                if line:
                    parts.append(f"【场景】{line}")
        if parent_expand > 0 and tc.scene_id:
            sres = await db.execute(
                select(TextChunk)
                .where(
                    TextChunk.story_version_id == story_version_id,
                    TextChunk.scene_id == tc.scene_id,
                    TextChunk.id != tc.id,
                )
                .order_by(TextChunk.chunk_index)
                .limit(parent_expand)
            )
            sibs = list(sres.scalars().all())
            if sibs:
                extra = "\n".join(_clip(s.content, 400) for s in sibs)
                parts.append("【同场景邻块】\n" + extra)
        return "\n".join(parts).strip()
