"""assemble_context 画像前置与 profile_loader 单测。"""

from app.services.profile_loader import profile_bundle_nonempty
from app.services.rag.base import RetrievedChunk, RetrievalResult
from app.services.rag.context import assemble_context


def test_profile_bundle_nonempty() -> None:
    assert not profile_bundle_nonempty(None)
    assert not profile_bundle_nonempty({})
    assert not profile_bundle_nonempty({"user_preferences": {}, "story_overrides": {}})
    assert profile_bundle_nonempty(
        {"user_preferences": {"tone": "dark"}, "story_overrides": {}}
    )
    assert profile_bundle_nonempty(
        {"user_preferences": {}, "story_overrides": {"pace": "slow"}}
    )


def test_assemble_context_prepends_profile_blocks() -> None:
    r = RetrievalResult(
        chunks=[
            RetrievedChunk(text_chunk_id=1, content="chunk正文", score=1.0, source="x"),
        ],
        structured=[],
        variant_type="naive_hybrid",
    )
    profile = {
        "user_preferences": {"favorite_genre": "悬疑"},
        "story_overrides": {"pace": "slow"},
    }
    out = assemble_context(r, token_budget=4000, profile=profile)
    assert "[用户画像-全局]" in out
    assert "悬疑" in out
    assert "[用户画像-本作品覆写]" in out
    assert "slow" in out
    assert "chunk正文" in out
    assert out.index("[用户画像-全局]") < out.index("chunk正文")


def test_assemble_context_profile_dropped_last_under_tight_budget() -> None:
    """预算极小时优先丢检索块，画像块尽量保留（列表尾部先 pop）。"""
    long_chunk = "Z" * 500
    r = RetrievalResult(
        chunks=[RetrievedChunk(text_chunk_id=1, content=long_chunk, score=1.0, source="x")],
        structured=[],
        variant_type="naive_hybrid",
    )
    profile = {"user_preferences": {"k": "v"}, "story_overrides": {}}
    out = assemble_context(r, token_budget=40, profile=profile)
    assert "[用户画像-全局]" in out
    assert "k" in out and "v" in out
