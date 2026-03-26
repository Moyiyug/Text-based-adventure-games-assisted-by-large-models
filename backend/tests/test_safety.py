"""叙事安全层单测（mock DeepSeek，无网络）。"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from openai import APIStatusError

from app.models.session import Session as NarrativeSession
from app.services.narrative.engine import process_turn_sse
from app.services.narrative.safety import (
    handle_api_block,
    is_likely_content_policy_block,
    soften_content,
)


def test_is_likely_content_policy_block_positive() -> None:
    assert is_likely_content_policy_block(
        RuntimeError("Request blocked due to content policy")
    )
    assert is_likely_content_policy_block(RuntimeError("moderation failed"))


def test_is_likely_content_policy_block_negative() -> None:
    assert not is_likely_content_policy_block(RuntimeError("connection reset"))
    assert not is_likely_content_policy_block(ValueError("bad input"))


def test_is_likely_content_policy_block_api_status() -> None:
    err = MagicMock(spec=APIStatusError)
    err.status_code = 400
    err.message = "content policy violation"
    assert is_likely_content_policy_block(err)


def test_handle_api_block_shape() -> None:
    fb = handle_api_block(42, "kick door")
    assert fb.narrative
    assert len(fb.choices) >= 1
    assert "session_id=42" in fb.log_message


def test_soften_content_delegates_to_deepseek() -> None:
    async def _inner() -> str:
        with patch(
            "app.services.narrative.safety.deepseek_chat",
            new_callable=AsyncMock,
            return_value="  柔和版  ",
        ) as m_chat:
            out = await soften_content("血腥描写")
        m_chat.assert_awaited_once()
        return out

    assert asyncio.run(_inner()) == "柔和版"


def test_process_turn_sse_content_policy_rollback() -> None:
    async def _failing_stream(*_a, **_kw):
        raise RuntimeError("blocked: content policy violation")
        yield ""  # pragma: no cover

    session = MagicMock(spec=NarrativeSession)
    session.id = 5
    session.user_id = 1
    session.story_id = 2
    session.story_version_id = 3
    session.rag_config_id = 1
    session.mode = "strict"
    session.style_config = {}
    session.turn_count = 0
    session.narrative_status = "in_progress"
    session.narrative_plan = {}

    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.rollback = AsyncMock()
    db.refresh = AsyncMock()
    db.commit = AsyncMock()

    async def _run() -> list[str]:
        lines: list[str] = []
        with (
            patch(
                "app.services.narrative.engine.deepseek_chat_stream",
                side_effect=_failing_stream,
            ),
            patch(
                "app.services.narrative.engine.load_prompt_templates",
                new_callable=AsyncMock,
                return_value={"system": "s", "gm": "g", "style": "x", "retrieval": "{context}"},
            ),
            patch(
                "app.services.narrative.engine.load_session_profile_bundle",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "app.services.narrative.engine.get_rag_config_by_id",
                new_callable=AsyncMock,
                return_value=MagicMock(config={}),
            ),
            patch(
                "app.services.narrative.engine.build_turn_retrieval_query_and_bias",
                new_callable=AsyncMock,
                return_value=("hello", None),
            ),
            patch(
                "app.services.narrative.engine.dispatch_retrieve",
                new_callable=AsyncMock,
            ) as m_ret,
            patch(
                "app.services.narrative.engine.assemble_context",
                return_value="ctx",
            ),
            patch(
                "app.services.narrative.engine.build_generation_prompt",
                return_value=[{"role": "user", "content": "x"}],
            ),
            patch(
                "app.services.narrative.engine._latest_state_dict",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "app.services.narrative.engine._message_history",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.services.narrative.engine.schedule_profile_inference_after_turn",
                MagicMock(),
            ),
        ):
            from app.services.rag.base import RetrievalResult

            m_ret.return_value = RetrievalResult(
                chunks=[], structured=[], variant_type="naive_hybrid"
            )
            async for line in process_turn_sse(db, session, "hello"):
                lines.append(line)
        return lines

    lines = asyncio.run(_run())
    db.rollback.assert_awaited()
    assert any('"type": "error"' in ln for ln in lines)
    assert any('"type": "done"' in ln for ln in lines)
