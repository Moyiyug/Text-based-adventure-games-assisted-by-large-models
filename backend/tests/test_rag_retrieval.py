"""RAG 检索：加权 RRF、上下文拼装、调度器错误路径单元测试。"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.rag.base import RetrievedChunk, RetrievalResult, StructuredHit
from app.services.rag.context import assemble_context
from app.services.rag.dispatcher import dispatch_retrieve
from app.services.rag.variant_a import RRF_K, _weighted_rrf


def test_weighted_rrf_bm25_only_rank_one() -> None:
    """BM25 路 rank=1 时贡献 w_b / (RRF_K + 1)。"""
    bm25_ids = [10]
    vector_ids: list[int] = []
    w = 0.3
    out = _weighted_rrf(bm25_ids, vector_ids, w, final_top_k=5)
    assert len(out) == 1
    assert out[0][0] == 10
    assert out[0][1] == pytest.approx(w / (RRF_K + 1))


def test_weighted_rrf_merges_duplicate_ids() -> None:
    """同 id 在两路均出现时分数相加。"""
    bm25_ids = [1, 2]
    vector_ids = [2, 3]
    w_b = 0.5
    out = _weighted_rrf(bm25_ids, vector_ids, w_b, final_top_k=10)
    by_id = dict(out)
    assert 2 in by_id
    s2 = by_id[2]
    s2_expected = w_b / (RRF_K + 2) + (1.0 - w_b) / (RRF_K + 1)
    assert s2 == pytest.approx(s2_expected)


def test_assemble_context_respects_token_budget() -> None:
    long = "段落" * 2000
    r = RetrievalResult(
        chunks=[RetrievedChunk(text_chunk_id=1, content=long, score=1.0, source="fusion")],
        structured=[],
        variant_type="naive_hybrid",
    )
    out = assemble_context(r, token_budget=80)
    assert len(out) < len(long)
    assert "截断" in out or len(out) <= len(long)


def test_assemble_context_structured_before_chunks() -> None:
    r = RetrievalResult(
        chunks=[RetrievedChunk(text_chunk_id=1, content="子", score=1.0, source="fusion")],
        structured=[StructuredHit(kind="entity", payload={"name": "Alice"})],
        variant_type="structured",
    )
    out = assemble_context(r, token_budget=4000)
    assert "entity" in out
    assert "Alice" in out
    assert "子" in out


def test_dispatch_retrieve_unknown_variant_raises() -> None:
    async def _run() -> None:
        db = AsyncMock()
        rc = MagicMock()
        rc.config = {}
        rc.variant_type = "unknown_xyz"
        db.get = AsyncMock(return_value=rc)
        with pytest.raises(ValueError, match="未知 variant_type"):
            await dispatch_retrieve(db, "query", story_version_id=1, rag_config_id=99)

    asyncio.run(_run())
