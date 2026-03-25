"""将玩家原话整理为「叙事承接用」短句，不引入新设定；落库仍保留原文。"""

from __future__ import annotations

import logging

from app.services.llm.deepseek import deepseek_chat

logger = logging.getLogger(__name__)

_SYSTEM_STRICT = (
    "你是文字冒险游戏的输入桥接器（严谨模式）。把玩家输入压缩改写成 1～2 句中文，供 GM 叙事承接用。\n"
    "优先表述为「角色试图/声称/打算…」等可裁定行动，**禁止**把明显违背 state 或与常识冲突的陈述改写成**已发生的事实**。\n"
    "禁止新增世界观事实、NPC、地点或道具；禁止与给定 state 矛盾。\n"
    "只输出改写后的句子，不要引号或解释。"
)

_SYSTEM_CREATIVE = (
    "你是文字冒险游戏的输入桥接器（创作模式）。把玩家的简短或模糊输入改写成 1～2 句中文，"
    "表述为可承接的具体行动或意图；可在不新增硬设定的前提下做温和、有趣的语义桥接。\n"
    "禁止新增世界观事实、NPC、地点或道具；禁止与给定 state 矛盾。\n"
    "只输出改写后的句子，不要引号或解释。"
)


async def rationalize_player_turn(
    *,
    user_text: str,
    state_summary: str,
    mode: str,
    temperature: float = 0.2,
    timeout: float = 45.0,
) -> str:
    if not user_text.strip():
        return ""
    human = (
        f"模式：{mode}\n"
        f"[当前状态摘要]\n{state_summary}\n\n"
        f"[玩家原话]\n{user_text.strip()}"
    )
    sys_prompt = _SYSTEM_STRICT if mode == "strict" else _SYSTEM_CREATIVE
    try:
        raw = await deepseek_chat(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": human},
            ],
            temperature=temperature,
            timeout=timeout,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("input_bridge deepseek_chat failed: %s", e)
        return ""
    out = (raw or "").strip()
    if len(out) > 500:
        out = out[:500]
    return out
