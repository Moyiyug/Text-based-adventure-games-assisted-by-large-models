"""管理员会话查看 API 的 Pydantic 模型。参照 BACKEND_STRUCTURE §2.10。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.session import SessionMessageOut


class AdminSessionListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    username: str = ""
    story_id: int
    story_title: str = ""
    story_version_id: int
    rag_config_id: int
    mode: str
    status: str
    turn_count: int
    opening_goal: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TranscriptSessionMeta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    story_id: int
    story_version_id: int
    rag_config_id: int
    mode: str
    status: str
    turn_count: int
    opening_goal: str


class TranscriptResponse(BaseModel):
    session: TranscriptSessionMeta
    messages: list[SessionMessageOut]


class AdminUserFeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    message_id: int
    feedback_type: str
    content: str | None
    reviewed: bool
    created_at: datetime | None = None


class FeedbackListResponse(BaseModel):
    items: list[AdminUserFeedbackOut]


class AdminSessionsListResponse(BaseModel):
    items: list[AdminSessionListItem]
    total: int
