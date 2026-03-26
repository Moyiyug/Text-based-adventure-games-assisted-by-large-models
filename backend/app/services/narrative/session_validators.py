"""会话开场前校验：作品版本、RAG、提示模板。"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session as NarrativeSession
from app.models.story import Story, StoryVersion
from app.services.narrative.prompts import load_prompt_templates
from app.services.rag.dispatcher import get_rag_config_by_id


async def validate_session_ready_for_opening(db: AsyncSession, sess: NarrativeSession) -> None:
    """
    校验开场生成前置条件；失败时抛出 HTTPException（明确 detail）。
    调用方须已确认会话存在、活跃、且无助手消息（或仅在竞态二次校验前使用）。
    """
    if sess.story_version_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="会话缺少作品版本，无法生成开场",
        )

    sv = await db.get(StoryVersion, sess.story_version_id)
    if sv is None or sv.story_id != sess.story_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="会话关联的作品版本无效",
        )
    if not sv.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="会话绑定的作品版本未生效，无法生成开场",
        )

    story = await db.get(Story, sess.story_id)
    if story is None or story.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作品不存在")
    if story.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="作品未就绪，无法生成开场",
        )

    if sess.rag_config_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="会话缺少 RAG 配置",
        )
    rc = await get_rag_config_by_id(db, sess.rag_config_id)
    if rc is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="rag_config 不存在或已删除",
        )

    try:
        templates = await load_prompt_templates(db, sess.mode)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e) or "会话模式无效",
        ) from e

    missing = [
        layer
        for layer in ("system", "gm", "style", "retrieval")
        if not (templates.get(layer) or "").strip()
    ]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="叙事模板未就绪：缺少 " + "、".join(missing) + " 层激活模板",
        )
