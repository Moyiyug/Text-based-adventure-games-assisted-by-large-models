"""RAG 配置 API 模型。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RagConfigResponse(BaseModel):
    id: int
    name: str
    variant_type: str
    config: dict[str, Any]
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class RagConfigUpdate(BaseModel):
    name: str | None = Field(None, max_length=50)
    config: dict[str, Any] | None = None


class DebugRetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    rag_config_id: int | None = None
    story_version_id: int | None = None
