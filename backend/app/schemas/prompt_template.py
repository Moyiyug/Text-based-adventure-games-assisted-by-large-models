"""管理员提示词 API 的 Pydantic 模型。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PromptTemplateAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    layer: str
    template_text: str
    applicable_mode: str
    is_active: bool
    version: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PromptTemplateLayerGroup(BaseModel):
    """同一 layer 下按 applicable_mode 分桶。"""

    layer: str
    by_mode: dict[str, list[PromptTemplateAdminOut]] = Field(
        default_factory=dict,
        description="键为 strict / creative / all 等",
    )


class PromptTemplatesGroupedResponse(BaseModel):
    layers: list[PromptTemplateLayerGroup]


class PromptTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    layer: str = Field(..., min_length=1, max_length=20)
    template_text: str = Field(..., min_length=1)
    applicable_mode: str = Field(default="all", max_length=10)
    is_active: bool = True


class PromptTemplateUpdate(BaseModel):
    name: str | None = Field(None, max_length=50)
    template_text: str | None = None
    applicable_mode: str | None = Field(None, max_length=10)
    is_active: bool | None = None
    bump_version: bool = False


class PromptTemplatePutResponse(PromptTemplateAdminOut):
    pass
