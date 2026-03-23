"""管理员提示词模板。参照 BACKEND_STRUCTURE §2.7。"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.prompt_template import PromptTemplate
from app.models.user import User
from app.schemas.prompt_template import (
    PromptTemplateAdminOut,
    PromptTemplateCreate,
    PromptTemplateLayerGroup,
    PromptTemplatesGroupedResponse,
    PromptTemplatePutResponse,
    PromptTemplateUpdate,
)

router = APIRouter(prefix="/prompts", tags=["admin-prompts"])


def _group_templates(rows: list[PromptTemplate]) -> PromptTemplatesGroupedResponse:
    by_layer: dict[str, dict[str, list[PromptTemplate]]] = {}
    for r in rows:
        by_layer.setdefault(r.layer, {}).setdefault(r.applicable_mode, []).append(r)

    layers: list[PromptTemplateLayerGroup] = []
    for layer in sorted(by_layer.keys()):
        modes_map = by_layer[layer]
        by_mode: dict[str, list[PromptTemplateAdminOut]] = {}
        for mode_key in sorted(modes_map.keys()):
            by_mode[mode_key] = [
                PromptTemplateAdminOut.model_validate(x) for x in modes_map[mode_key]
            ]
        layers.append(PromptTemplateLayerGroup(layer=layer, by_mode=by_mode))
    return PromptTemplatesGroupedResponse(layers=layers)


@router.get("", response_model=PromptTemplatesGroupedResponse)
async def list_prompt_templates(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(PromptTemplate).order_by(
            PromptTemplate.layer,
            PromptTemplate.applicable_mode,
            PromptTemplate.id,
        )
    )
    rows = list(res.scalars().all())
    return _group_templates(rows)


@router.put("/{template_id}", response_model=PromptTemplatePutResponse)
async def update_prompt_template(
    template_id: int,
    body: PromptTemplateUpdate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    pt = await db.get(PromptTemplate, template_id)
    if pt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")
    bump = body.bump_version
    patch = body.model_dump(exclude_unset=True)
    patch.pop("bump_version", None)
    if not patch and not bump:
        return PromptTemplatePutResponse.model_validate(pt)
    if "name" in patch and patch["name"] is not None:
        pt.name = patch["name"].strip()
    if "template_text" in patch and patch["template_text"] is not None:
        pt.template_text = patch["template_text"]
    if "applicable_mode" in patch and patch["applicable_mode"] is not None:
        pt.applicable_mode = patch["applicable_mode"].strip()
    if "is_active" in patch and patch["is_active"] is not None:
        pt.is_active = patch["is_active"]
    if bump:
        pt.version = int(pt.version or 1) + 1
    pt.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(pt)
    return PromptTemplatePutResponse.model_validate(pt)


@router.post("", response_model=PromptTemplatePutResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt_template(
    body: PromptTemplateCreate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    pt = PromptTemplate(
        name=body.name.strip(),
        layer=body.layer.strip(),
        template_text=body.template_text,
        applicable_mode=body.applicable_mode.strip(),
        is_active=body.is_active,
        version=1,
    )
    db.add(pt)
    await db.commit()
    await db.refresh(pt)
    return PromptTemplatePutResponse.model_validate(pt)
