"""叙事内容安全：输出软化、API 风控拦截时的降级文案。参照 BACKEND_STRUCTURE §4.4.3、IMPLEMENTATION_PLAN 4.6。"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from openai import APIStatusError

from app.services.llm.deepseek import deepseek_chat

logger = logging.getLogger(__name__)

_SOFTEN_SYSTEM = (
    "你是文字冒险游戏的叙事编辑。请将下列叙事段落中可能过于露骨、血腥或不适宜的表述，"
    "改写为含蓄、文艺、仍保持氛围与情节信息的版本。"
    "不要添加评论或前言，只输出改写后的正文；不要引入 ---META--- 或 JSON。"
)


@dataclass(frozen=True)
class FallbackNarrative:
    """DeepSeek 等内容策略拦截时给玩家的可继续游玩文案。"""

    narrative: str
    choices: list[str]
    log_message: str


def _exc_text_lower(exc: BaseException) -> str:
    parts: list[str] = [str(exc).lower()]
    if isinstance(exc, APIStatusError):
        msg = getattr(exc, "message", None)
        if msg:
            parts.append(str(msg).lower())
        body = getattr(exc, "body", None)
        if body is not None:
            parts.append(str(body).lower())
    return " ".join(parts)


def is_likely_content_policy_block(exc: BaseException) -> bool:
    """
    判断是否疑似内容安全/审核拦截。宁缺毋滥：不确定则返回 False，走通用错误路径。
    """
    if isinstance(exc, APIStatusError):
        code = getattr(exc, "status_code", None) or 0
        blob = _exc_text_lower(exc)
        if code in (400, 403):
            keys = (
                "content",
                "policy",
                "moderation",
                "safety",
                "blocked",
                "filter",
                "违规",
                "审核",
            )
            if any(k in blob for k in keys):
                return True
    blob = _exc_text_lower(exc)
    keys = (
        "content policy",
        "content_policy",
        "moderation",
        "safety",
        "blocked",
        "inappropriate",
        "违规",
        "审核",
        "敏感",
    )
    return any(k in blob for k in keys)


def handle_api_block(session_id: int, user_input: str) -> FallbackNarrative:
    """生成运营日志用信息与玩家可见的降级叙事 + 选项。"""
    log_message = (
        f"content_policy_fallback session_id={session_id} user_input_chars={len(user_input)}"
    )
    narrative = (
        "这一段叙事因内容安全策略未能自动生成。你可以换一种说法描述行动，或从下面选项继续。"
    )
    choices = ["换个方式描述刚才的行动", "先观察周围环境"]
    return FallbackNarrative(
        narrative=narrative,
        choices=choices,
        log_message=log_message,
    )


async def soften_content(text: str) -> str:
    """
    对叙事正文做文艺化软化（非流式额外调用）。
    仅作用于纯叙事文本，不包含 ---META--- 段。
    """
    t = (text or "").strip()
    if not t:
        return text or ""
    messages = [
        {"role": "system", "content": _SOFTEN_SYSTEM},
        {"role": "user", "content": t},
    ]
    out = await deepseek_chat(messages, temperature=0.35)
    return (out or "").strip() or t
