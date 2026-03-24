"""画像推断、合并与 profile API。参照 Phase 5.1–5.4。"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import Base
from app.models.profile import StoryProfile, UserProfile
from app.models.story import Story
from app.models.user import User
from app.services.profile import (
    apply_profile_update,
    classify_update_target,
    infer_preferences,
    merge_profile_json,
    schedule_profile_inference_after_turn,
)


def test_merge_profile_json_nested() -> None:
    base = {"a": {"x": 1}, "b": 2}
    patch = {"a": {"y": 3}, "c": 4}
    out = merge_profile_json(base, patch)
    assert out["a"] == {"x": 1, "y": 3}
    assert out["b"] == 2
    assert out["c"] == 4


def test_classify_update_target_explicit_and_patch_keys() -> None:
    assert classify_update_target({"target": "global", "patch": {"reading_style": "细"}}) == "global"
    assert classify_update_target({"target": "story", "patch": {"world_identity": "盗贼"}}) == "story"
    assert classify_update_target({"patch": {"npc_relations": {}}}) == "story"
    assert classify_update_target({"patch": {"moral_tendency": "守序"}}) == "global"
    assert classify_update_target({"patch": {"unknown_key": "v"}}) == "global"


def test_classify_mismatch_target_corrected_by_keys() -> None:
    assert (
        classify_update_target({"target": "global", "patch": {"world_identity": "仅故事键"}})
        == "story"
    )
    assert (
        classify_update_target({"target": "story", "patch": {"reading_style": "仅全局键"}})
        == "global"
    )


def test_infer_preferences_parses_deepseek_json() -> None:
    class Msg:
        def __init__(self, role: str, content: str) -> None:
            self.role = role
            self.content = content

    async def _run() -> None:
        raw_llm = '{"updates":[{"target":"global","patch":{"reading_style":"快节奏"}}]}'
        with patch(
            "app.services.profile.deepseek_chat",
            new_callable=AsyncMock,
            return_value=raw_llm,
        ):
            out = await infer_preferences(
                [Msg("user", "快点推进")],
                {"user_preferences": {}, "story_overrides": {}},
            )
        assert out == [{"target": "global", "patch": {"reading_style": "快节奏"}}]

    asyncio.run(_run())


def test_apply_profile_update_upsert() -> None:
    async def _run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with SessionLocal() as db:
            db.add(
                User(
                    username="pu1",
                    password_hash=hash_password("pw12345678"),
                    display_name="P",
                    role="player",
                )
            )
            await db.commit()
            res = await db.execute(select(User).where(User.username == "pu1"))
            u = res.scalar_one()
            uid = u.id
            await apply_profile_update(
                db,
                uid,
                1,
                [{"target": "global", "patch": {"reading_style": "a"}}],
            )
            await apply_profile_update(
                db,
                uid,
                1,
                [{"target": "global", "patch": {"difficulty_level": "hard"}}],
            )
            await apply_profile_update(
                db,
                uid,
                1,
                [{"target": "story", "patch": {"stage_goals": "逃出去"}}],
            )
        async with SessionLocal() as db:
            up = (await db.execute(select(UserProfile).where(UserProfile.user_id == uid))).scalar_one()
            assert up.preferences.get("reading_style") == "a"
            assert up.preferences.get("difficulty_level") == "hard"
            sp = (await db.execute(select(StoryProfile).where(StoryProfile.user_id == uid))).scalar_one()
            assert sp.overrides.get("stage_goals") == "逃出去"
        await engine.dispose()

    asyncio.run(_run())


def _memory_client_with_user_story():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    async def init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with SessionLocal() as s:
            s.add(
                User(
                    username="apiu1",
                    password_hash=hash_password("pw12345678"),
                    display_name="A",
                    role="player",
                )
            )
            s.add(Story(title="T1", description=None, status="ready"))
            await s.commit()
            res = await s.execute(select(User).where(User.username == "apiu1"))
            user = res.scalar_one()
            token = create_access_token({"sub": str(user.id)})
            return SessionLocal, token

    SessionLocal, token = asyncio.run(init())

    async def override_get_db():
        async with SessionLocal() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = override_get_db
    return engine, SessionLocal, token


def test_get_profile_unauthorized() -> None:
    with TestClient(app) as client:
        r = client.get("/api/users/me/profile")
        assert r.status_code in (401, 403)


def test_get_profile_authorized_empty() -> None:
    engine, _sl, token = _memory_client_with_user_story()
    try:
        with TestClient(app) as client:
            r = client.get(
                "/api/users/me/profile",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            assert r.json() == {"preferences": {}}
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())


def test_get_story_profile_404() -> None:
    engine, _sl, token = _memory_client_with_user_story()
    try:
        with TestClient(app) as client:
            r = client.get(
                "/api/users/me/profile/story/99999",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())


def test_import_profile_invalid_json_422() -> None:
    engine, _sl, token = _memory_client_with_user_story()
    try:
        with TestClient(app) as client:
            r = client.post(
                "/api/users/me/profile/import",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("card.json", b"not json", "application/json")},
            )
            assert r.status_code == 422
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())


def test_import_profile_story_scope_without_story_id_422() -> None:
    engine, _sl, token = _memory_client_with_user_story()
    try:
        body = json.dumps({"scope": "story", "payload": {}})
        with TestClient(app) as client:
            r = client.post(
                "/api/users/me/profile/import",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("card.json", body.encode("utf-8"), "application/json")},
            )
            assert r.status_code == 422
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())


def test_import_profile_user_id_mismatch_400() -> None:
    engine, _sl, token = _memory_client_with_user_story()
    try:
        body = json.dumps(
            {"scope": "global", "user_id": 99999, "payload": {"reading_style": "x"}}
        )
        with TestClient(app) as client:
            r = client.post(
                "/api/users/me/profile/import",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("card.json", body.encode("utf-8"), "application/json")},
            )
            assert r.status_code == 400
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())


def test_schedule_profile_inference_skips_when_disabled() -> None:
    with patch.object(settings, "PROFILE_INFERENCE_ENABLED", False):
        with patch("app.services.profile.asyncio.create_task") as m_task:
            schedule_profile_inference_after_turn(1, 4)
            m_task.assert_not_called()


def test_schedule_profile_inference_triggers_on_interval() -> None:
    def _swallow_coro(coro):
        if asyncio.iscoroutine(coro):
            coro.close()
        return MagicMock()

    with patch.object(settings, "PROFILE_INFERENCE_ENABLED", True):
        with patch.object(settings, "PROFILE_INFERENCE_EVERY_N_TURNS", 4):
            with patch(
                "app.services.profile.asyncio.create_task",
                side_effect=_swallow_coro,
            ) as m_task:
                schedule_profile_inference_after_turn(7, 4)
                m_task.assert_called_once()
