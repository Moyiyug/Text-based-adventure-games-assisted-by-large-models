"""用户画像 API 与角色卡导入。参照 BACKEND_STRUCTURE §1.4、§2.2。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GlobalProfileResponse(BaseModel):
    preferences: dict[str, Any] = Field(default_factory=dict)


class StoryProfileResponse(BaseModel):
    story_id: int
    overrides: dict[str, Any] = Field(default_factory=dict)


class ProfileImportResponse(BaseModel):
    """导入成功后返回当前全局偏好与（若适用）该作品覆写。"""

    scope: Literal["global", "story"]
    preferences: dict[str, Any] = Field(default_factory=dict)
    story_id: int | None = None
    overrides: dict[str, Any] = Field(default_factory=dict)


class ProfileCardImport(BaseModel):
    """上传 JSON 文件解析后的结构。"""

    model_config = ConfigDict(extra="ignore")

    schema_version: str | None = None
    scope: Literal["global", "story"]
    story_id: int | None = None
    user_id: int | None = Field(
        default=None,
        description="若填写须与当前登录用户一致，否则 400",
    )
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def story_requires_story_id(self) -> ProfileCardImport:
        if self.scope == "story" and self.story_id is None:
            raise ValueError("scope 为 story 时必须提供 story_id")
        return self
