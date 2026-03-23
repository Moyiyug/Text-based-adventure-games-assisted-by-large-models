"""将玩家原话整理为「叙事承接用」短句，不引入新设定；落库仍保留原文。"""

from __future__ import annotations

import logging

from app.services.llm.deepseek import deepseek_chat

logger = logging.getLogger(__name__)

_SYSTEM = (
    "你是文字冒险游戏的输入桥接器。把玩家的简短或模糊输入改写成 1～2 句中文，"
    "表述为「角色已经尝试去做的具体行动」及合理意图。"
    "禁止新增世界观事实、NPC、地点或道具；禁止与给定 state 矛盾。"
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
        logger.warning("input_bridge deepseek_chat failed: %s", e)
        return ""
    out = (raw or "").strip()
    if len(out) > 500:
        out = out[:500]
    return out
