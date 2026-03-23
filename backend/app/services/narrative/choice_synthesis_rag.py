"""分步生成第二轮：与主叙事共用检索证据块，专产出 choices / choice_beats（NARRATIVE_SPLIT_CHOICES_LLM）。"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from app.services.llm.deepseek import deepseek_chat
from app.services.narrative.prompts import build_choices_only_prompt

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SplitChoicesResult:
    choices: list[str]
    choice_beats: list[str] | None


def _parse_json_object_from_raw(raw: str) -> dict[str, object] | None:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9]*\s*", "", text)
        if "```" in text:
            text = text[: text.index("```")].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        obj = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _coerce_split_result(data: dict[str, Any], *, mode: str) -> SplitChoicesResult | None:
    raw_ch = data.get("choices")
    if not isinstance(raw_ch, list) or len(raw_ch) < 2:
        return None
    choices = [str(x).strip() for x in raw_ch if str(x).strip()]
    if len(choices) < 2:
        return None
    if len(choices) > 4:
        choices = choices[:4]
    beats: list[str] | None = None
    raw_be = data.get("choice_beats")
    if isinstance(raw_be, list) and raw_be:
        b = [str(x).strip() for x in raw_be if str(x).strip()]
        if len(b) == len(choices):
            beats = b
        else:
            logger.warning(
                "choice_synthesis_rag choice_beats length mismatch mode=%s choices=%s beats=%s",
                mode,
                len(choices),
                len(b),
            )
    if mode == "strict" and beats is None:
        logger.info(
            "choice_synthesis_rag strict mode without valid choice_beats; continuing with choices only"
        )
    return SplitChoicesResult(choices=choices, choice_beats=beats)


async def synthesize_choices_with_rag_context(
    *,
    context: str,
    state: dict[str, object] | None,
    narrative: str,
    user_input: str,
    mode: str,
    style_config: dict[str, object] | None,
    templates: dict[str, str],
    temperature: float = 0.25,
    timeout: float = 90.0,
) -> SplitChoicesResult | None:
    """
    第二次 DeepSeek 调用：messages 与主生成同构检索 user 块 + 叙事/状态 tail。
    失败返回 None。
    """
    if mode not in ("strict", "creative"):
        return None
    if not narrative.strip():
        return None
    messages = build_choices_only_prompt(
        context=context,
        state=state,
        narrative=narrative,
        user_input=user_input,
        mode=mode,
        style_config=style_config,
        templates=templates,
    )
    try:
        raw = await deepseek_chat(messages, temperature=temperature, timeout=timeout)
    except Exception as e:  # noqa: BLE001
        logger.warning("choice_synthesis_rag deepseek_chat failed: %s", e)
        return None
    data = _parse_json_object_from_raw(raw)
    if data is None:
        logger.warning(
            "choice_synthesis_rag could not parse JSON object (response_len=%s)",
            len(raw.strip()),
        )
        return None
    out = _coerce_split_result(data, mode=mode)
    if out is None:
        logger.warning("choice_synthesis_rag invalid choices after coerce")
    return out
