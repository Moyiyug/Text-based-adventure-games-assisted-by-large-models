import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.profile import StoryProfile, UserProfile
from app.models.story import Story
from app.models.user import User
from app.schemas.auth import UserResponse
from app.schemas.profile import (
    GlobalProfileResponse,
    ProfileCardImport,
    ProfileImportResponse,
    StoryProfileResponse,
)
from app.schemas.user import UpdateSettingsRequest
from app.services.profile import apply_profile_update

router = APIRouter()


@router.put("/me/settings", response_model=UserResponse)
async def update_settings(
    data: UpdateSettingsRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.display_name is not None:
        user.display_name = data.display_name
    if data.bio is not None:
        user.bio = data.bio
    await db.flush()
    await db.refresh(user)
    return user


@router.get("/me/profile", response_model=GlobalProfileResponse)
async def get_my_global_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = (
        await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    ).scalar_one_or_none()
    prefs = dict(row.preferences) if row else {}
    return GlobalProfileResponse(preferences=prefs)


async def _require_story_exists(db: AsyncSession, story_id: int) -> Story:
    story = await db.get(Story, story_id)
    if story is None or story.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作品不存在")
    return story


@router.get("/me/profile/story/{story_id}", response_model=StoryProfileResponse)
async def get_my_story_profile(
    story_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_story_exists(db, story_id)
    row = (
        await db.execute(
            select(StoryProfile).where(
                StoryProfile.user_id == user.id,
                StoryProfile.story_id == story_id,
            )
        )
    ).scalar_one_or_none()
    ov = dict(row.overrides) if row else {}
    return StoryProfileResponse(story_id=story_id, overrides=ov)


@router.post("/me/profile/import", response_model=ProfileImportResponse)
async def import_profile_card(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    raw = await file.read()
    max_b = settings.PROFILE_IMPORT_MAX_BYTES
    if len(raw) > max_b:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件过大，上限 {max_b} 字节",
        )
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="角色卡须为 UTF-8 编码的 JSON",
        ) from e
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="角色卡 JSON 格式不合法",
        ) from e
    if not isinstance(obj, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="角色卡 JSON 格式不合法",
        )
    try:
        card = ProfileCardImport.model_validate(obj)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="角色卡 JSON 格式不合法",
        ) from e

    if card.user_id is not None and card.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id 与当前账号不一致",
        )

    story_db_id = 0
    if card.scope == "story":
        sid = card.story_id
        assert sid is not None
        await _require_story_exists(db, sid)
        story_db_id = sid

    target = "global" if card.scope == "global" else "story"
    patch = dict(card.payload) if card.payload else {}
    if patch:
        await apply_profile_update(
            db,
            user.id,
            story_db_id,
            [{"target": target, "patch": patch}],
        )

    up_row = (
        await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    ).scalar_one_or_none()
    prefs = dict(up_row.preferences) if up_row else {}
    if card.scope == "story":
        sid = card.story_id
        assert sid is not None
        sp_row = (
            await db.execute(
                select(StoryProfile).where(
                    StoryProfile.user_id == user.id,
                    StoryProfile.story_id == sid,
                )
            )
        ).scalar_one_or_none()
        ovs = dict(sp_row.overrides) if sp_row else {}
        return ProfileImportResponse(
            scope="story",
            preferences=prefs,
            story_id=sid,
            overrides=ovs,
        )
    return ProfileImportResponse(scope="global", preferences=prefs)
