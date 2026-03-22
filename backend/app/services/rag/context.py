"""将 RetrievalResult 压入 Token 预算内的上下文字符串。参照 IMPLEMENTATION_PLAN 3.5。"""

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


def assemble_context(
    retrieved: RetrievalResult,
    *,
    mode: str = "strict",
    token_budget: int = 4000,
    session_state: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
) -> str:
    """
    按优先级拼接：结构化事实 → 文本块（含 parent_child 的父级说明）。
    超出 token_budget 时从尾部截断（先丢文本块尾部，再丢结构化尾部）。
    """
    _ = mode, session_state, profile  # Phase 4 使用
    enc = _get_encoder()
    parts: list[str] = []

    for sh in retrieved.structured:
        line = f"[{sh.kind}] {json.dumps(sh.payload, ensure_ascii=False)}"
        parts.append(line)

    for ch in retrieved.chunks:
        if ch.parent_context:
            block = f"【父级摘要】{ch.parent_context}\n【子块】{ch.content}"
        else:
            block = ch.content
        parts.append(block)

    full = "\n\n---\n\n".join(parts) if parts else ""
    if not full.strip():
        return ""

    if _approx_tokens(full, enc) <= token_budget:
        return full

    # 从后往前去掉整块直至满足预算
    while parts and _approx_tokens("\n\n---\n\n".join(parts), enc) > token_budget:
        parts.pop()

    out = "\n\n---\n\n".join(parts)
    if _approx_tokens(out, enc) > token_budget and out:
        # 最后一块硬截断
        while out and _approx_tokens(out, enc) > token_budget:
            out = out[: max(0, len(out) - 200)]
        out = out.rstrip() + "\n…[上下文已截断]"
    return out
