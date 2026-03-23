"""choice_fallback：JSON 行解析与 DeepSeek 二次抽取（mock）。"""

import asyncio
from unittest.mock import AsyncMock, patch

from app.services.narrative.choice_fallback import (
    _parse_json_array_line,
    synthesize_choices_from_context,
)


def test_parse_json_array_line_plain() -> None:
    assert _parse_json_array_line('["a","b"]') == ["a", "b"]


def test_parse_json_array_line_fence() -> None:
    raw = '```json\n["x","y"]\n```'
    assert _parse_json_array_line(raw) == ["x", "y"]


def test_parse_json_array_line_invalid() -> None:
    assert _parse_json_array_line("not json") is None


def test_synthesize_choices_three_items() -> None:
    async def _run() -> list[str]:
        with patch(
            "app.services.narrative.choice_fallback.deepseek_chat",
            new_callable=AsyncMock,
            return_value='["行动一","行动二","行动三"]',
        ):
            return await synthesize_choices_from_context(
                user_input="看什么",
                narrative="你在走廊里。" * 20,
            )

    assert asyncio.run(_run()) == ["行动一", "行动二", "行动三"]


def test_synthesize_choices_two_items() -> None:
    async def _run() -> list[str]:
        with patch(
            "app.services.narrative.choice_fallback.deepseek_chat",
            new_callable=AsyncMock,
            return_value='["甲","乙"]',
        ):
            return await synthesize_choices_from_context(
                user_input="继续",
                narrative="叙事节选足够长用于测试截断逻辑。",
            )

    assert asyncio.run(_run()) == ["甲", "乙"]


def test_synthesize_invalid_response_empty() -> None:
    async def _run() -> list[str]:
        with patch(
            "app.services.narrative.choice_fallback.deepseek_chat",
            new_callable=AsyncMock,
            return_value="not json",
        ):
            return await synthesize_choices_from_context(
                user_input="x",
                narrative="y",
            )

    assert asyncio.run(_run()) == []


def test_synthesize_empty_narrative() -> None:
    async def _run() -> list[str]:
        return await synthesize_choices_from_context(user_input="x", narrative="  \n")

    assert asyncio.run(_run()) == []
