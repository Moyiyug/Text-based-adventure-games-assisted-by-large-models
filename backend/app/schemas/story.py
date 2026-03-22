from datetime import datetime

from pydantic import BaseModel, Field


class StoryUploadResponse(BaseModel):
    id: int
    story_version_id: int | None = None
    title: str
    description: str | None
    source_file_path: str | None
    status: str


class StoryUpdateRequest(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=5000)


class AdminStoryListItem(BaseModel):
    id: int
    title: str
    description: str | None
    status: str
    source_file_path: str | None
    version_count: int
    active_version_id: int | None
    last_ingested_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": False}


class IngestionJobResponse(BaseModel):
    id: int
    story_id: int
    story_version_id: int | None
    status: str
    progress: float
    steps_completed: list
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class IngestionWarningItem(BaseModel):
    id: int
    job_id: int
    warning_type: str
    message: str
    chapter_id: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class IngestTriggerResponse(BaseModel):
    job_id: int
    message: str = "入库任务已提交"


class RollbackRequest(BaseModel):
    target_version_id: int | None = Field(
        None,
        description="要恢复为当前生效的版本 id；不传则使用当前备份版本",
    )


class PlayerStoryListItem(BaseModel):
    id: int
    title: str
    description: str | None
    created_at: datetime


class PlayerChapterOutline(BaseModel):
    id: int
    chapter_number: int
    title: str | None
    summary: str | None


class PlayerStoryDetail(BaseModel):
    id: int
    title: str
    description: str | None
    chapters: list[PlayerChapterOutline]
