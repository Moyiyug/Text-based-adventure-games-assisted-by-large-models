"""choice_grounding：多轮质检与改写（mock DeepSeek）。"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.services.narrative.choice_grounding import ground_choices_for_turn


@pytest.fixture
def base_kwargs() -> dict:
    return {
        "narrative_excerpt": "你在森林里。",
        "state": {"current_location": "森林"},
        "evidence_context": "证据：森林中有小路。",
    }


def test_skip_when_fewer_than_two_choices(base_kwargs: dict) -> None:
    async def _run() -> None:
        mock = AsyncMock(return_value='{"grounding_ok":true,"choices":["仅一条"]}')
        with patch(
            "app.services.narrative.choice_grounding.deepseek_chat",
            new_callable=AsyncMock,
            return_value=mock.return_value,
        ) as m:
            r = await ground_choices_for_turn(
                mode="strict",
                choices=["一条"],
                beats=None,
                max_attempts=2,
                **base_kwargs,
            )
        assert r.choices == ["一条"]
        assert r.attempts_used == 0
        assert not r.grounding_failed
        m.assert_not_called()

    asyncio.run(_run())


def test_first_attempt_passes(base_kwargs: dict) -> None:
    raw = '{"grounding_ok":true,"choices":["靠近","离开"]}'

    async def _run() -> None:
        with patch(
            "app.services.narrative.choice_grounding.deepseek_chat",
            new_callable=AsyncMock,
            return_value=raw,
        ) as m:
            r = await ground_choices_for_turn(
                mode="strict",
                choices=["靠近", "离开"],
                beats=None,
                max_attempts=2,
                **base_kwargs,
            )
        assert m.await_count == 1
        assert r.choices == ["靠近", "离开"]
        assert not r.grounding_failed
        assert r.attempts_used == 1

    asyncio.run(_run())


def test_second_attempt_succeeds(base_kwargs: dict) -> None:
    first = '{"grounding_ok":false,"choices":["胡编甲","胡编乙"]}'
    second = '{"grounding_ok":true,"choices":["观察","撤退"]}'

    async def _run() -> None:
        with patch(
            "app.services.narrative.choice_grounding.deepseek_chat",
            new_callable=AsyncMock,
            side_effect=[first, second],
        ) as m:
            r = await ground_choices_for_turn(
                mode="strict",
                choices=["初A", "初B"],
                beats=None,
                max_attempts=2,
                **base_kwargs,
            )
        assert m.await_count == 2
        assert r.choices == ["观察", "撤退"]
        assert not r.grounding_failed
        assert r.attempts_used == 2
        assert r.choices_changed_from_input

    asyncio.run(_run())


def test_both_attempts_fail_keeps_last(base_kwargs: dict) -> None:
    first = '{"grounding_ok":false,"choices":["末次一","末次二"]}'
    second = '{"grounding_ok":false,"choices":["仍不行一","仍不行二"]}'

    async def _run() -> None:
        with patch(
            "app.services.narrative.choice_grounding.deepseek_chat",
            new_callable=AsyncMock,
            side_effect=[first, second],
        ) as m:
            r = await ground_choices_for_turn(
                mode="creative",
                choices=["x", "y"],
                beats=None,
                max_attempts=2,
                **base_kwargs,
            )
        assert m.await_count == 2
        assert r.grounding_failed
        assert r.choices == ["仍不行一", "仍不行二"]
        assert r.attempts_used == 2

    asyncio.run(_run())


def test_strict_with_beats_equal_length(base_kwargs: dict) -> None:
    raw = (
        '{"grounding_ok":true,"choices":["A","B"],'
        '"choice_beats":["b1","b2"]}'
    )

    async def _run() -> None:
        with patch(
            "app.services.narrative.choice_grounding.deepseek_chat",
            new_callable=AsyncMock,
            return_value=raw,
        ):
            r = await ground_choices_for_turn(
                mode="strict",
                choices=["A", "B"],
                beats=["old1", "old2"],
                max_attempts=2,
                **base_kwargs,
            )
        assert r.choice_beats == ["b1", "b2"]

    asyncio.run(_run())


def test_strict_beats_mismatch_clears_beats(base_kwargs: dict) -> None:
    raw = '{"grounding_ok":true,"choices":["A","B"],"choice_beats":["only_one"]}'

    async def _run() -> None:
        with patch(
            "app.services.narrative.choice_grounding.deepseek_chat",
            new_callable=AsyncMock,
            return_value=raw,
        ):
            r = await ground_choices_for_turn(
                mode="strict",
                choices=["A", "B"],
                beats=["x", "y"],
                max_attempts=2,
                **base_kwargs,
            )
        assert r.choice_beats is None

    asyncio.run(_run())
