from pydantic import BaseModel, Field


class UpdateSettingsRequest(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=30)
    bio: str | None = Field(None, max_length=500)
