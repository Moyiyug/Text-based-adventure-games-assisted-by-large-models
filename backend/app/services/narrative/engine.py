"""叙事生成：开场非流式 + 回合流式。参照 BACKEND_STRUCTURE §4.4。"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.session import Session as NarrativeSession
from app.models.session import SessionEvent, SessionMessage, SessionState
from app.services.llm.deepseek import deepseek_chat, deepseek_chat_stream
from app.services.narrative.meta_parse import MetaStreamSplitter, parse_complete_model_output
from app.services.narrative.safety import (
    handle_api_block,
    is_likely_content_policy_block,
    soften_content,
)
from app.services.narrative.prompts import (
    build_generation_prompt,
    load_prompt_templates,
)
from app.services.narrative.state import apply_state_update, validate_state_update
from app.services.profile_loader import (
    load_session_profile_bundle,
    profile_bundle_nonempty,
)
from app.services.rag.context import assemble_context
from app.services.rag.dispatcher import dispatch_retrieve

logger = logging.getLogger(__name__)

_HISTORY_LIMIT = 24
_TOKEN_BUDGET = 6000

OPENING_USER_PROMPT = (
    "请根据玩家的冒险目标，生成本会话的**开场**交互叙事，并给出首批选项。"
    "严格遵守系统提示中的输出格式（叙事后接 ---META--- 再单行 JSON）。"
)


@dataclass
class NarrativeResult:
    narrative: str
    choices: list[str]
    state_update: dict[str, Any]
    internal_notes: str
    parse_error: str | None


def _sse_line(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _latest_state_dict(db: AsyncSession, session_id: int) -> dict[str, Any]:
    res = await db.execute(
        select(SessionState)
        .where(SessionState.session_id == session_id)
        .order_by(SessionState.turn_number.desc(), SessionState.id.desc())
        .limit(1)
    )
    row = res.scalar_one_or_none()
    if row is None or row.state is None:
        return {}
    return dict(row.state)


async def _message_history(db: AsyncSession, session_id: int) -> list[dict[str, str]]:
    res = await db.execute(
        select(SessionMessage)
        .where(SessionMessage.session_id == session_id)
        .order_by(SessionMessage.id.desc())
        .limit(_HISTORY_LIMIT)
    )
    rows = list(reversed(list(res.scalars().all())))
    return [{"role": m.role, "content": m.content} for m in rows]


async def generate_opening(
    db: AsyncSession,
    session: NarrativeSession,
) -> NarrativeResult:
    """非流式生成开场，写入 assistant 消息、状态与事件。"""
    templates = await load_prompt_templates(db, session.mode)
    profile_bundle = await load_session_profile_bundle(
        db, session.user_id, session.story_id
    )
    profile_used = profile_bundle_nonempty(profile_bundle)
    retrieved = await dispatch_retrieve(
        db,
        session.opening_goal or "开场",
        session.story_version_id,
        session.rag_config_id,
    )
    context = assemble_context(
        retrieved,
        mode=session.mode,
        token_budget=_TOKEN_BUDGET,
        profile=profile_bundle,
    )
    state = await _latest_state_dict(db, session.id)
    messages = build_generation_prompt(
        OPENING_USER_PROMPT,
        context,
        state,
        None,
        mode=session.mode,
        style_config=dict(session.style_config or {}),
        templates=templates,
        history=[],
    )
    narrative_body: str
    choices_body: list[str]
    state_update_body: dict[str, Any]
    internal_notes_body: str
    parse_error_body: str | None

    try:
        raw = await deepseek_chat(messages, temperature=0.4)
    except Exception as e:
        if not is_likely_content_policy_block(e):
            raise
        fb = handle_api_block(session.id, session.opening_goal or "")
        logger.warning("opening content policy block: %s", fb.log_message)
        narrative_body = fb.narrative
        choices_body = list(fb.choices)
        state_update_body = {}
        internal_notes_body = ""
        parse_error_body = "api_content_policy"
    else:
        parsed = parse_complete_model_output(raw)
        narrative_body = parsed.narrative
        choices_body = parsed.choices
        state_update_body = parsed.state_update
        internal_notes_body = parsed.internal_notes
        parse_error_body = parsed.parse_error
        if internal_notes_body:
            logger.info("opening internal_notes: %s", internal_notes_body[:500])
        if (
            settings.NARRATIVE_SAFETY_SOFTEN
            and narrative_body.strip()
            and not parse_error_body
        ):
            try:
                narrative_body = await soften_content(narrative_body)
            except Exception as soften_exc:  # noqa: BLE001
                logger.warning(
                    "soften_content failed session_id=%s: %s", session.id, soften_exc
                )

    new_turn = max(1, session.turn_count + 1)

    su_in = state_update_body if not parse_error_body else {}
    validated = validate_state_update(state, su_in)
    await apply_state_update(db, session.id, new_turn, validated)

    db.add(
        SessionMessage(
            session_id=session.id,
            turn_number=new_turn,
            role="assistant",
            content=narrative_body,
            metadata_={
                "opening": True,
                "choices": choices_body,
                "parse_error": parse_error_body,
                "profile_context_used": profile_used,
            },
        )
    )
    db.add(
        SessionEvent(
            session_id=session.id,
            turn_number=new_turn,
            event_type="state_change",
            content={
                "choices": choices_body,
                "state_update": state_update_body,
                "parse_error": parse_error_body,
            },
        )
    )
    session.turn_count = new_turn
    session.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)

    return NarrativeResult(
        narrative=narrative_body,
        choices=choices_body,
        state_update=validated,
        internal_notes=internal_notes_body,
        parse_error=parse_error_body,
    )


async def process_turn_sse(
    db: AsyncSession,
    session: NarrativeSession,
    user_input: str,
) -> AsyncIterator[str]:
    """
    执行一轮对话：先写入用户消息，再流式生成 assistant，最后落库。
    产出 SSE 文本行（含 `data: {...}\\n\\n`）。
    """
    text = user_input.strip()
    if not text:
        yield _sse_line({"type": "error", "message": "内容不能为空"})
        yield _sse_line({"type": "done"})
        return

    state = await _latest_state_dict(db, session.id)
    history_for_prompt = await _message_history(db, session.id)

    current_turn = session.turn_count + 1
    db.add(
        SessionMessage(
            session_id=session.id,
            turn_number=current_turn,
            role="user",
            content=text,
            metadata_={},
        )
    )
    await db.flush()

    retrieved = None
    try:
        templates = await load_prompt_templates(db, session.mode)
        profile_bundle = await load_session_profile_bundle(
            db, session.user_id, session.story_id
        )
        profile_used = profile_bundle_nonempty(profile_bundle)
        retrieved = await dispatch_retrieve(
            db,
            text,
            session.story_version_id,
            session.rag_config_id,
        )
        context = assemble_context(
            retrieved,
            mode=session.mode,
            token_budget=_TOKEN_BUDGET,
            profile=profile_bundle,
        )
        messages = build_generation_prompt(
            text,
            context,
            state,
            None,
            mode=session.mode,
            style_config=dict(session.style_config or {}),
            templates=templates,
            history=history_for_prompt,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("process_turn 准备阶段失败 session_id=%s", session.id)
        yield _sse_line({"type": "error", "message": str(e)[:800]})
        yield _sse_line({"type": "done"})
        await db.rollback()
        return

    splitter = MetaStreamSplitter()
    try:
        async for delta in deepseek_chat_stream(messages, temperature=0.35):
            for piece in splitter.feed(delta):
                if piece:
                    yield _sse_line({"type": "token", "content": piece})
    except Exception as e:  # noqa: BLE001
        # 流式回合遇内容策略拦截：rollback（含本轮 user 消息），不落库 fallback，与 IMPLEMENTATION_PLAN 4.6 一致。
        if is_likely_content_policy_block(e):
            fb = handle_api_block(session.id, text)
            logger.warning("turn stream content policy block: %s", fb.log_message)
            yield _sse_line(
                {
                    "type": "error",
                    "message": fb.narrative[:800],
                }
            )
        else:
            logger.exception("DeepSeek 流式失败 session_id=%s", session.id)
            yield _sse_line({"type": "error", "message": str(e)[:800]})
        yield _sse_line({"type": "done"})
        await db.rollback()
        return

    parsed = splitter.finalize()
    if parsed.internal_notes:
        logger.info("turn internal_notes: %s", parsed.internal_notes[:500])

    choices = parsed.choices if not parsed.parse_error else []
    su = parsed.state_update if not parsed.parse_error else {}
    validated = validate_state_update(state, su)

    try:
        await apply_state_update(db, session.id, current_turn, validated)
        db.add(
            SessionMessage(
                session_id=session.id,
                turn_number=current_turn,
                role="assistant",
                content=parsed.narrative,
                metadata_={
                    "choices": choices,
                    "parse_error": parsed.parse_error,
                    "rag_variant": retrieved.variant_type if retrieved else None,
                    "profile_context_used": profile_used,
                },
            )
        )
        db.add(
            SessionEvent(
                session_id=session.id,
                turn_number=current_turn,
                event_type="state_change",
                content={"choices": choices, "state_update": su, "parse_error": parsed.parse_error},
            )
        )
        session.turn_count = current_turn
        session.updated_at = datetime.now(timezone.utc)
        await db.commit()
    except Exception as e:  # noqa: BLE001
        logger.exception("process_turn 落库失败 session_id=%s", session.id)
        yield _sse_line({"type": "error", "message": f"落库失败: {e}"[:800]})
        await db.rollback()
        yield _sse_line({"type": "done"})
        return

    yield _sse_line({"type": "choices", "choices": choices})
    yield _sse_line({"type": "state_update", "state": validated})
    if parsed.parse_error:
        yield _sse_line({"type": "error", "message": parsed.parse_error})
    yield _sse_line({"type": "done"})
