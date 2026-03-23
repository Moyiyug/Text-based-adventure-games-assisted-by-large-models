"""会话 API 的 Pydantic 模型。参照 BACKEND_STRUCTURE §2.4。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SessionCreate(BaseModel):
    story_id: int
    mode: str = Field(..., pattern="^(strict|creative)$")
    opening_goal: str = Field(..., min_length=1, max_length=8000)
    rag_config_id: int | None = None
    style_config: dict[str, Any] | None = None


class SessionMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    turn_number: int
    role: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce_orm(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        if hasattr(data, "metadata_"):
            return {
                "id": data.id,
                "turn_number": data.turn_number,
                "role": data.role,
                "content": data.content,
                "metadata": data.metadata_ if data.metadata_ is not None else {},
            }
        return data


class SessionStateSnapshot(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    turn_number: int
    state: dict[str, Any]
    created_at: datetime | None = None


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    story_id: int
    story_version_id: int
    rag_config_id: int
    mode: str
    opening_goal: str
    style_config: dict[str, Any]
    status: str
    turn_count: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
    latest_state: SessionStateSnapshot | None = None


class SessionListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    story_id: int
    story_version_id: int
    rag_config_id: int
    mode: str
    status: str
    turn_count: int
    opening_goal: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FeedbackCreate(BaseModel):
    message_id: int
    feedback_type: str = Field(..., min_length=1, max_length=30)
    content: str | None = Field(None, max_length=4000)


class UserFeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    message_id: int
    feedback_type: str
    content: str | None
    reviewed: bool
    created_at: datetime | None = None


class SessionCreateResponse(SessionResponse):
    opening_message: SessionMessageOut | None = None


class SessionMessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=12000)


class OpeningGenerationResponse(BaseModel):
    narrative: str
    choices: list[str]
    state_update: dict[str, Any]
    parse_error: str | None = None
