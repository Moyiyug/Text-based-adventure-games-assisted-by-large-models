"""completed 会话：POST messages / resume 返回 409。Phase 11.4。"""

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
from app.models.rag_config import RagConfig
from app.models.session import Session as NarrativeSession
from app.models.story import Story, StoryVersion
from app.models.user import User


def _seed_session_factory(*, narrative_status: str, session_status: str):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def init() -> tuple[str, int]:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with SessionLocal() as db:
            db.add(
                User(
                    username="nc_done",
                    password_hash=hash_password("pw12345678"),
                    display_name="N",
                    role="player",
                )
            )
            db.add(
                RagConfig(
                    name="rc_nc",
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
            res = await db.execute(select(User).where(User.username == "nc_done"))
            user = res.scalar_one()
            db.add(
                NarrativeSession(
                    user_id=user.id,
                    story_id=1,
                    story_version_id=1,
                    rag_config_id=1,
                    mode="strict",
                    opening_goal="intent",
                    style_config={},
                    narrative_status=narrative_status,
                    narrative_plan={"current_timeline_order": 1, "arc_end_order": 1},
                    status=session_status,
                    turn_count=1,
                )
            )
            await db.commit()
            res2 = await db.execute(select(NarrativeSession))
            sess = res2.scalar_one()
            token = create_access_token({"sub": str(user.id)})
            return token, sess.id

    return SessionLocal, asyncio.run(init())


def test_post_messages_409_when_narrative_completed() -> None:
    SessionLocal, (token, sid) = _seed_session_factory(
        narrative_status="completed",
        session_status="active",
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with SessionLocal() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("app.api.sessions.async_session_factory", SessionLocal):
            with TestClient(app) as client:
                r = client.post(
                    f"/api/sessions/{sid}/messages",
                    json={"content": "hello"},
                    headers={"Authorization": f"Bearer {token}"},
                )
        assert r.status_code == 409
        body = r.json()
        assert "detail" in body
        assert "已完成" in str(body["detail"])
    finally:
        app.dependency_overrides.clear()


def test_resume_409_when_narrative_completed() -> None:
    SessionLocal, (token, sid) = _seed_session_factory(
        narrative_status="completed",
        session_status="archived",
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with SessionLocal() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            r = client.post(
                f"/api/sessions/{sid}/resume",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 409
        assert "已完成" in str(r.json().get("detail", ""))
    finally:
        app.dependency_overrides.clear()
