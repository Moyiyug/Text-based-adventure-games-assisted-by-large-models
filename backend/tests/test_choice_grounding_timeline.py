"""选项 grounding 注入时间线块与启发式 note（mock DeepSeek）。"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import settings
from app.schemas.narrative_plan import NarrativePlan
from app.services.narrative.choice_grounding import ground_choices_for_turn


@pytest.fixture
def base_kwargs() -> dict:
    return {
        "narrative_excerpt": "你在森林里。",
        "state": {"current_location": "森林"},
        "evidence_context": "证据：森林中有小路。",
    }


def test_grounding_user_payload_contains_timeline_order(base_kwargs: dict) -> None:
    plan = NarrativePlan(
        opening_anchor_summary="序章营地",
        arc_goal="抵达王都",
        current_timeline_order=2,
        arc_end_order=10,
    )
    tac = (
        f"当前时间线次序：{plan.current_timeline_order}；弧线上界次序：{plan.arc_end_order}"
    )
    raw = '{"grounding_ok":true,"choices":["靠近","离开"]}'
    captured: list[str] = []

    async def _capture(*args: object, **kwargs: object) -> str:
        messages = args[0] if args else kwargs.get("messages")
        assert isinstance(messages, list) and len(messages) >= 2
        user = messages[1].get("content", "")
        captured.append(str(user))
        return raw

    async def _run() -> None:
        with patch(
            "app.services.narrative.choice_grounding.deepseek_chat",
            new_callable=AsyncMock,
            side_effect=_capture,
        ):
            await ground_choices_for_turn(
                mode="strict",
                choices=["靠近", "离开"],
                beats=None,
                max_attempts=1,
                timeline_arc_constraints="【选项质检·时间线与弧线】\n" + tac,
                timeline_orders_for_heuristic=(2, 10),
                **base_kwargs,
            )

    asyncio.run(_run())
    assert captured and "当前时间线次序：2" in captured[0]
    assert "timeline_arc_constraints" in captured[0]


def test_heuristic_note_mode_appends_on_second_attempt(base_kwargs: dict) -> None:
    first = '{"grounding_ok":false,"choices":["去看大结局","离开"]}'
    second = '{"grounding_ok":true,"choices":["观察","撤退"]}'

    async def _run() -> None:
        with patch.object(settings, "NARRATIVE_CHOICE_TIMELINE_HEURISTIC_MODE", "note"):
            with patch(
                "app.services.narrative.choice_grounding.deepseek_chat",
                new_callable=AsyncMock,
                side_effect=[first, second],
            ) as m:
                await ground_choices_for_turn(
                    mode="strict",
                    choices=["去看大结局", "离开"],
                    beats=None,
                    max_attempts=2,
                    timeline_orders_for_heuristic=(0, 5),
                    **base_kwargs,
                )
        assert m.await_count == 2
        second_call = m.await_args_list[1]
        user_content = second_call[0][0][1]["content"]
        assert "另：" in user_content or "终局跳跃" in user_content

    asyncio.run(_run())
