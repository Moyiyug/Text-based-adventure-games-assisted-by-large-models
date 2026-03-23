"""将 RetrievalResult 压入 Token 预算内的上下文字符串。参照 IMPLEMENTATION_PLAN 3.5、4.8。"""

from __future__ import annotations

import json
from typing import Any

import tiktoken

from app.services.rag.base import RetrievalResult


def _approx_tokens(text: str, enc: Any | None) -> int:
    if enc is not None:
        return len(enc.encode(text))
    return max(1, len(text) // 2)


def _get_encoder():
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception:  # noqa: BLE001
        return None


def _profile_blocks(profile: dict[str, Any] | None) -> list[str]:
    """高优先级前置块：全局偏好 + 本作品覆写。"""
    if not profile:
        return []
    blocks: list[str] = []
    prefs = profile.get("user_preferences") or {}
    if prefs:
        blocks.append(
            f"[用户画像-全局]\n{json.dumps(prefs, ensure_ascii=False)}"
        )
    over = profile.get("story_overrides") or {}
    if over:
        blocks.append(
            f"[用户画像-本作品覆写]\n{json.dumps(over, ensure_ascii=False)}"
        )
    return blocks


def assemble_context(
    retrieved: RetrievalResult,
    *,
    mode: str = "strict",
    token_budget: int = 4000,
    session_state: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
) -> str:
    """
    按优先级拼接：用户画像（全局 + 作品覆写）→ 结构化事实 → 文本块。
    超出 token_budget 时从尾部整块移除（先丢检索块，画像块最后丢）。
    """
    _ = mode, session_state
    enc = _get_encoder()
    parts: list[str] = []

    parts.extend(_profile_blocks(profile))

    for sh in retrieved.structured:
        line = f"[{sh.kind}] {json.dumps(sh.payload, ensure_ascii=False)}"
        parts.append(line)

    for ch in retrieved.chunks:
        if ch.parent_context:
            block = f"【父级摘要】{ch.parent_context}\n【子块】{ch.content}"
        else:
            block = ch.content
        parts.append(block)

    if not parts:
        return ""

    def _joined() -> str:
        return "\n\n---\n\n".join(parts)

    full = _joined()
    if _approx_tokens(full, enc) <= token_budget:
        return full

    while parts and _approx_tokens(_joined(), enc) > token_budget:
        parts.pop()

    out = _joined()
    if _approx_tokens(out, enc) > token_budget and out:
        while out and _approx_tokens(out, enc) > token_budget:
            out = out[: max(0, len(out) - 200)]
        out = out.rstrip() + "\n…[上下文已截断]"
    return out
