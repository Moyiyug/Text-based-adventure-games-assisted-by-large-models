"""管理员查看全站会话。参照 BACKEND_STRUCTURE §2.10。"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.session import Session as NarrativeSession
from app.models.session import SessionMessage, UserFeedback
from app.models.story import Story
from app.models.user import User
from app.schemas.admin_session import (
    AdminSessionListItem,
    AdminSessionsListResponse,
    AdminUserFeedbackOut,
    FeedbackListResponse,
    TranscriptResponse,
    TranscriptSessionMeta,
)
from app.schemas.session import SessionMessageOut

router = APIRouter(prefix="/sessions", tags=["admin-sessions"])

_DEFAULT_LIMIT = 100
_MAX_LIMIT = 500


@router.get("", response_model=AdminSessionsListResponse)
async def list_all_sessions(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    user_id: int | None = None,
    story_id: int | None = None,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    def _filters(q):
        if user_id is not None:
            q = q.where(NarrativeSession.user_id == user_id)
        if story_id is not None:
            q = q.where(NarrativeSession.story_id == story_id)
        if status_filter is not None:
            q = q.where(NarrativeSession.status == status_filter)
        return q

    count_q = _filters(select(func.count()).select_from(NarrativeSession))
    total = int((await db.execute(count_q)).scalar_one())

    list_q = _filters(select(NarrativeSession)).order_by(NarrativeSession.updated_at.desc())
    res = await db.execute(list_q.offset(offset).limit(limit))
    sessions = list(res.scalars().all())
    if not sessions:
        return AdminSessionsListResponse(items=[], total=total)

    uids = {s.user_id for s in sessions}
    sids = {s.story_id for s in sessions}
    users = {}
    if uids:
        ures = await db.execute(select(User).where(User.id.in_(uids)))
        users = {u.id: u for u in ures.scalars().all()}
    stories = {}
    if sids:
        sres = await db.execute(select(Story).where(Story.id.in_(sids)))
        stories = {st.id: st for st in sres.scalars().all()}

    items: list[AdminSessionListItem] = []
    for s in sessions:
        u = users.get(s.user_id)
        st = stories.get(s.story_id)
        items.append(
            AdminSessionListItem(
                id=s.id,
                user_id=s.user_id,
                username=u.username if u else "",
                story_id=s.story_id,
                story_title=st.title if st else "",
                story_version_id=s.story_version_id,
                rag_config_id=s.rag_config_id,
                mode=s.mode,
                status=s.status,
                narrative_status=s.narrative_status,
                narrative_plan=dict(s.narrative_plan or {}),
                turn_count=s.turn_count,
                opening_goal=s.opening_goal,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
        )
    return AdminSessionsListResponse(items=items, total=total)


@router.get("/{session_id}/transcript", response_model=TranscriptResponse)
async def get_session_transcript(
    session_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    sess = await db.get(NarrativeSession, session_id)
    if sess is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")

    mres = await db.execute(
        select(SessionMessage)
        .where(SessionMessage.session_id == session_id)
        .order_by(SessionMessage.id.asc())
    )
    messages = [SessionMessageOut.model_validate(m) for m in mres.scalars().all()]
    return TranscriptResponse(
        session=TranscriptSessionMeta.model_validate(sess),
        messages=messages,
    )


@router.get("/{session_id}/feedback", response_model=FeedbackListResponse)
async def list_session_feedback(
    session_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    sess = await db.get(NarrativeSession, session_id)
    if sess is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")

    res = await db.execute(
        select(UserFeedback)
        .where(UserFeedback.session_id == session_id)
        .order_by(UserFeedback.id.asc())
    )
    rows = list(res.scalars().all())
    return FeedbackListResponse(
        items=[AdminUserFeedbackOut.model_validate(r) for r in rows],
    )
