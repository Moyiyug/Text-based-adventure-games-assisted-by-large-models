import re
from datetime import datetime, timezone
from pathlib import Path

import aiofiles
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.ingestion import IngestionJob, IngestionWarning
from app.models.story import Story, StoryVersion
from app.models.user import User
from app.schemas.rag_config import DebugRetrieveRequest
from app.schemas.story import (
    AdminStoryListItem,
    IngestionJobResponse,
    IngestionWarningItem,
    IngestTriggerResponse,
    RollbackRequest,
    StoryUpdateRequest,
    StoryUploadResponse,
)
from app.services.ingestion.pipeline import run_ingestion_background
from app.services.rag.context import assemble_context
from app.services.rag.dispatcher import dispatch_retrieve

router = APIRouter()


def _safe_filename(name: str) -> str:
    base = Path(name).name
    base = re.sub(r"[^\w.\-一-龥\u3000-\u303f\uff00-\uffef]", "_", base)
    return base[:200] if base else "upload.bin"


async def _get_story_or_404(db: AsyncSession, story_id: int, *, allow_deleted: bool = False) -> Story:
    story = await db.get(Story, story_id)
    if story is None or (not allow_deleted and story.deleted_at is not None):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作品不存在")
    return story


@router.get("", response_model=list[AdminStoryListItem])
async def list_stories(
    include_deleted: bool = False,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(Story)
    if not include_deleted:
        q = q.where(Story.deleted_at.is_(None))
    q = q.order_by(Story.id.desc())
    res = await db.execute(q)
    stories = list(res.scalars().all())

    out: list[AdminStoryListItem] = []
    for s in stories:
        vres = await db.execute(select(StoryVersion).where(StoryVersion.story_id == s.id))
        versions = list(vres.scalars().all())
        active = next((v for v in versions if v.is_active), None)
        last_ing = await db.scalar(
            select(func.max(IngestionJob.completed_at)).where(
                IngestionJob.story_id == s.id,
                IngestionJob.status == "completed",
            )
        )
        out.append(
            AdminStoryListItem(
                id=s.id,
                title=s.title,
                description=s.description,
                status=s.status,
                source_file_path=s.source_file_path,
                version_count=len(versions),
                active_version_id=active.id if active else None,
                last_ingested_at=last_ing,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
        )
    return out


@router.post("/upload", response_model=StoryUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_story(
    file: UploadFile = File(...),
    title: str = Form(..., min_length=1, max_length=200),
    description: str | None = Form(None, max_length=5000),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    story = Story(
        title=title.strip(),
        description=description.strip() if description else None,
        status="pending",
    )
    db.add(story)
    await db.flush()

    upload_root = settings.upload_dir_path
    story_dir = upload_root / str(story.id)
    story_dir.mkdir(parents=True, exist_ok=True)

    fname = _safe_filename(file.filename or "upload.txt")
    dest = story_dir / fname

    try:
        async with aiofiles.open(dest, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                await out.write(chunk)
    except OSError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件保存失败: {e}",
        ) from e

    rel_path = f"{story.id}/{fname}"
    story.source_file_path = rel_path

    result = await db.execute(select(StoryVersion).where(StoryVersion.story_id == story.id))
    existing = result.scalars().all()
    next_ver = max((v.version_number for v in existing), default=0) + 1

    for v in existing:
        v.is_active = False

    version = StoryVersion(
        story_id=story.id,
        version_number=next_ver,
        is_active=True,
        is_backup=False,
    )
    db.add(version)
    await db.flush()
    await db.refresh(story)
    await db.refresh(version)

    return StoryUploadResponse(
        id=story.id,
        story_version_id=version.id,
        title=story.title,
        description=story.description,
        source_file_path=story.source_file_path,
        status=story.status,
    )


@router.put("/{story_id}", response_model=StoryUploadResponse)
async def update_story(
    story_id: int,
    body: StoryUpdateRequest,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    story = await _get_story_or_404(db, story_id)
    if body.title is not None:
        story.title = body.title.strip()
    if body.description is not None:
        story.description = body.description.strip() if body.description else None
    await db.flush()
    await db.refresh(story)
    vres = await db.execute(
        select(StoryVersion).where(StoryVersion.story_id == story.id, StoryVersion.is_active.is_(True))
    )
    av = vres.scalar_one_or_none()
    return StoryUploadResponse(
        id=story.id,
        story_version_id=av.id if av else 0,
        title=story.title,
        description=story.description,
        source_file_path=story.source_file_path,
        status=story.status,
    )


@router.delete("/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
async def soft_delete_story(
    story_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    story = await _get_story_or_404(db, story_id)
    story.deleted_at = datetime.now(timezone.utc)
    await db.flush()


@router.post("/{story_id}/ingest", response_model=IngestTriggerResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_ingest(
    story_id: int,
    background_tasks: BackgroundTasks,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    story = await _get_story_or_404(db, story_id)
    if story.status == "ingesting":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该作品正在入库中",
        )
    job = IngestionJob(story_id=story.id, story_version_id=None, status="pending")
    db.add(job)
    await db.flush()
    await db.refresh(job)
    jid = job.id
    await db.commit()
    background_tasks.add_task(run_ingestion_background, story_id, jid)
    return IngestTriggerResponse(job_id=jid)


@router.get("/{story_id}/ingestion-jobs", response_model=list[IngestionJobResponse])
async def list_ingestion_jobs(
    story_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _get_story_or_404(db, story_id, allow_deleted=True)
    res = await db.execute(
        select(IngestionJob)
        .where(IngestionJob.story_id == story_id)
        .order_by(IngestionJob.created_at.desc())
    )
    return list(res.scalars().all())


@router.get(
    "/{story_id}/ingestion-jobs/{job_id}/warnings",
    response_model=list[IngestionWarningItem],
)
async def list_ingestion_job_warnings(
    story_id: int,
    job_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _get_story_or_404(db, story_id, allow_deleted=True)
    job = await db.get(IngestionJob, job_id)
    if job is None or job.story_id != story_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    wres = await db.execute(
        select(IngestionWarning)
        .where(IngestionWarning.job_id == job_id)
        .order_by(IngestionWarning.created_at.asc())
    )
    return list(wres.scalars().all())


@router.post("/{story_id}/rollback", status_code=status.HTTP_200_OK)
async def rollback_story_version(
    story_id: int,
    body: RollbackRequest,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    story = await _get_story_or_404(db, story_id)
    if story.status == "ingesting":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="入库进行中，无法回滚",
        )

    vres = await db.execute(select(StoryVersion).where(StoryVersion.story_id == story_id))
    versions = list(vres.scalars().all())
    if not versions:
        raise HTTPException(status_code=400, detail="无版本记录")

    prev_active = next((v for v in versions if v.is_active), None)
    if not prev_active:
        raise HTTPException(status_code=400, detail="无当前生效版本")

    prev_backup = next((v for v in versions if v.is_backup), None)

    if body.target_version_id is None:
        target = prev_backup
        if not target:
            raise HTTPException(status_code=400, detail="无备份版本可回滚")
    else:
        target = await db.get(StoryVersion, body.target_version_id)
        if target is None or target.story_id != story_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="目标版本不存在")

    if target.id == prev_active.id:
        raise HTTPException(status_code=400, detail="目标已是当前生效版本")

    for v in versions:
        v.is_active = False
        v.is_backup = False

    target.is_active = True
    target.is_archived = False
    if prev_active.id != target.id:
        prev_active.is_backup = True

    if prev_backup and prev_backup.id != target.id:
        prev_backup.is_archived = True

    cfg = dict(target.ingestion_config or {})
    cfg["vectors_dirty"] = True
    target.ingestion_config = cfg

    await db.flush()
    return {
        "ok": True,
        "active_version_id": target.id,
        "backup_version_id": prev_active.id if prev_active.id != target.id else None,
    }


@router.post("/{story_id}/debug-retrieve")
async def debug_retrieve(
    story_id: int,
    body: DebugRetrieveRequest,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """管理端调试检索（Phase 3 验收）；不经过会话表。"""
    await _get_story_or_404(db, story_id)
    if body.story_version_id is not None:
        sv = await db.get(StoryVersion, body.story_version_id)
        if sv is None or sv.story_id != story_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="版本不属于该作品")
        sv_id = body.story_version_id
    else:
        avres = await db.execute(
            select(StoryVersion).where(
                StoryVersion.story_id == story_id,
                StoryVersion.is_active.is_(True),
            )
        )
        av = avres.scalar_one_or_none()
        if av is None:
            raise HTTPException(status_code=400, detail="无当前生效版本")
        sv_id = av.id
    try:
        result = await dispatch_retrieve(
            db,
            body.query.strip(),
            sv_id,
            rag_config_id=body.rag_config_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    preview = assemble_context(result, token_budget=8000)
    return {
        "story_version_id": sv_id,
        "variant_type": result.variant_type,
        "structured": [{"kind": s.kind, "payload": s.payload} for s in result.structured],
        "chunks": [
            {
                "text_chunk_id": c.text_chunk_id,
                "score": c.score,
                "source": c.source,
                "chapter_id": c.chapter_id,
                "scene_id": c.scene_id,
                "parent_context": c.parent_context,
                "content_preview": (c.content[:500] + "…") if len(c.content) > 500 else c.content,
            }
            for c in result.chunks
        ],
        "context_preview": preview[:12000],
    }
