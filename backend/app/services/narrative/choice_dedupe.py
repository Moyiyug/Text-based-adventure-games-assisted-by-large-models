"""选项规范化去重；与 grounding 之后衔接，保证至少两条可点选项（LLM 补全 + 末级占位）。"""

from __future__ import annotations

import logging
import re
import unicodedata

from app.services.narrative.choice_fallback import synthesize_choices_from_context

logger = logging.getLogger(__name__)

# 末级兜底：无叙事或 LLM 失败时仍满足 UI ≥2 契约（不向玩家展示「系统生成」前缀）
_PLACEHOLDER_CHOICES: tuple[str, str] = ("继续推进当前情节", "暂缓行动、观察周遭")


def normalize_choice_dedupe_key(s: str) -> str:
    t = unicodedata.normalize("NFKC", (s or "").strip())
    t = re.sub(r"\s+", " ", t)
    return t.casefold()


def dedupe_choices_with_beats(
    choices: list[str],
    beats: list[str] | None,
) -> tuple[list[str], list[str] | None]:
    """
    按 NFKC + 空白折叠后的 key 保序去重；保留每条首次出现的展示文案。
    beats 与 choices 等长时按保留下标收缩，否则丢弃 beats。
    """
    seen: set[str] = set()
    out_ch: list[str] = []
    kept_indices: list[int] = []
    for i, raw in enumerate(choices):
        disp = raw.strip()
        key = normalize_choice_dedupe_key(disp)
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        out_ch.append(disp)
        kept_indices.append(i)
    if beats is None:
        return out_ch, None
    if len(beats) != len(choices):
        return out_ch, None
    out_be = [beats[i] for i in kept_indices if i < len(beats)]
    if len(out_be) != len(out_ch):
        return out_ch, None
    return out_ch, out_be


async def ensure_at_least_two_choices(
    *,
    choices: list[str],
    beats: list[str] | None,
    narrative: str,
    user_input: str,
    assembled_context: str | None = None,
    templates: dict[str, str] | None = None,
) -> tuple[list[str], list[str] | None, str | None, bool]:
    """
    去重 → 不足 2 条则强制 synthesize（带检索节选）→ 仍不足则用占位。
    返回 (choices, beats, source_override, was_deduped)。
    source_override 仅在为 llm_fallback / placeholder_fallback 时非空，调用方据此写 metadata。
    """
    orig_n = len(choices)
    ch, be = dedupe_choices_with_beats(choices, beats)
    was_deduped = len(ch) != orig_n

    if len(ch) >= 2:
        return ch, be, None, was_deduped

    if not narrative.strip():
        logger.warning("ensure_at_least_two_choices: empty narrative, using placeholder pair")
        return list(_PLACEHOLDER_CHOICES), None, "placeholder_fallback", was_deduped

    syn = await synthesize_choices_from_context(
        user_input=user_input,
        narrative=narrative,
        assembled_context=assembled_context,
        templates=templates,
    )
    if len(syn) >= 2:
        return syn, None, "llm_fallback", was_deduped

    logger.warning("ensure_at_least_two_choices: synthesize returned <%s, using placeholder", len(syn))
    return list(_PLACEHOLDER_CHOICES), None, "placeholder_fallback", was_deduped
