"""玩家端作品列表与详情。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.content import Chapter
from app.models.story import Story, StoryVersion
from app.models.user import User
from app.schemas.story import PlayerChapterOutline, PlayerStoryDetail, PlayerStoryListItem

router = APIRouter()


async def _active_version_id(db: AsyncSession, story_id: int) -> int | None:
    res = await db.execute(
        select(StoryVersion.id).where(
            StoryVersion.story_id == story_id,
            StoryVersion.is_active.is_(True),
        )
    )
    return res.scalar_one_or_none()


@router.get("", response_model=list[PlayerStoryListItem])
async def list_ready_stories(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(Story)
        .where(Story.deleted_at.is_(None), Story.status == "ready")
        .order_by(Story.id.desc())
    )
    stories = list(res.scalars().all())
    return [
        PlayerStoryListItem(
            id=s.id,
            title=s.title,
            description=s.description,
            created_at=s.created_at,
        )
        for s in stories
    ]


@router.get("/{story_id}", response_model=PlayerStoryDetail)
async def get_story_detail(
    story_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    story = await db.get(Story, story_id)
    if story is None or story.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作品不存在")
    if story.status != "ready":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作品未就绪或不可用")

    av_id = await _active_version_id(db, story_id)
    if av_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作品无生效版本")

    cres = await db.execute(
        select(Chapter)
        .where(Chapter.story_version_id == av_id)
        .order_by(Chapter.chapter_number)
    )
    chapters = list(cres.scalars().all())
    outlines = [
        PlayerChapterOutline(
            id=ch.id,
            chapter_number=ch.chapter_number,
            title=ch.title,
            summary=ch.summary,
        )
        for ch in chapters
    ]
    return PlayerStoryDetail(
        id=story.id,
        title=story.title,
        description=story.description,
        chapters=outlines,
    )
