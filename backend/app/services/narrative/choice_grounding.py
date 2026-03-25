"""选项事实对齐：检查 + 有限次改写，合并原 strict refine 语义（回合 SSE 路径）。

每轮最多 ``NARRATIVE_CHOICE_GROUNDING_MAX_ATTEMPTS`` 次 DeepSeek 调用；首调即 grounding_ok 则不再追加。
与主生成、双阶段、fallback 等叠加后的总调用数以配置为准（见 PRD / BACKEND_STRUCTURE §4.4）。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.services.llm.deepseek import deepseek_chat

logger = logging.getLogger(__name__)

_MAX_ITEM_LEN = 120
_STATE_JSON_MAX = 2000


@dataclass
class GroundingResult:
    choices: list[str]
    choice_beats: list[str] | None
    grounding_failed: bool
    attempts_used: int
    choices_changed_from_input: bool


_SYSTEM_STRICT = (
    "你是交互小说选项质检编辑。根据「检索证据摘要」「叙事节选」「会话状态」与当前候选选项，"
    "只输出**一行**合法 JSON 对象，不要 Markdown。键：\n"
    '- "grounding_ok": bool，选项是否均被证据支持、彼此区分、与叙事衔接且无编造关键事实；\n'
    '- "choices": 字符串数组，2～4 条，每条为简短中文可执行行动；'
    "**禁止**两条在全文去空白、NFKC 规范化后实质相同，或仅为同义换皮；\n"
    '- "choice_beats": 字符串数组，**仅当** user 中 current_choice_beats 非空时必填，且必须与 choices 等长，'
    "每项 1～2 句第三人称大纲；若 user 中 current_choice_beats 为空数组则不要输出 choice_beats 键。\n"
    "若仍不达标，仍输出你认为最优的 choices（2～4 条），并将 grounding_ok 置为 false。"
)

_SYSTEM_CREATIVE = (
    "你是创作模式文字冒险的选项编辑。以检索证据为锚，允许在自洽前提下更有趣；"
    "仅当选项与证据**明显矛盾**或彼此重复时将 grounding_ok 置为 false。"
    "choices 中不得含实质重复项（去空白、NFKC 后不得两条相同或仅措辞微差）。"
    "只输出**一行**合法 JSON：grounding_ok（bool）、choices（2～4 条中文短行动）。"
    "若 user 中 current_choice_beats 非空，须同时输出与 choices 等长的 choice_beats；否则不要输出 choice_beats。"
)


def _strip_code_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9]*\s*", "", t)
        if "```" in t:
            t = t[: t.index("```")].strip()
    return t


def _extract_json_object(text: str) -> dict[str, Any] | None:
    t = _strip_code_fence(text)
    start = t.find("{")
    end = t.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        obj = json.loads(t[start : end + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _normalize_choices(raw: list[Any]) -> list[str]:
    out: list[str] = []
    for x in raw:
        s = str(x).strip()
        if not s or len(s) > _MAX_ITEM_LEN:
            continue
        if s not in out:
            out.append(s)
        if len(out) >= 4:
            break
    return out


def _beats_for_strict(
    choices: list[str],
    raw_beats: Any,
    had_input_beats: bool,
) -> list[str] | None:
    if not had_input_beats:
        return None
    if not isinstance(raw_beats, list):
        return None
    beats = [str(x).strip() for x in raw_beats if str(x).strip()]
    if len(beats) != len(choices):
        return None
    return beats


def _beats_for_creative(
    choices: list[str],
    raw_beats: Any,
    had_input_beats: bool,
) -> list[str] | None:
    if not had_input_beats:
        return None
    if not isinstance(raw_beats, list):
        return None
    beats = [str(x).strip() for x in raw_beats if str(x).strip()]
    if len(beats) != len(choices):
        return None
    return beats


def _lists_equal(a: list[str] | None, b: list[str] | None) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return len(a) == len(b) and all(x == y for x, y in zip(a, b))


async def ground_choices_for_turn(
    *,
    mode: str,
    narrative_excerpt: str,
    state: dict[str, Any],
    evidence_context: str,
    choices: list[str],
    beats: list[str] | None,
    max_attempts: int | None = None,
) -> GroundingResult:
    """
    对候选 choices 做多轮 LLM 质检与改写。choices 少于 2 条时直接返回，不调用模型。
    """
    initial_choices = list(choices)
    initial_beats = list(beats) if beats else None

    if len(choices) < 2:
        return GroundingResult(
            choices=list(choices),
            choice_beats=beats,
            grounding_failed=False,
            attempts_used=0,
            choices_changed_from_input=False,
        )

    attempts_cap = max_attempts if max_attempts is not None else settings.NARRATIVE_CHOICE_GROUNDING_MAX_ATTEMPTS
    attempts_cap = max(1, min(attempts_cap, 8))

    ev_max = settings.NARRATIVE_CHOICE_GROUNDING_EVIDENCE_CHARS
    nar_max = settings.NARRATIVE_CHOICE_GROUNDING_NARRATIVE_CHARS
    ev = evidence_context.strip()
    if len(ev) > ev_max:
        ev = ev[-ev_max:]
    nar = narrative_excerpt.strip()
    if len(nar) > nar_max:
        nar = nar[-nar_max:]
    state_json = json.dumps(state or {}, ensure_ascii=False)[:_STATE_JSON_MAX]

    had_input_beats = bool(beats and len(beats) > 0)
    sys_prompt = _SYSTEM_STRICT if mode == "strict" else _SYSTEM_CREATIVE

    current_ch = _normalize_choices(choices)
    if len(current_ch) < 2:
        return GroundingResult(
            choices=current_ch,
            choice_beats=None if not had_input_beats else beats,
            grounding_failed=False,
            attempts_used=0,
            choices_changed_from_input=current_ch != initial_choices,
        )
    current_be: list[str] | None = list(beats) if had_input_beats else None

    attempts_used = 0
    grounding_ok = False

    for attempt_idx in range(attempts_cap):
        attempts_used += 1
        beats_in = current_be if had_input_beats else []
        payload: dict[str, Any] = {
            "evidence_excerpt": ev,
            "narrative_excerpt": nar,
            "state_json": state_json,
            "current_choices": current_ch,
            "current_choice_beats": beats_in,
            "attempt": attempt_idx + 1,
            "session_mode": mode,
        }
        if attempt_idx > 0:
            payload["note"] = "上一轮 grounding_ok 为 false，请修订 choices（及 beats 若适用）直至可置 true。"

        human = (
            "请根据下列 JSON 质检并必要时改写选项，只输出一行 JSON 对象：\n"
            + json.dumps(payload, ensure_ascii=False)
        )

        try:
            raw = await deepseek_chat(
                [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": human},
                ],
                temperature=0.2,
                timeout=90.0,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("choice_grounding deepseek_chat failed: %s", e)
            break

        obj = _extract_json_object(raw)
        if not obj:
            logger.warning("choice_grounding could not parse JSON (attempt %s)", attempt_idx + 1)
            continue

        ch_raw = obj.get("choices")
        if not isinstance(ch_raw, list):
            continue
        next_ch = _normalize_choices(ch_raw)
        if len(next_ch) < 2:
            continue

        if mode == "strict":
            next_be = _beats_for_strict(next_ch, obj.get("choice_beats"), had_input_beats)
        else:
            next_be = _beats_for_creative(next_ch, obj.get("choice_beats"), had_input_beats)

        current_ch = next_ch
        current_be = next_be

        gok = obj.get("grounding_ok")
        grounding_ok = bool(gok) if isinstance(gok, bool) else False

        if grounding_ok:
            changed = (current_ch != initial_choices) or not _lists_equal(current_be, initial_beats)
            return GroundingResult(
                choices=current_ch,
                choice_beats=current_be,
                grounding_failed=False,
                attempts_used=attempts_used,
                choices_changed_from_input=changed,
            )

    changed = (current_ch != initial_choices) or not _lists_equal(current_be, initial_beats)
    return GroundingResult(
        choices=current_ch,
        choice_beats=current_be,
        grounding_failed=True,
        attempts_used=attempts_used,
        choices_changed_from_input=changed,
    )
