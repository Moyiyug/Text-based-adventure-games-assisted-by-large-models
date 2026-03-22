"""按 story_version 构建 BM25 索引（进程内缓存）。"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from rank_bm25 import BM25Okapi
from sqlalchemy import select

from app.models.content import TextChunk

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# story_version_id -> (BM25Okapi, list of chunk ids in corpus order)
_bm25_cache: dict[int, tuple[BM25Okapi, list[int]]] = {}


def invalidate_bm25_cache(story_version_id: int | None = None) -> None:
    """清除缓存；None 表示全部。"""
    global _bm25_cache
    if story_version_id is None:
        _bm25_cache.clear()
    else:
        _bm25_cache.pop(story_version_id, None)


def tokenize_for_bm25(text: str) -> list[str]:
    """中英混合 MVP：连续英文/数字为词，单字 CJK 为词。"""
    if not text or not text.strip():
        return ["empty"]
    tokens: list[str] = []
    for m in re.finditer(r"[a-zA-Z0-9]+|[\u4e00-\u9fff]", text.lower()):
        tokens.append(m.group(0))
    return tokens if tokens else ["empty"]


async def get_bm25_for_version(db: AsyncSession, story_version_id: int) -> tuple[BM25Okapi, list[int]]:
    if story_version_id in _bm25_cache:
        return _bm25_cache[story_version_id]
    res = await db.execute(
        select(TextChunk.id, TextChunk.content)
        .where(TextChunk.story_version_id == story_version_id)
        .order_by(TextChunk.chunk_index)
    )
    rows = list(res.all())
    ids = [r[0] for r in rows]
    corpus = [tokenize_for_bm25(r[1] or "") for r in rows]
    if not corpus:
        bm25 = BM25Okapi([["empty"]])
        pair = (bm25, [])
    else:
        bm25 = BM25Okapi(corpus)
        pair = (bm25, ids)
    _bm25_cache[story_version_id] = pair
    return pair


async def bm25_top_ids(
    db: AsyncSession,
    story_version_id: int,
    query: str,
    top_k: int,
) -> list[tuple[int, float]]:
    """返回 (chunk_id, bm25_score) 降序。"""
    bm25, ids = await get_bm25_for_version(db, story_version_id)
    if not ids:
        return []
    q_tokens = tokenize_for_bm25(query)
    scores = bm25.get_scores(q_tokens)
    ranked = sorted(zip(ids, scores, strict=True), key=lambda x: x[1], reverse=True)
    return ranked[:top_k]
