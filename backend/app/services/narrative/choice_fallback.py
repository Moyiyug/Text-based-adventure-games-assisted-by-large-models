"""当 META / 正文编号均未产出选项时，用 DeepSeek 二次生成 2～4 条行动（RULES §5.2 补充，非主协议）。"""

from __future__ import annotations

import json
import logging
import re

from app.core.config import settings
from app.services.llm.deepseek import deepseek_chat
from app.services.narrative.prompts import build_retrieval_prompt

logger = logging.getLogger(__name__)

_RETRIEVAL_FALLBACK_MAX_CHARS = 4000

_SYSTEM_PROMPT = (
    "你是交互小说选项生成器。根据叙事与玩家输入，只输出一行合法 JSON 数组，"
    "含 2～4 个字符串，每个为简短中文玩家行动（无 Markdown、无编号、无解释）。"
)


def _truncate_narrative(narrative: str, max_chars: int) -> str:
    t = narrative.strip()
    if len(t) <= max_chars:
        return t
    return t[-max_chars:]


def _parse_json_array_line(raw: str) -> list[object] | None:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9]*\s*", "", text)
        fence = text.rfind("```")
        if fence >= 0:
            text = text[:fence].strip()
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end <= start:
        return None
    try:
        val = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return val if isinstance(val, list) else None


def _format_retrieval_for_fallback(
    assembled_context: str | None,
    templates: dict[str, str] | None,
) -> str | None:
    """将 assemble_context 产物包装为与主生成一致的检索段（节选）。"""
    if not assembled_context or not assembled_context.strip():
        return None
    t = assembled_context.strip()
    if len(t) > _RETRIEVAL_FALLBACK_MAX_CHARS:
        t = t[-_RETRIEVAL_FALLBACK_MAX_CHARS:]
    if templates:
        return build_retrieval_prompt(t, templates)
    return f"【检索与设定证据】\n{t}"


async def synthesize_choices_from_context(
    *,
    user_input: str,
    narrative: str,
    max_choices: int = 4,
    max_item_len: int = 120,
    assembled_context: str | None = None,
    templates: dict[str, str] | None = None,
) -> list[str]:
    """
    基于叙事节选 + 玩家输入生成选项；失败返回 []。
    可选传入 assembled_context + templates，在 user 消息前附加与主流程同构的检索证据节选，降低幻觉。
    """
    if not narrative.strip():
        return []
    max_chars = max(500, settings.NARRATIVE_CHOICES_LLM_MAX_INPUT_CHARS)
    nar_excerpt = _truncate_narrative(narrative, max_chars)
    user_line = user_input.strip() or "（无）"
    tail = (
        f"【玩家输入】\n{user_line}\n\n【叙事节选】\n{nar_excerpt}\n\n"
        "只输出 JSON 数组，例如：[\"靠近观察\",\"转身离开\"]"
    )
    retrieval = _format_retrieval_for_fallback(assembled_context, templates)
    human = f"{retrieval}\n\n{tail}" if retrieval else tail
    try:
        raw = await deepseek_chat(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": human},
            ],
            temperature=0.25,
            timeout=90.0,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("choice_fallback deepseek_chat failed: %s", e)
        return []

    arr = _parse_json_array_line(raw)
    if arr is None:
        logger.warning(
            "choice_fallback could not parse JSON array (response_len=%s)",
            len(raw.strip()),
        )
        return []

    out: list[str] = []
    for x in arr:
        s = str(x).strip()
        if not s or len(s) > max_item_len:
            continue
        if s not in out:
            out.append(s)
        if len(out) >= max_choices:
            break
    if len(out) < 2:
        logger.warning("choice_fallback fewer than 2 valid strings after coerce")
        return []
    return out
