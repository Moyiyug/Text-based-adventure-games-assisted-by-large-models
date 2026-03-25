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
from app.services.narrative.choice_dedupe import ensure_at_least_two_choices
from app.services.narrative.choice_fallback import synthesize_choices_from_context
from app.services.narrative.choice_grounding import ground_choices_for_turn
from app.services.narrative.choice_refine import refine_strict_choices
from app.services.narrative.meta_parse import (
    MetaStreamSplitter,
    ParsedTurnOutput,
    extract_choice_lines_from_narrative,
    parse_complete_model_output,
    strip_leaking_meta_suffix,
)
from app.services.narrative.safety import (
    handle_api_block,
    is_likely_content_policy_block,
    soften_content,
)
from app.services.narrative.prompts import (
    build_generation_prompt,
    build_two_phase_meta_prompt,
    load_prompt_templates,
)
from app.services.narrative.turn_context import build_turn_hints_text
from app.services.narrative.state import apply_state_update, validate_state_update
from app.services.profile import schedule_profile_inference_after_turn
from app.services.profile_loader import (
    load_session_profile_bundle,
    profile_bundle_nonempty,
)
from app.services.rag.context import assemble_context
from app.services.rag.dispatcher import dispatch_retrieve

logger = logging.getLogger(__name__)

_HISTORY_LIMIT = 24
_META_LOG_TAIL = 400


def _log_meta_parse_issue(
    *,
    phase: str,
    session_id: int,
    turn_number: int,
    choices: list[str],
    parse_error: str | None,
    raw_tail_source: str,
) -> None:
    if choices and not parse_error:
        return
    tail = raw_tail_source[-_META_LOG_TAIL:] if len(raw_tail_source) > _META_LOG_TAIL else raw_tail_source
    logger.warning(
        "narrative_meta_parse_issue phase=%s session_id=%s turn=%s choices_len=%s parse_error=%r raw_tail=%r",
        phase,
        session_id,
        turn_number,
        len(choices),
        parse_error,
        tail,
    )
_TOKEN_BUDGET = 6000

OPENING_USER_PROMPT = (
    "请根据玩家的冒险目标，生成本会话的**开场**交互叙事，并给出首批选项。"
    "严格遵守系统提示中的输出格式（叙事后接 ---META--- 再单行 JSON）。"
    "开场须尊重原作**时间线**：从检索证据所暗示的、玩家可介入的**较早合理锚点**切入，避免一跳到后期剧透或终盘场景；"
    "若证据含多段，优先选**时序靠前**且能建立场景与目标的片段来组织开场。"
)

OPENING_TURN_HINTS = (
    "[开场回合]\n本段为会话首次叙事：建立场景、张力与可点选项；无需承接上一轮 GM。\n"
    "首段应用一两句点明当前在作品时间轴中的位置（如章节/时期/关键事件前后关系），勿用终局或重大剧透后的台词作无铺垫开场锚点。"
)


async def _last_n_assistant_messages(
    db: AsyncSession, session_id: int, n: int
) -> list[SessionMessage]:
    res = await db.execute(
        select(SessionMessage)
        .where(
            SessionMessage.session_id == session_id,
            SessionMessage.role == "assistant",
        )
        .order_by(SessionMessage.id.desc())
        .limit(n)
    )
    rows = list(res.scalars().all())
    return list(reversed(rows))


async def _maybe_refine_strict_choices(
    *,
    mode: str,
    narrative: str,
    prev_state: dict[str, Any],
    context: str,
    choices: list[str],
    beats: list[str] | None,
) -> tuple[list[str], list[str] | None, bool]:
    """回合路径在 ``NARRATIVE_CHOICE_GROUNDING_ENABLED`` 时改走 ``ground_choices_for_turn``，本函数仅作回退/开场等保留。"""
    if mode != "strict" or not settings.NARRATIVE_STRICT_CHOICE_REFINE:
        return choices, beats, False
    if len(choices) < 2:
        return choices, beats, False
    refined = await refine_strict_choices(
        narrative_excerpt=narrative,
        state_json=json.dumps(prev_state or {}, ensure_ascii=False),
        evidence_excerpt=context,
        current_choices=choices,
        current_beats=beats,
    )
    if not refined:
        return choices, beats, False
    return refined["choices"], refined["choice_beats"], True


async def _apply_choice_grounding_or_refine(
    *,
    mode: str,
    narrative_excerpt: str,
    state: dict[str, Any],
    evidence_context: str,
    choices: list[str],
    beats: list[str] | None,
) -> tuple[list[str], list[str] | None, bool, bool, int]:
    """
    候选 options：开启 grounding 时走 ``ground_choices_for_turn``，否则 ``_maybe_refine_strict_choices``。
    返回 (choices, beats, choices_changed_flag, grounding_failed, grounding_attempts)；
    未走 grounding 时后两项为 (False, 0)。
    """
    if settings.NARRATIVE_CHOICE_GROUNDING_ENABLED and len(choices) >= 2:
        gr = await ground_choices_for_turn(
            mode=mode,
            narrative_excerpt=narrative_excerpt,
            state=state,
            evidence_context=evidence_context,
            choices=choices,
            beats=beats,
        )
        return (
            gr.choices,
            gr.choice_beats,
            gr.choices_changed_from_input,
            gr.grounding_failed,
            gr.attempts_used,
        )
    ch, be, refined = await _maybe_refine_strict_choices(
        mode=mode,
        narrative=narrative_excerpt,
        prev_state=state,
        context=evidence_context,
        choices=choices,
        beats=beats,
    )
    return ch, be, refined, False, 0


def _merge_grounding_turn_meta(
    turn_meta: dict[str, Any],
    *,
    choices_len: int,
    choices_grounding_attempts: int,
    choices_grounding_failed: bool,
) -> None:
    """写入与 BACKEND_STRUCTURE §4.4.4 一致的 grounding 键（就地更新）。"""
    if not settings.NARRATIVE_CHOICE_GROUNDING_ENABLED or choices_len < 2:
        return
    if choices_grounding_attempts:
        turn_meta["choices_grounding_attempts"] = choices_grounding_attempts
    if choices_grounding_failed:
        turn_meta["choices_grounding_failed"] = True
    elif choices_grounding_attempts:
        turn_meta["choices_grounding_passed"] = True


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
    opening_hints = OPENING_TURN_HINTS if settings.NARRATIVE_TURN_HINTS_ENABLED else None
    opening_two_phase = settings.NARRATIVE_TWO_PHASE_ENABLED
    messages = build_generation_prompt(
        OPENING_USER_PROMPT,
        context,
        state,
        None,
        mode=session.mode,
        style_config=dict(session.style_config or {}),
        templates=templates,
        history=[],
        turn_hints=opening_hints,
        narrative_concise_mode=settings.NARRATIVE_CONCISE_MODE,
        narrative_two_phase_round_one=opening_two_phase,
    )
    narrative_body: str
    choices_body: list[str]
    state_update_body: dict[str, Any]
    internal_notes_body: str
    parse_error_body: str | None
    choices_source_val: str | None = None
    choice_beats_body: list[str] | None = None
    choices_refined_flag = False

    opening_raw_full: str | None = None
    try:
        opening_raw_full = await deepseek_chat(messages, temperature=0.4)
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
        if opening_two_phase:
            p1 = parse_complete_model_output(opening_raw_full or "")
            narrative_body = strip_leaking_meta_suffix(p1.narrative)
            messages2 = build_two_phase_meta_prompt(
                context=context,
                state=state,
                narrative=narrative_body,
                user_input=session.opening_goal or OPENING_USER_PROMPT,
                mode=session.mode,
                style_config=dict(session.style_config or {}),
                templates=templates,
            )
            raw2 = ""
            try:
                raw2 = await deepseek_chat(messages2, temperature=0.35)
            except Exception as e2:  # noqa: BLE001
                logger.warning("opening two_phase round2 failed: %s", e2)
            p2 = parse_complete_model_output(raw2 or "")
            choices_body = list(p2.choices)
            state_update_body = p2.state_update
            internal_notes_body = p2.internal_notes
            parse_error_body = p2.parse_error
            choices_source_val = p2.choices_source or (
                "model_json" if choices_body else None
            )
            choice_beats_body = p2.choice_beats
        else:
            parsed = parse_complete_model_output(opening_raw_full or "")
            narrative_body = parsed.narrative
            choices_body = parsed.choices
            state_update_body = parsed.state_update
            internal_notes_body = parsed.internal_notes
            parse_error_body = parsed.parse_error
            choices_source_val = parsed.choices_source
            choice_beats_body = parsed.choice_beats
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

    narrative_body = strip_leaking_meta_suffix(narrative_body)
    if not choices_body:
        choices_body = extract_choice_lines_from_narrative(narrative_body)
        if choices_body:
            choices_source_val = "narrative_regex"
    if (
        not choices_body
        and settings.NARRATIVE_CHOICES_LLM_FALLBACK
        and narrative_body.strip()
    ):
        try:
            syn = await synthesize_choices_from_context(
                user_input="（故事开场，尚无玩家上一句行动。）",
                narrative=narrative_body,
            )
        except Exception as fb_exc:  # noqa: BLE001
            logger.warning("opening choices LLM fallback error: %s", fb_exc)
            syn = []
        if syn:
            choices_body = syn
            choices_source_val = "llm_fallback"
            choice_beats_body = None

    (
        choices_body,
        choice_beats_body,
        choices_refined_flag,
        opening_grounding_failed,
        opening_grounding_attempts,
    ) = await _apply_choice_grounding_or_refine(
        mode=session.mode,
        narrative_excerpt=narrative_body,
        state=state,
        evidence_context=context,
        choices=choices_body,
        beats=choice_beats_body,
    )

    choices_body, choice_beats_body, source_override, choices_were_deduped = (
        await ensure_at_least_two_choices(
            choices=choices_body,
            beats=choice_beats_body,
            narrative=narrative_body,
            user_input="（故事开场，尚无玩家上一句行动。）",
            assembled_context=context,
            templates=templates,
        )
    )
    if source_override is not None:
        choices_source_val = source_override

    new_turn = max(1, session.turn_count + 1)

    _log_meta_parse_issue(
        phase="opening",
        session_id=session.id,
        turn_number=new_turn,
        choices=choices_body,
        parse_error=parse_error_body,
        raw_tail_source=opening_raw_full if opening_raw_full is not None else narrative_body,
    )

    su_in = state_update_body if not parse_error_body else {}
    validated = validate_state_update(state, su_in)
    await apply_state_update(db, session.id, new_turn, validated)

    opening_meta: dict[str, Any] = {
        "opening": True,
        "choices": choices_body,
        "choices_source": choices_source_val or "none",
        "parse_error": parse_error_body,
        "profile_context_used": profile_used,
    }
    if choice_beats_body:
        opening_meta["choice_beats"] = choice_beats_body
    if choices_refined_flag:
        opening_meta["choices_refined"] = True
    if choices_were_deduped:
        opening_meta["choices_deduplicated"] = True
    if source_override in ("llm_fallback", "placeholder_fallback"):
        opening_meta["choices_min_enforced"] = True
    _merge_grounding_turn_meta(
        opening_meta,
        choices_len=len(choices_body),
        choices_grounding_attempts=opening_grounding_attempts,
        choices_grounding_failed=opening_grounding_failed,
    )
    db.add(
        SessionMessage(
            session_id=session.id,
            turn_number=new_turn,
            role="assistant",
            content=narrative_body,
            metadata_=opening_meta,
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
        assistants = await _last_n_assistant_messages(db, session.id, 2)
        prev_gm: str | None = None
        prev_prev_gm: str | None = None
        prev_meta: dict[str, Any] = {}
        if assistants:
            prev_gm = assistants[-1].content
            raw_meta = assistants[-1].metadata_
            if isinstance(raw_meta, dict):
                prev_meta = raw_meta
            if len(assistants) >= 2:
                prev_prev_gm = assistants[-2].content
        turn_hints = build_turn_hints_text(
            mode=session.mode,
            state=state,
            prev_gm_content=prev_gm,
            prev_meta=prev_meta,
            user_text=text,
            prev_prev_gm_content=prev_prev_gm,
        )
        prompt_user = text
        if settings.NARRATIVE_INPUT_BRIDGE:
            from app.services.narrative.input_bridge import rationalize_player_turn

            bridge = await rationalize_player_turn(
                user_text=text,
                state_summary=json.dumps(state or {}, ensure_ascii=False),
                mode=session.mode,
            )
            if bridge:
                prompt_user = f"{text}\n（叙事承接用·系统整理）\n{bridge}"
        # NARRATIVE_TWO_PHASE_ENABLED 时优先于 NARRATIVE_SPLIT_CHOICES_LLM（第一轮不产出可解析 META）
        split_choices_phase_one = (
            settings.NARRATIVE_SPLIT_CHOICES_LLM
            and not settings.NARRATIVE_TWO_PHASE_ENABLED
            and session.mode in ("strict", "creative")
        )
        messages = build_generation_prompt(
            prompt_user,
            context,
            state,
            None,
            mode=session.mode,
            style_config=dict(session.style_config or {}),
            templates=templates,
            history=history_for_prompt,
            turn_hints=turn_hints,
            narrative_concise_mode=settings.NARRATIVE_CONCISE_MODE,
            narrative_split_choices_phase_one=split_choices_phase_one,
            narrative_two_phase_round_one=settings.NARRATIVE_TWO_PHASE_ENABLED,
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

    parsed_stream = splitter.finalize()
    narrative_for_db = strip_leaking_meta_suffix(parsed_stream.narrative)

    if settings.NARRATIVE_TWO_PHASE_ENABLED:
        try:
            messages2 = build_two_phase_meta_prompt(
                context=context,
                state=state,
                narrative=narrative_for_db,
                user_input=text,
                mode=session.mode,
                style_config=dict(session.style_config or {}),
                templates=templates,
            )
            raw2 = await deepseek_chat(messages2, temperature=0.25)
        except Exception as e2:  # noqa: BLE001
            logger.warning("turn two_phase round2 failed: %s", e2)
            raw2 = ""
        p2 = parse_complete_model_output(raw2 or "")
        parsed = ParsedTurnOutput(
            narrative=narrative_for_db,
            choices=list(p2.choices),
            state_update=p2.state_update,
            internal_notes=p2.internal_notes,
            parse_error=p2.parse_error,
            choices_source=p2.choices_source or ("model_json" if p2.choices else None),
            choice_beats=p2.choice_beats,
        )
    else:
        parsed = ParsedTurnOutput(
            narrative=narrative_for_db,
            choices=list(parsed_stream.choices),
            state_update=parsed_stream.state_update,
            internal_notes=parsed_stream.internal_notes,
            parse_error=parsed_stream.parse_error,
            choices_source=parsed_stream.choices_source,
            choice_beats=parsed_stream.choice_beats,
        )

    if parsed.internal_notes:
        logger.info("turn internal_notes: %s", parsed.internal_notes[:500])

    _log_meta_parse_issue(
        phase="turn_stream",
        session_id=session.id,
        turn_number=current_turn,
        choices=parsed.choices,
        parse_error=parsed.parse_error,
        raw_tail_source=splitter.accumulated_raw(),
    )

    choices = list(parsed.choices)
    choices_source_val = parsed.choices_source
    if not choices:
        choices = extract_choice_lines_from_narrative(narrative_for_db)
        if choices:
            choices_source_val = "narrative_regex"
    if (
        not choices
        and settings.NARRATIVE_CHOICES_LLM_FALLBACK
        and narrative_for_db.strip()
    ):
        try:
            syn = await synthesize_choices_from_context(
                user_input=text,
                narrative=narrative_for_db,
            )
        except Exception as fb_exc:  # noqa: BLE001
            logger.warning("turn choices LLM fallback error: %s", fb_exc)
            syn = []
        if syn:
            choices = syn
            choices_source_val = "llm_fallback"

    choice_beats_val: list[str] | None = parsed.choice_beats
    if choices_source_val in ("narrative_regex", "llm_fallback"):
        choice_beats_val = None

    (
        choices,
        choice_beats_val,
        choices_refined_flag,
        choices_grounding_failed,
        choices_grounding_attempts,
    ) = await _apply_choice_grounding_or_refine(
        mode=session.mode,
        narrative_excerpt=narrative_for_db,
        state=state,
        evidence_context=context,
        choices=choices,
        beats=choice_beats_val,
    )

    choices, choice_beats_val, turn_source_override, turn_choices_deduped = (
        await ensure_at_least_two_choices(
            choices=choices,
            beats=choice_beats_val,
            narrative=narrative_for_db,
            user_input=text,
            assembled_context=context,
            templates=templates,
        )
    )
    if turn_source_override is not None:
        choices_source_val = turn_source_override

    su = parsed.state_update if not parsed.parse_error else {}
    validated = validate_state_update(state, su)

    try:
        await apply_state_update(db, session.id, current_turn, validated)
        turn_meta: dict[str, Any] = {
            "choices": choices,
            "choices_source": choices_source_val or "none",
            "parse_error": parsed.parse_error,
            "rag_variant": retrieved.variant_type if retrieved else None,
            "profile_context_used": profile_used,
        }
        if choice_beats_val:
            turn_meta["choice_beats"] = choice_beats_val
        if choices_refined_flag:
            turn_meta["choices_refined"] = True
        if turn_choices_deduped:
            turn_meta["choices_deduplicated"] = True
        if turn_source_override in ("llm_fallback", "placeholder_fallback"):
            turn_meta["choices_min_enforced"] = True
        _merge_grounding_turn_meta(
            turn_meta,
            choices_len=len(choices),
            choices_grounding_attempts=choices_grounding_attempts,
            choices_grounding_failed=choices_grounding_failed,
        )
        db.add(
            SessionMessage(
                session_id=session.id,
                turn_number=current_turn,
                role="assistant",
                content=narrative_for_db,
                metadata_=turn_meta,
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
        schedule_profile_inference_after_turn(session.id, session.turn_count)
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

    yield _sse_line({"type": "done"})
