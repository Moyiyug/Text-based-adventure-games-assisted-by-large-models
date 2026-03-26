"""按 RagConfig 分发到具体检索变体。参照 IMPLEMENTATION_PLAN 3.5。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rag_config import RagConfig
from app.services.rag.base import RetrievalResult, TimelineRetrievalBias
from app.services.rag.variant_a import NaiveHybridRetriever
from app.services.rag.variant_b import ParentChildRetriever
from app.services.rag.variant_c import StructuredRetriever


async def get_rag_config_by_id(db: AsyncSession, config_id: int) -> RagConfig | None:
    return await db.get(RagConfig, config_id)


async def get_active_rag_config(db: AsyncSession) -> RagConfig:
    res = await db.execute(select(RagConfig).where(RagConfig.is_active.is_(True)))
    row = res.scalar_one_or_none()
    if row is None:
        raise ValueError("无激活的 RAG 配置，请运行 scripts/seed_rag_configs.py 并在管理端激活一条")
    return row


async def dispatch_retrieve(
    db: AsyncSession,
    query: str,
    story_version_id: int,
    rag_config_id: int | None = None,
    *,
    timeline_bias: TimelineRetrievalBias | None = None,
) -> RetrievalResult:
    if rag_config_id is not None:
        rc = await get_rag_config_by_id(db, rag_config_id)
        if rc is None:
            raise ValueError(f"rag_config id={rag_config_id} 不存在")
    else:
        rc = await get_active_rag_config(db)
    cfg = dict(rc.config or {})
    vt = (rc.variant_type or "").strip()
    if vt == "naive_hybrid":
        return await NaiveHybridRetriever().retrieve(
            db, query, story_version_id, cfg, timeline_bias=timeline_bias
        )
    if vt == "parent_child":
        return await ParentChildRetriever().retrieve(
            db, query, story_version_id, cfg, timeline_bias=timeline_bias
        )
    if vt == "structured":
        return await StructuredRetriever().retrieve(
            db, query, story_version_id, cfg, timeline_bias=timeline_bias
        )
    raise ValueError(f"未知 variant_type: {vt}")
