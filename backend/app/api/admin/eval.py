"""管理员评测 API。参照 BACKEND_STRUCTURE §2.9。"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.eval import EvalCase, EvalResult, EvalRun
from app.models.rag_config import RagConfig
from app.models.story import StoryVersion
from app.models.user import User
from app.schemas.eval import (
    EvalCaseBrief,
    EvalResultOut,
    EvalResultsListResponse,
    EvalRunCreate,
    EvalRunOut,
    EvalRunsListResponse,
    EvalRunTriggerResponse,
    EvalSampleSessionsRequest,
)
from app.services.eval import (
    create_sample_session_eval_run,
    generate_eval_cases,
    run_evaluation_job,
)

router = APIRouter(prefix="/eval", tags=["admin-eval"])

_DEFAULT_LIMIT = 50
_MAX_LIMIT = 200


@router.post("/runs", response_model=EvalRunTriggerResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_eval_run(
    body: EvalRunCreate,
    background_tasks: BackgroundTasks,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    rc = await db.get(RagConfig, body.rag_config_id)
    if rc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RAG 配置不存在")
    sv = await db.get(StoryVersion, body.story_version_id)
    if sv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作品版本不存在")

    case_ids_for_job: list[int] | None = None
    if body.case_ids is not None:
        if not body.case_ids:
            case_ids_for_job = []
        else:
            cres = await db.execute(
                select(EvalCase).where(
                    EvalCase.id.in_(body.case_ids),
                    EvalCase.story_version_id == body.story_version_id,
                )
            )
            found = {c.id for c in cres.scalars().all()}
            missing = set(body.case_ids) - found
            if missing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"用例 id 不属于该版本或不存在: {sorted(missing)}",
                )
            case_ids_for_job = list(body.case_ids)
    elif body.generate_cases:
        created = await generate_eval_cases(db, body.story_version_id)
        await db.flush()
        case_ids_for_job = [c.id for c in created]

    run = EvalRun(
        rag_config_id=body.rag_config_id,
        story_version_id=body.story_version_id,
        status="pending",
        total_cases=0,
    )
    db.add(run)
    await db.flush()
    await db.refresh(run)
    rid = run.id
    await db.commit()
    background_tasks.add_task(run_evaluation_job, rid, case_ids_for_job)
    return EvalRunTriggerResponse(run_id=rid)


@router.get("/runs", response_model=EvalRunsListResponse)
async def list_eval_runs(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    story_version_id: int | None = None,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    q = select(EvalRun)
    if story_version_id is not None:
        q = q.where(EvalRun.story_version_id == story_version_id)
    if status_filter:
        q = q.where(EvalRun.status == status_filter.strip())
    count_base = select(func.count()).select_from(EvalRun)
    if story_version_id is not None:
        count_base = count_base.where(EvalRun.story_version_id == story_version_id)
    if status_filter:
        count_base = count_base.where(EvalRun.status == status_filter.strip())
    total = int((await db.execute(count_base)).scalar_one())
    q = q.order_by(EvalRun.id.desc()).offset(offset).limit(limit)
    res = await db.execute(q)
    rows = list(res.scalars().all())
    return EvalRunsListResponse(
        items=[EvalRunOut.model_validate(r) for r in rows],
        total=total,
    )


@router.get("/runs/{run_id}", response_model=EvalRunOut)
async def get_eval_run(
    run_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    run = await db.get(EvalRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评测运行不存在")
    return EvalRunOut.model_validate(run)


@router.get("/runs/{run_id}/results", response_model=EvalResultsListResponse)
async def list_eval_results(
    run_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    run = await db.get(EvalRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评测运行不存在")

    res = await db.execute(
        select(EvalResult)
        .where(EvalResult.eval_run_id == run_id)
        .order_by(EvalResult.id.asc())
    )
    rows = list(res.scalars().all())
    case_ids = list({r.eval_case_id for r in rows})
    cases_map: dict[int, EvalCase] = {}
    if case_ids:
        cres = await db.execute(select(EvalCase).where(EvalCase.id.in_(case_ids)))
        cases_map = {c.id: c for c in cres.scalars().all()}
    items: list[EvalResultOut] = []
    for r in rows:
        ec = cases_map.get(r.eval_case_id)
        case_brief = EvalCaseBrief.model_validate(ec) if ec else None
        items.append(
            EvalResultOut(
                id=r.id,
                eval_run_id=r.eval_run_id,
                eval_case_id=r.eval_case_id,
                generated_answer=r.generated_answer,
                retrieved_context=list(r.retrieved_context or []),
                structured_facts_used=list(r.structured_facts_used or []),
                faithfulness_score=r.faithfulness_score,
                story_quality_score=r.story_quality_score,
                choices_grounding_score=r.choices_grounding_score,
                judge_reasoning=r.judge_reasoning,
                created_at=r.created_at,
                case=case_brief,
            )
        )
    return EvalResultsListResponse(items=items, total=len(items))


@router.post("/sample-sessions", response_model=EvalRunTriggerResponse, status_code=status.HTTP_202_ACCEPTED)
async def sample_sessions_eval(
    body: EvalSampleSessionsRequest,
    background_tasks: BackgroundTasks,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        rid, case_ids = await create_sample_session_eval_run(
            db, body.session_id, body.max_turns
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    background_tasks.add_task(run_evaluation_job, rid, case_ids)
    return EvalRunTriggerResponse(run_id=rid, message="会话抽样评测已排队")
