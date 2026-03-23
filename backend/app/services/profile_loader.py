"""从 DB 加载会话相关的用户画像（全局 + 作品覆写）。参照 BACKEND_STRUCTURE §4.3、IMPLEMENTATION_PLAN 4.8。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import StoryProfile, UserProfile


async def load_session_profile_bundle(
    db: AsyncSession,
    user_id: int,
    story_id: int,
) -> dict[str, Any]:
    """
    返回可 JSON 序列化的画像包，供 assemble_context / 评测元数据使用。
    键：user_preferences（无行则为 {}）、story_overrides（无行则为 {}）。
    """
    up = (
        await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    ).scalar_one_or_none()
    sp = (
        await db.execute(
            select(StoryProfile).where(
                StoryProfile.user_id == user_id,
                StoryProfile.story_id == story_id,
            )
        )
    ).scalar_one_or_none()

    return {
        "user_preferences": dict(up.preferences) if up else {},
        "story_overrides": dict(sp.overrides) if sp else {},
    }


def profile_bundle_nonempty(bundle: dict[str, Any] | None) -> bool:
    if not bundle:
        return False
    prefs = bundle.get("user_preferences") or {}
    over = bundle.get("story_overrides") or {}
    return bool(prefs) or bool(over)
