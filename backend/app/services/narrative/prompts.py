"""提示词拼装。模板正文由 DB seed / 管理端维护，此处只做占位符替换与 messages 组装。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prompt_template import PromptTemplate
from app.services.profile_loader import profile_bundle_nonempty


async def load_prompt_templates(db: AsyncSession, mode: str) -> dict[str, str]:
    """
    按 layer 取当前 mode 或 applicable_mode=all 的激活模板（每 layer 取 id 最大的一条）。
    返回键：system, retrieval, gm, style
    """
    if mode not in ("strict", "creative"):
        raise ValueError("mode 须为 strict 或 creative")

    res = await db.execute(
        select(PromptTemplate).where(
            PromptTemplate.is_active.is_(True),
            (
                (PromptTemplate.applicable_mode == mode)
                | (PromptTemplate.applicable_mode == "all")
            ),
        )
    )
    rows = list(res.scalars().all())
    by_layer: dict[str, PromptTemplate] = {}
    for pt in rows:
        if pt.layer not in ("system", "retrieval", "gm", "style"):
            continue
        cur = by_layer.get(pt.layer)
        if cur is None or pt.id > cur.id:
            by_layer[pt.layer] = pt
    out: dict[str, str] = {}
    for layer in ("system", "retrieval", "gm", "style"):
        p = by_layer.get(layer)
        if p is not None:
            out[layer] = p.template_text
    return out


def build_system_prompt(
    mode: str,
    style_config: dict[str, Any] | None,
    templates: dict[str, str],
) -> str:
    """合并 system + gm + style 层（不含 retrieval）。"""
    style_json = json.dumps(style_config or {}, ensure_ascii=False)
    parts: list[str] = []
    for key in ("system", "gm", "style"):
        raw = templates.get(key)
        if not raw:
            continue
        if "{style_config}" in raw:
            parts.append(raw.replace("{style_config}", style_json))
        else:
            parts.append(raw)
    return "\n\n".join(parts).strip() or "你是叙事助手。"


def build_retrieval_prompt(context: str, templates: dict[str, str]) -> str:
    """检索证据包装。"""
    raw = templates.get("retrieval") or "【检索证据】\n{context}"
    return raw.replace("{context}", context.strip() or "（无）").strip()


def build_generation_prompt(
    user_input: str,
    context: str,
    state: dict[str, Any] | None,
    profile: dict[str, Any] | None,
    *,
    mode: str,
    style_config: dict[str, Any] | None,
    templates: dict[str, str],
    history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """
    返回 OpenAI 风格 messages：system（含 system+gm+style）→ user（检索块）→ 可选 history → user（状态+画像+本轮输入）。
    """
    system_text = build_system_prompt(mode, style_config, templates)
    retrieval_text = build_retrieval_prompt(context, templates)

    state_json = json.dumps(state or {}, ensure_ascii=False)
    profile_json = json.dumps(profile or {}, ensure_ascii=False)

    messages: list[dict[str, str]] = [{"role": "system", "content": system_text}]
    messages.append(
        {
            "role": "user",
            "content": f"[检索与设定证据]\n{retrieval_text}",
        }
    )
    if history:
        for h in history:
            r = h.get("role", "user")
            c = h.get("content", "")
            if r in ("user", "assistant") and c:
                messages.append({"role": r, "content": c})
    # 画像默认经 assemble_context 注入检索块；仅当显式传入非空 profile 时保留 tail 段（兼容旧调用）
    tail_chunks = [f"[当前会话状态 JSON]\n{state_json}"]
    if profile_bundle_nonempty(profile):
        tail_chunks.append(f"[用户画像/作品覆写 JSON]\n{profile_json}")
    tail_chunks.append(f"[玩家本轮输入]\n{user_input.strip()}")
    tail = "\n\n".join(tail_chunks)
    messages.append({"role": "user", "content": tail})
    return messages
