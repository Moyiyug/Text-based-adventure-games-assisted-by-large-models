"""回合级提示拼装：摘要、choice_beats 匹配、滞回检测（仅服务端，不展示给玩家）。"""

from __future__ import annotations

import re
from typing import Any

from app.core.config import settings


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[\w\u4e00-\u9fff]+", s) if len(w) > 1}


def word_jaccard_similarity(a: str, b: str) -> float:
    """词级 Jaccard，用于检测相邻 GM 段是否过度相似。"""
    wa, wb = _words(a), _words(b)
    if not wa and not wb:
        return 1.0
    if not wa or not wb:
        return 0.0
    inter = len(wa & wb)
    union = len(wa | wb)
    return inter / union if union else 0.0


def gm_tail_excerpt(content: str, max_chars: int = 320) -> str:
    t = (content or "").strip()
    if len(t) <= max_chars:
        return t
    return "…" + t[-max_chars:]


def match_choice_beat_index(
    user_text: str, choices: list[str] | None
) -> int | None:
    """若玩家输入与某条选项一致或互为子串，返回下标。"""
    if not choices:
        return None
    u = user_text.strip()
    if not u:
        return None
    for i, c in enumerate(choices):
        ct = c.strip()
        if not ct:
            continue
        if u == ct or u in ct or ct in u:
            return i
    return None


def build_turn_hints_text(
    *,
    mode: str,
    state: dict[str, Any] | None,
    prev_gm_content: str | None,
    prev_meta: dict[str, Any] | None,
    user_text: str,
    prev_prev_gm_content: str | None = None,
) -> str | None:
    """
    拼装注入到 build_generation_prompt 的 turn_hints。
    若未启用或无内容则返回 None。
    """
    if not settings.NARRATIVE_TURN_HINTS_ENABLED:
        return None
    chunks: list[str] = []

    goal = (state or {}).get("active_goal") or "（未设定）"
    loc = (state or {}).get("current_location") or "（未设定）"
    chunks.append(
        f"[回合推进提示]\n"
        f"当前地点（state）：{loc}\n"
        f"当前目标（state）：{goal}\n"
        "玩家本轮输入（含点选选项原文）视为其在世界中已做出的行动尝试；"
        "叙事必须写出后果、反馈或阻力，禁止只重复场景描写而不回应输入。\n"
        "承接上轮时可用 1～2 句过渡，随后必须引入至少一项新信息：事件、对话、物品、关系或目标进展；"
        "禁止大段同义复述上一轮 GM 正文。\n"
        "自由输入与选项同等对待；若玩家表述模糊，请在叙事开头用一两句合理理解其意图并付诸行动，再写结果。"
    )

    if prev_gm_content and prev_gm_content.strip():
        chunks.append(
            f"[上一段 GM 节选（仅供衔接，勿照抄）]\n{gm_tail_excerpt(prev_gm_content)}"
        )

    if prev_meta and isinstance(prev_meta, dict):
        beats = prev_meta.get("choice_beats")
        chs = prev_meta.get("choices")
        if (
            isinstance(beats, list)
            and isinstance(chs, list)
            and beats
            and chs
            and len(beats) == len(chs)
        ):
            choices_str = [str(x) for x in chs]
            beats_str = [str(x) for x in beats]
            idx = match_choice_beat_index(user_text, choices_str)
            if idx is not None and 0 <= idx < len(beats_str):
                chunks.append(
                    f"[选中项隐含推进大纲（仅 GM 内部用，勿逐字复述给玩家当剧透）]\n{beats_str[idx].strip()}"
                )

    if (
        prev_gm_content
        and prev_prev_gm_content
        and settings.NARRATIVE_STALL_BREAK_ENABLED
    ):
        sim = word_jaccard_similarity(prev_prev_gm_content, prev_gm_content)
        th = settings.NARRATIVE_STALL_SIMILARITY_THRESHOLD
        if sim >= th:
            chunks.append(
                "[僵局打破]\n"
                "检测到相邻回合叙事可能过度相似；本轮必须引入新冲突、新信息或 NPC 主动行动之一，推动局面变化。"
            )

    if mode == "strict":
        chunks.append(
            "[严谨模式]\n"
            "选项须具体可执行，与检索证据及 state 一致；避免多数选项同为泛泛「继续观察」。"
            "证据不足时用谨慎措辞，勿编造关键设定。META JSON 中建议填写与 choices 等长的 choice_beats 数组，"
            "每项 1～2 句第三人称大纲，描述若玩家选该项时下一段的核心转折（非成品正文）。"
        )

    if not chunks:
        return None
    return "\n\n".join(chunks)
