"""严谨模式下对 choices / choice_beats 做一次精炼（可选，主流结束后调用）。"""

from __future__ import annotations

import json
import logging
import re

from app.services.llm.deepseek import deepseek_chat

logger = logging.getLogger(__name__)

_SYSTEM = (
    "你是严谨向文字冒险的选项编辑。给定叙事节选、状态与候选选项，"
    "输出**单行 JSON 对象**，键为 choices（字符串数组）与 choice_beats（字符串数组），"
    "二者必须等长、2～4 项；choice_beats 每项为 1～2 句第三人称大纲，对应若玩家选该项时下一段核心转折。"
    "选项须具体可执行、彼此区分，并与证据摘要一致；禁止两条仅措辞不同或去空白后实质相同；禁止 Markdown。"
    "若 user JSON 含 timeline_arc_constraints，精炼时须一并服从其中时间线与弧线上界。"
)


def _parse_refine_obj(raw: str) -> dict[str, list[str]] | None:
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
    if not isinstance(obj, dict):
        return None
    ch = obj.get("choices")
    be = obj.get("choice_beats")
    if not isinstance(ch, list) or not isinstance(be, list):
        return None
    choices = [str(x).strip() for x in ch if str(x).strip()]
    beats = [str(x).strip() for x in be if str(x).strip()]
    if len(choices) < 2 or len(choices) != len(beats):
        return None
    if len(choices) > 4:
        choices, beats = choices[:4], beats[:4]
    return {"choices": choices, "choice_beats": beats}


async def refine_strict_choices(
    *,
    narrative_excerpt: str,
    state_json: str,
    evidence_excerpt: str,
    current_choices: list[str],
    current_beats: list[str] | None,
    timeline_arc_constraints: str | None = None,
    temperature: float = 0.2,
    timeout: float = 90.0,
) -> dict[str, list[str]] | None:
    beats_in = current_beats or []
    payload: dict[str, object] = {
        "narrative_excerpt": narrative_excerpt[-3500:],
        "state_json": state_json[:2000],
        "evidence_excerpt": evidence_excerpt[-2500:],
        "current_choices": current_choices,
        "current_choice_beats": beats_in,
    }
    tac = (timeline_arc_constraints or "").strip()
    if tac:
        payload["timeline_arc_constraints"] = tac
    human = (
        "请精炼下列 JSON 中的选项与大纲（可改写以更符合证据与推进），只输出一行 JSON 对象：\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    try:
        raw = await deepseek_chat(
            [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": human},
            ],
            temperature=temperature,
            timeout=timeout,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("choice_refine deepseek_chat failed: %s", e)
        return None
    return _parse_refine_obj(raw)
