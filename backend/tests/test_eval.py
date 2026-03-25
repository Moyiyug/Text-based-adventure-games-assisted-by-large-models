"""评测 ORM、服务与管理端 API。参照 Phase 6。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.content import TextChunk
from app.models.eval import EvalCase, EvalResult, EvalRun
from app.models.rag_config import RagConfig
from app.models.session import Session as NarrativeSession
from app.models.session import SessionMessage
from app.models.story import Story, StoryVersion
from app.models.user import User
from app.services.eval import SESSION_TURN, run_evaluation_job
from app.services.rag.base import RetrievalResult


def test_admin_eval_routes_registered() -> None:
    paths = [getattr(r, "path", "") for r in app.routes]
    assert any("/api/admin/eval/runs" in p for p in paths)


def _seed_eval_fixtures(*, admin: bool = True):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    async def init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with SessionLocal() as s:
            s.add(
                User(
                    username="ev_admin" if admin else "ev_player",
                    password_hash=hash_password("pw12345678"),
                    display_name="E",
                    role="admin" if admin else "player",
                )
            )
            s.add(RagConfig(name="rc1", variant_type="naive_hybrid", config={}, is_active=True))
            s.add(Story(title="S1", description=None, status="ready"))
            await s.flush()
            s.add(
                StoryVersion(
                    story_id=1,
                    version_number=1,
                    is_active=True,
                    is_backup=False,
                    is_archived=False,
                )
            )
            await s.flush()
            s.add(
                TextChunk(
                    story_version_id=1,
                    chapter_id=None,
                    scene_id=None,
                    chunk_index=0,
                    content="主角在雨天进入古城，遇见守门人。",
                )
            )
            s.add(
                EvalCase(
                    story_version_id=1,
                    case_type="fact_qa",
                    question="守门人何时出现？",
                    evidence_spans=["古城"],
                    rubric="是否基于材料",
                )
            )
            await s.commit()
            res = await s.execute(select(User).where(User.username == ("ev_admin" if admin else "ev_player")))
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


def test_eval_runs_unauthorized() -> None:
    with TestClient(app) as client:
        r = client.get("/api/admin/eval/runs")
        assert r.status_code in (401, 403)


def test_eval_runs_forbidden_player() -> None:
    engine, _sl, token = _seed_eval_fixtures(admin=False)
    try:
        with TestClient(app) as client:
            r = client.get(
                "/api/admin/eval/runs",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())


def test_start_eval_run_202_and_skips_background() -> None:
    engine, SessionLocal, token = _seed_eval_fixtures(admin=True)

    async def noop_job(_rid: int, _cids: list[int] | None) -> None:
        return None

    try:
        with patch("app.api.admin.eval.run_evaluation_job", new=noop_job):
            with TestClient(app) as client:
                r = client.post(
                    "/api/admin/eval/runs",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "rag_config_id": 1,
                        "story_version_id": 1,
                        "generate_cases": False,
                        "case_ids": [1],
                    },
                )
        assert r.status_code == 202
        data = r.json()
        assert "run_id" in data
        rid = data["run_id"]
        with TestClient(app) as client:
            gr = client.get(
                f"/api/admin/eval/runs/{rid}",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert gr.status_code == 200
        assert gr.json()["status"] == "pending"
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())


def test_run_evaluation_job_with_mocks() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    async def _run() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with SessionLocal() as s:
            s.add(
                User(
                    username="x",
                    password_hash=hash_password("pw12345678"),
                    display_name="X",
                    role="admin",
                )
            )
            s.add(RagConfig(name="r", variant_type="naive_hybrid", config={}, is_active=True))
            s.add(Story(title="St", description=None, status="ready"))
            await s.flush()
            s.add(
                StoryVersion(
                    story_id=1,
                    version_number=1,
                    is_active=True,
                    is_backup=False,
                    is_archived=False,
                )
            )
            await s.flush()
            s.add(
                EvalCase(
                    story_version_id=1,
                    case_type="fact_qa",
                    question="测试问题",
                    evidence_spans=[],
                    rubric="测试",
                )
            )
            s.add(
                EvalRun(
                    rag_config_id=1,
                    story_version_id=1,
                    status="pending",
                    total_cases=0,
                )
            )
            await s.commit()

        from app.core import database as dbmod

        orig = dbmod.async_session_factory
        dbmod.async_session_factory = SessionLocal
        try:
            with (
                patch(
                    "app.services.eval.dispatch_retrieve",
                    new_callable=AsyncMock,
                    return_value=RetrievalResult(chunks=[], structured=[], variant_type="naive_hybrid"),
                ),
                patch(
                    "app.services.eval.deepseek_chat",
                    new_callable=AsyncMock,
                    side_effect=[
                        "模型回答示例",
                        '{"faithfulness_score":0.8,"story_quality_score":0.7,"choices_grounding_score":null,"judge_reasoning":"ok"}',
                    ],
                ),
            ):
                await run_evaluation_job(1, [1])
        finally:
            dbmod.async_session_factory = orig

        async with SessionLocal() as s2:
            run = await s2.get(EvalRun, 1)
            assert run is not None
            assert run.status == "completed"
            res = await s2.execute(select(EvalResult).where(EvalResult.eval_run_id == 1))
            rows = list(res.scalars().all())
            assert len(rows) == 1
            assert rows[0].faithfulness_score == 0.8
            assert rows[0].story_quality_score == 0.7
            assert rows[0].choices_grounding_score is None
            assert run.avg_choices_grounding is None

    try:
        asyncio.run(_run())
    finally:
        asyncio.run(engine.dispose())


def test_run_evaluation_job_session_turn_with_choices_grounding() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    async def _run() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with SessionLocal() as s:
            s.add(
                User(
                    username="st",
                    password_hash=hash_password("pw12345678"),
                    display_name="S",
                    role="admin",
                )
            )
            s.add(RagConfig(name="r3", variant_type="naive_hybrid", config={}, is_active=True))
            s.add(Story(title="St3", description=None, status="ready"))
            await s.flush()
            s.add(
                StoryVersion(
                    story_id=1,
                    version_number=1,
                    is_active=True,
                    is_backup=False,
                    is_archived=False,
                )
            )
            await s.flush()
            s.add(
                EvalCase(
                    story_version_id=1,
                    case_type=SESSION_TURN,
                    question="玩家说了什么",
                    evidence_spans=[
                        {"kind": "gm_output", "text": "GM 回复正文"},
                        {"kind": "session_choices", "items": ["向左", "向右"]},
                    ],
                    rubric="会话回放",
                )
            )
            s.add(
                EvalRun(
                    rag_config_id=1,
                    story_version_id=1,
                    status="pending",
                    total_cases=0,
                )
            )
            await s.commit()

        from app.core import database as dbmod

        orig = dbmod.async_session_factory
        dbmod.async_session_factory = SessionLocal
        judge_json = (
            '{"faithfulness_score":0.55,"story_quality_score":0.6,'
            '"choices_grounding_score":0.85,"judge_reasoning":"选项可支持"}'
        )
        try:
            with (
                patch(
                    "app.services.eval.dispatch_retrieve",
                    new_callable=AsyncMock,
                    return_value=RetrievalResult(chunks=[], structured=[], variant_type="naive_hybrid"),
                ),
                patch(
                    "app.services.eval.deepseek_chat",
                    new_callable=AsyncMock,
                    side_effect=[judge_json],
                ),
            ):
                await run_evaluation_job(1, [1])
        finally:
            dbmod.async_session_factory = orig

        async with SessionLocal() as s2:
            run = await s2.get(EvalRun, 1)
            assert run is not None
            assert run.status == "completed"
            res = await s2.execute(select(EvalResult).where(EvalResult.eval_run_id == 1))
            rows = list(res.scalars().all())
            assert len(rows) == 1
            assert rows[0].choices_grounding_score == 0.85
            assert run.avg_choices_grounding == 0.85

    try:
        asyncio.run(_run())
    finally:
        asyncio.run(engine.dispose())


def test_sample_sessions_requires_pairs() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    async def init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with SessionLocal() as s:
            s.add(
                User(
                    username="adm2",
                    password_hash=hash_password("pw12345678"),
                    display_name="A",
                    role="admin",
                )
            )
            s.add(RagConfig(name="r2", variant_type="naive_hybrid", config={}, is_active=True))
            s.add(Story(title="St2", description=None, status="ready"))
            await s.flush()
            s.add(
                StoryVersion(
                    story_id=1,
                    version_number=1,
                    is_active=True,
                    is_backup=False,
                    is_archived=False,
                )
            )
            await s.flush()
            s.add(
                NarrativeSession(
                    user_id=1,
                    story_id=1,
                    story_version_id=1,
                    rag_config_id=1,
                    mode="strict",
                    opening_goal="g",
                    status="active",
                    turn_count=1,
                )
            )
            await s.flush()
            s.add(
                SessionMessage(
                    session_id=1,
                    turn_number=1,
                    role="assistant",
                    content="仅有 GM",
                    metadata_={},
                )
            )
            await s.commit()
            tok = create_access_token({"sub": "1"})
            return SessionLocal, tok

    SessionLocal, token = asyncio.run(init())

    async def override_get_db():
        async with SessionLocal() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("app.api.admin.eval.run_evaluation_job", new=lambda *_a, **_k: None):
            with TestClient(app) as client:
                r = client.post(
                    "/api/admin/eval/sample-sessions",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"session_id": 1, "max_turns": 5},
                )
        assert r.status_code == 400
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())
