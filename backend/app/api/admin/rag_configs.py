"""管理员 RAG 方案配置。参照 BACKEND_STRUCTURE §2.8。"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.rag_config import RagConfig
from app.models.user import User
from app.schemas.rag_config import RagConfigResponse, RagConfigUpdate

router = APIRouter(prefix="/rag-configs", tags=["admin-rag-configs"])


@router.get("", response_model=list[RagConfigResponse])
async def list_rag_configs(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(RagConfig).order_by(RagConfig.id))
    rows = list(res.scalars().all())
    return [RagConfigResponse.model_validate(r) for r in rows]


@router.put("/{config_id}", response_model=RagConfigResponse)
async def update_rag_config(
    config_id: int,
    body: RagConfigUpdate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    rc = await db.get(RagConfig, config_id)
    if rc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置不存在")
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        return RagConfigResponse.model_validate(rc)
    if "name" in patch and patch["name"] is not None:
        rc.name = patch["name"].strip()
    if "config" in patch and patch["config"] is not None:
        rc.config = dict(patch["config"])
    rc.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(rc)
    return RagConfigResponse.model_validate(rc)


@router.post("/{config_id}/activate", response_model=RagConfigResponse)
async def activate_rag_config(
    config_id: int,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    rc = await db.get(RagConfig, config_id)
    if rc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置不存在")
    now = datetime.now(timezone.utc)
    await db.execute(update(RagConfig).values(is_active=False))
    rc.is_active = True
    rc.updated_at = now
    await db.flush()
    await db.refresh(rc)
    return RagConfigResponse.model_validate(rc)
