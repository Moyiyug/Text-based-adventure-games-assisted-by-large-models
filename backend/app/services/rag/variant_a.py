"""方案 A：BM25 + Chroma + 加权 RRF。参照 IMPLEMENTATION_PLAN 3.2。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import TextChunk
from app.services.rag.base import BaseRetriever, RetrievedChunk, RetrievalResult
from app.services.rag.bm25_index import bm25_top_ids
from app.services.rag.chroma_query import chroma_query_chunk_ids

RRF_K = 60.0


def _weighted_rrf(
    bm25_ids: list[int],
    vector_ids_ordered: list[int],
    bm25_weight: float,
    final_top_k: int,
) -> list[tuple[int, float]]:
    """双路排名加权 RRF：bm25_weight 作用于 BM25 路，(1-w) 作用于向量路。"""
    w_b = max(0.0, min(1.0, float(bm25_weight)))
    w_v = 1.0 - w_b
    scores: dict[int, float] = {}
    for rank, cid in enumerate(bm25_ids, start=1):
        scores[cid] = scores.get(cid, 0.0) + w_b / (RRF_K + rank)
    for rank, cid in enumerate(vector_ids_ordered, start=1):
        scores[cid] = scores.get(cid, 0.0) + w_v / (RRF_K + rank)
    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return ordered[:final_top_k]


class NaiveHybridRetriever(BaseRetriever):
    async def retrieve(
        self,
        db: AsyncSession,
        query: str,
        story_version_id: int,
        config: dict,
    ) -> RetrievalResult:
        bm25_top_k = int(config.get("bm25_top_k", 10))
        vector_top_k = int(config.get("vector_top_k", 10))
        bm25_weight = float(config.get("bm25_weight", 0.3))
        final_top_k = int(config.get("final_top_k", 5))

        bm25_pairs = await bm25_top_ids(db, story_version_id, query, bm25_top_k)
        bm25_ids = [p[0] for p in bm25_pairs]

        vec_pairs = await chroma_query_chunk_ids(query, story_version_id, vector_top_k)
        vec_pairs_sorted = sorted(vec_pairs, key=lambda x: x[1])
        vector_ids_ordered = [p[0] for p in vec_pairs_sorted]

        fused = _weighted_rrf(bm25_ids, vector_ids_ordered, bm25_weight, final_top_k)
        if not fused:
            return RetrievalResult(chunks=[], structured=[], variant_type="naive_hybrid")

        id_list = [x[0] for x in fused]
        res = await db.execute(select(TextChunk).where(TextChunk.id.in_(id_list)))
        by_id = {c.id: c for c in res.scalars().all()}
        chunks: list[RetrievedChunk] = []
        for cid, score in fused:
            tc = by_id.get(cid)
            if tc is None:
                continue
            chunks.append(
                RetrievedChunk(
                    text_chunk_id=tc.id,
                    content=tc.content,
                    score=score,
                    source="fusion",
                    chapter_id=tc.chapter_id,
                    scene_id=tc.scene_id,
                )
            )
        return RetrievalResult(chunks=chunks, structured=[], variant_type="naive_hybrid")
