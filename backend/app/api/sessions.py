"""玩家会话 CRUD。流式 POST .../messages 见 Phase 4.4。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory, get_db
from app.core.dependencies import get_current_user, require_session_owner
from app.models.session import Session as NarrativeSession
from app.models.session import SessionMessage, SessionState, UserFeedback
from app.models.story import Story, StoryVersion
from app.models.user import User
from app.schemas.session import (
    FeedbackCreate,
    OpeningGenerationResponse,
    SessionCreate,
    SessionCreateResponse,
    SessionListItem,
    SessionMessageCreate,
    SessionMessageOut,
    SessionResponse,
    SessionStateSnapshot,
    UserFeedbackOut,
)
from app.services.narrative.engine import EmptyOpeningNarrativeError, generate_opening, process_turn_sse
from app.services.narrative.session_validators import validate_session_ready_for_opening
from app.services.narrative.session_arc_planner import (
    apply_narrative_plan_to_session,
    plan_session_arc,
)
from app.services.narrative.state import initialize_state
from app.services.rag.dispatcher import get_active_rag_config, get_rag_config_by_id

router = APIRouter()

_MESSAGES_CAP = 500


async def _active_version_id(db: AsyncSession, story_id: int) -> int | None:
    res = await db.execute(
        select(StoryVersion.id).where(
            StoryVersion.story_id == story_id,
            StoryVersion.is_active.is_(True),
        )
    )
    return res.scalar_one_or_none()


async def _latest_state_row(db: AsyncSession, session_id: int) -> SessionState | None:
    res = await db.execute(
        select(SessionState)
        .where(SessionState.session_id == session_id)
        .order_by(SessionState.turn_number.desc(), SessionState.id.desc())
        .limit(1)
    )
    return res.scalar_one_or_none()


def _state_snapshot(row: SessionState | None) -> SessionStateSnapshot | None:
    if row is None:
        return None
    return SessionStateSnapshot.model_validate(row)


def _session_detail(
    sess: NarrativeSession,
    latest: SessionState | None,
) -> SessionResponse:
    data = SessionResponse.model_validate(sess).model_dump()
    data["latest_state"] = _state_snapshot(latest)
    return SessionResponse(**data)


@router.post("", response_model=SessionCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: SessionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    story = await db.get(Story, body.story_id)
    if story is None or story.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作品不存在")
    if story.status != "ready":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="作品未就绪，无法开始会话")

    sv_id = await _active_version_id(db, body.story_id)
    if sv_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="作品无生效版本")

    if body.rag_config_id is not None:
        rc = await get_rag_config_by_id(db, body.rag_config_id)
        if rc is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="rag_config 不存在")
        rag_id = rc.id
    else:
        rc = await get_active_rag_config(db)
        rag_id = rc.id

    style = dict(body.style_config or {})

    sess = NarrativeSession(
        user_id=user.id,
        story_id=body.story_id,
        story_version_id=sv_id,
        rag_config_id=rag_id,
        mode=body.mode,
        opening_goal=body.opening_goal.strip(),
        style_config=style,
        status="active",
        turn_count=0,
    )
    db.add(sess)
    await db.flush()

    arc_plan = await plan_session_arc(db, sess)
    apply_narrative_plan_to_session(sess, arc_plan, narrative_status="opening_pending")

    db.add(
        SessionState(
            session_id=sess.id,
            turn_number=0,
            state=initialize_state(sess),
        )
    )
    await db.commit()
    await db.refresh(sess)

    latest = await _latest_state_row(db, sess.id)
    base = _session_detail(sess, latest)
    return SessionCreateResponse(
        **base.model_dump(),
        opening_message=None,
    )


@router.get("", response_model=list[SessionListItem])
async def list_my_sessions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(NarrativeSession)
        .where(NarrativeSession.user_id == user.id)
        .order_by(NarrativeSession.updated_at.desc())
    )
    rows = list(res.scalars().all())
    return [SessionListItem.model_validate(r) for r in rows]


@router.post("/{session_id}/opening", response_model=OpeningGenerationResponse)
async def create_opening_narrative(
    session_id: int,
    user: User = Depends(get_current_user),
):
    """生成开场叙事并落库（幂等：已存在 assistant 消息则 409）。"""
    async with async_session_factory() as db:
        sess = await db.get(NarrativeSession, session_id)
        if sess is None or sess.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
        if sess.status != "active":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="会话非活跃状态")
        ac = await db.scalar(
            select(func.count())
            .select_from(SessionMessage)
            .where(
                SessionMessage.session_id == session_id,
                SessionMessage.role == "assistant",
            )
        )
        if (ac or 0) > 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已存在助手消息，无需重复生成开场")

        await validate_session_ready_for_opening(db, sess)

        ac2 = await db.scalar(
            select(func.count())
            .select_from(SessionMessage)
            .where(
                SessionMessage.session_id == session_id,
                SessionMessage.role == "assistant",
            )
        )
        if (ac2 or 0) > 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已存在助手消息，无需重复生成开场")

        try:
            out = await generate_opening(db, sess)
        except EmptyOpeningNarrativeError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="开场叙事生成失败：正文为空，请稍后重试",
            ) from None
        return OpeningGenerationResponse(
            narrative=out.narrative,
            choices=out.choices,
            state_update=out.state_update,
            parse_error=out.parse_error,
        )


@router.post("/{session_id}/messages")
async def stream_session_message(
    session_id: int,
    body: SessionMessageCreate,
    user: User = Depends(get_current_user),
):
    """流式叙事回合（SSE）。使用独立 DB 会话，避免与 get_db 长事务冲突。"""
    async with async_session_factory() as db:
        sess = await db.get(NarrativeSession, session_id)
        if sess is None or sess.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
        if sess.status != "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="会话已归档或非活跃",
            )
        if sess.narrative_status == "completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="会话故事线已完成，无法继续推进",
            )

    async def event_stream():
        async with async_session_factory() as db:
            sess = await db.get(NarrativeSession, session_id)
            if sess is None or sess.user_id != user.id:
                yield 'data: {"type":"error","message":"会话不存在"}\n\n'
                yield 'data: {"type":"done"}\n\n'
                return
            if sess.status != "active":
                yield 'data: {"type":"error","message":"会话已归档或非活跃"}\n\n'
                yield 'data: {"type":"done"}\n\n'
                return
            if sess.narrative_status == "completed":
                yield 'data: {"type":"error","message":"会话故事线已完成，无法继续推进"}\n\n'
                yield 'data: {"type":"done"}\n\n'
                return
            async for line in process_turn_sse(db, sess, body.content):
                yield line

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream; charset=utf-8",
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    sess: NarrativeSession = Depends(require_session_owner),
):
    latest = await _latest_state_row(db, session_id)
    return _session_detail(sess, latest)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    sess: NarrativeSession = Depends(require_session_owner),
):
    await db.delete(sess)
    await db.commit()
    return None


@router.post("/{session_id}/archive", response_model=SessionResponse)
async def archive_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    sess: NarrativeSession = Depends(require_session_owner),
):
    sess.status = "archived"
    sess.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(sess)
    latest = await _latest_state_row(db, session_id)
    return _session_detail(sess, latest)


@router.post("/{session_id}/resume", response_model=SessionResponse)
async def resume_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    sess: NarrativeSession = Depends(require_session_owner),
):
    """将 archived 会话恢复为 active，以便继续 POST .../messages。参见 BACKEND_STRUCTURE §2.4。"""
    if sess.status == "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="会话已是进行中",
        )
    if sess.status != "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="仅支持从已归档状态恢复会话",
        )
    if sess.narrative_status == "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="故事线已完成，无法恢复为可推进状态",
        )
    sess.status = "active"
    sess.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(sess)
    latest = await _latest_state_row(db, session_id)
    return _session_detail(sess, latest)


@router.get("/{session_id}/messages", response_model=list[SessionMessageOut])
async def list_messages(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    _sess: NarrativeSession = Depends(require_session_owner),
):
    res = await db.execute(
        select(SessionMessage)
        .where(SessionMessage.session_id == session_id)
        .order_by(SessionMessage.id.asc())
        .limit(_MESSAGES_CAP)
    )
    rows = list(res.scalars().all())
    return [SessionMessageOut.model_validate(m) for m in rows]


@router.get("/{session_id}/state", response_model=SessionStateSnapshot)
async def get_current_state(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    _sess: NarrativeSession = Depends(require_session_owner),
):
    latest = await _latest_state_row(db, session_id)
    if latest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="无状态记录")
    return SessionStateSnapshot.model_validate(latest)


@router.post("/{session_id}/feedback", response_model=UserFeedbackOut, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    session_id: int,
    body: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    _sess: NarrativeSession = Depends(require_session_owner),
):
    msg = await db.get(SessionMessage, body.message_id)
    if msg is None or msg.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="消息不属于该会话")

    fb = UserFeedback(
        session_id=session_id,
        message_id=body.message_id,
        feedback_type=body.feedback_type.strip(),
        content=body.content.strip() if body.content else None,
        reviewed=False,
    )
    db.add(fb)
    await db.commit()
    await db.refresh(fb)
    return UserFeedbackOut.model_validate(fb)
