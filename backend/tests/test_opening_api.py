"""POST /api/sessions/{id}/opening：前置校验、409 幂等。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.prompt_template import PromptTemplate
from app.models.rag_config import RagConfig
from app.models.session import Session as NarrativeSession
from app.models.session import SessionMessage
from app.models.story import Story, StoryVersion
from app.models.user import User


def _seed_opening_case(
    *,
    rag_config_id: int = 1,
    with_assistant_message: bool = False,
    with_prompt_templates: bool = True,
):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def init() -> tuple[str, int]:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with SessionLocal() as db:
            db.add(
                User(
                    username="op_user",
                    password_hash=hash_password("pw12345678"),
                    display_name="O",
                    role="player",
                )
            )
            db.add(
                RagConfig(
                    name="rc_op",
                    variant_type="naive_hybrid",
                    config={},
                    is_active=True,
                )
            )
            db.add(Story(title="St", description=None, status="ready"))
            await db.flush()
            db.add(
                StoryVersion(
                    story_id=1,
                    version_number=1,
                    is_active=True,
                    is_backup=False,
                    is_archived=False,
                )
            )
            await db.flush()
            if with_prompt_templates:
                for layer, name in (
                    ("system", "s"),
                    ("gm", "g"),
                    ("style", "y"),
                    ("retrieval", "r"),
                ):
                    db.add(
                        PromptTemplate(
                            name=name,
                            layer=layer,
                            template_text=f"[{layer}] {{style_config}} ctx {{context}}",
                            applicable_mode="strict",
                            is_active=True,
                        )
                    )
            res = await db.execute(select(User).where(User.username == "op_user"))
            user = res.scalar_one()
            db.add(
                NarrativeSession(
                    user_id=user.id,
                    story_id=1,
                    story_version_id=1,
                    rag_config_id=rag_config_id,
                    mode="strict",
                    opening_goal="intent",
                    style_config={},
                    narrative_status="opening_pending",
                    narrative_plan={"current_timeline_order": 1, "arc_end_order": 1},
                    status="active",
                    turn_count=0,
                )
            )
            await db.flush()
            res2 = await db.execute(select(NarrativeSession))
            sess = res2.scalar_one()
            if with_assistant_message:
                db.add(
                    SessionMessage(
                        session_id=sess.id,
                        turn_number=1,
                        role="assistant",
                        content="hi",
                        metadata_={},
                    )
                )
            await db.commit()
            token = create_access_token({"sub": str(user.id)})
            return token, sess.id

    return SessionLocal, asyncio.run(init())


def test_post_opening_409_when_assistant_exists() -> None:
    SessionLocal, (token, sid) = _seed_opening_case(with_assistant_message=True)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with SessionLocal() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("app.api.sessions.async_session_factory", SessionLocal):
            with TestClient(app) as client:
                r = client.post(
                    f"/api/sessions/{sid}/opening",
                    headers={"Authorization": f"Bearer {token}"},
                )
        assert r.status_code == 409
        assert "助手" in str(r.json().get("detail", ""))
    finally:
        app.dependency_overrides.clear()


def test_post_opening_400_when_rag_missing() -> None:
    SessionLocal, (token, sid) = _seed_opening_case(rag_config_id=99999, with_prompt_templates=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with SessionLocal() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("app.api.sessions.async_session_factory", SessionLocal):
            with TestClient(app) as client:
                r = client.post(
                    f"/api/sessions/{sid}/opening",
                    headers={"Authorization": f"Bearer {token}"},
                )
        assert r.status_code == 400
        assert "rag" in str(r.json().get("detail", "")).lower()
    finally:
        app.dependency_overrides.clear()


def test_post_opening_503_when_prompt_templates_missing() -> None:
    SessionLocal, (token, sid) = _seed_opening_case(with_prompt_templates=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with SessionLocal() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("app.api.sessions.async_session_factory", SessionLocal):
            with TestClient(app) as client:
                r = client.post(
                    f"/api/sessions/{sid}/opening",
                    headers={"Authorization": f"Bearer {token}"},
                )
        assert r.status_code == 503
        detail = str(r.json().get("detail", ""))
        assert "模板" in detail
    finally:
        app.dependency_overrides.clear()
