"""Chroma 向量检索（与 indexer 同集合）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.ingestion.embeddings import embed_texts
from app.services.ingestion.indexer import get_chunks_collection

if TYPE_CHECKING:
    pass


async def chroma_query_chunk_ids(
    query: str,
    story_version_id: int,
    top_k: int,
) -> list[tuple[int, float]]:
    """
    返回 (text_chunk_id, distance)，distance 越小越相似（Chroma 默认 L2）。
    """
    if top_k <= 0:
        return []
    vecs = await embed_texts([query])
    if not vecs:
        return []
    coll = get_chunks_collection()
    try:
        raw = coll.query(
            query_embeddings=[vecs[0]],
            n_results=max(1, top_k),
            where={"story_version_id": str(story_version_id)},
            include=["distances", "metadatas"],
        )
    except Exception:  # noqa: BLE001
        return []
    ids_out: list[tuple[int, float]] = []
    dist_lists = raw.get("distances") or []
    meta_lists = raw.get("metadatas") or []
    if not dist_lists or not meta_lists:
        return []
    for dist, meta in zip(dist_lists[0], meta_lists[0], strict=False):
        if not meta:
            continue
        tid = meta.get("text_chunk_id")
        if tid is None:
            continue
        try:
            cid = int(tid)
        except (TypeError, ValueError):
            continue
        d = float(dist) if dist is not None else 1e9
        ids_out.append((cid, d))
    return ids_out
