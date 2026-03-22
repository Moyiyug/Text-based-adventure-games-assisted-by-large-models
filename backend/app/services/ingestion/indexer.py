"""Chroma 向量索引 + SiliconFlow Embedding。参照 IMPLEMENTATION_PLAN Phase 2.8。"""

from __future__ import annotations

from typing import Sequence

import chromadb
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.content import TextChunk
from app.services.ingestion.embeddings import embed_texts


COLLECTION_NAME = "story_text_chunks"


def _get_client() -> chromadb.PersistentClient:
    path = str(settings.chroma_dir_path)
    settings.chroma_dir_path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=path)


def get_chunks_collection():
    client = _get_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def delete_embeddings_for_story_version(story_version_id: int) -> None:
    coll = get_chunks_collection()
    try:
        coll.delete(where={"story_version_id": str(story_version_id)})
    except Exception:  # noqa: BLE001
        # 集合为空或旧数据无该字段时可能异常，忽略
        pass


def delete_embeddings_for_text_chunk_ids(chunk_ids: list[int]) -> None:
    """按 TextChunk 主键删除 Chroma 中对应向量（ids 形如 tc_{id}）。"""
    if not chunk_ids:
        return
    coll = get_chunks_collection()
    ids = [f"tc_{i}" for i in chunk_ids]
    try:
        coll.delete(ids=ids)
    except Exception:  # noqa: BLE001
        pass


async def embed_and_store_chunks(
    db: AsyncSession,
    story_version_id: int,
    chunks: Sequence[TextChunk],
) -> tuple[int, list[str]]:
    """
    为已落库的 TextChunk 生成向量并写入 Chroma；回写 chroma_id。
    返回 (成功条数, warnings)。
    """
    warnings: list[str] = []
    if not chunks:
        return 0, warnings

    if not settings.SILICONFLOW_API_KEY.strip():
        warnings.append("跳过向量索引：SILICONFLOW_API_KEY 未配置")
        return 0, warnings

    texts = [c.content for c in chunks]
    try:
        vectors = await embed_texts(texts)
    except Exception as e:  # noqa: BLE001
        warnings.append(f"Embedding 调用失败: {e}")
        return 0, warnings

    if len(vectors) != len(chunks):
        warnings.append("向量条数与切块不一致，跳过写入")
        return 0, warnings

    coll = get_chunks_collection()
    ids = [f"tc_{c.id}" for c in chunks]
    metadatas = [
        {
            "story_version_id": str(story_version_id),
            "text_chunk_id": str(c.id),
            "chapter_id": str(c.chapter_id) if c.chapter_id is not None else "",
            "scene_id": str(c.scene_id) if c.scene_id is not None else "",
        }
        for c in chunks
    ]

    if hasattr(coll, "upsert"):
        coll.upsert(
            ids=ids,
            embeddings=vectors,
            documents=texts,
            metadatas=metadatas,
        )
    else:
        coll.add(
            ids=ids,
            embeddings=vectors,
            documents=texts,
            metadatas=metadatas,
        )

    for c, cid in zip(chunks, ids, strict=True):
        c.chroma_id = cid
    await db.flush()
    return len(chunks), warnings


async def delete_all_chunks_for_version(db: AsyncSession, story_version_id: int) -> None:
    """删除某版本在 DB 中记录的向量 id 并清理 Chroma。"""
    delete_embeddings_for_story_version(story_version_id)
    result = await db.execute(
        select(TextChunk).where(TextChunk.story_version_id == story_version_id)
    )
    for row in result.scalars().all():
        row.chroma_id = None
    await db.flush()
