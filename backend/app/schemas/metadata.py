from pydantic import BaseModel, Field


class EntityCreate(BaseModel):
    name: str = Field(..., max_length=100)
    canonical_name: str = Field(..., max_length=100)
    entity_type: str = Field(..., max_length=30)
    description: str | None = None
    aliases: list[str] = Field(default_factory=list)


class EntityUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    canonical_name: str | None = Field(None, max_length=100)
    entity_type: str | None = Field(None, max_length=30)
    description: str | None = None
    aliases: list[str] | None = None


class RelationshipCreate(BaseModel):
    entity_a_id: int
    entity_b_id: int
    relationship_type: str = Field(..., max_length=50)
    description: str | None = None
    confidence: float = 1.0


class RelationshipUpdate(BaseModel):
    relationship_type: str | None = Field(None, max_length=50)
    description: str | None = None
    confidence: float | None = None


class TimelineCreate(BaseModel):
    event_description: str
    chapter_id: int | None = None
    scene_id: int | None = None
    order_index: int
    participants: list[int] = Field(default_factory=list)


class TimelineUpdate(BaseModel):
    event_description: str | None = None
    chapter_id: int | None = None
    scene_id: int | None = None
    order_index: int | None = None
    participants: list[int] | None = None


class ChapterUpdate(BaseModel):
    title: str | None = Field(None, max_length=200)
    summary: str | None = None


class SceneUpdate(BaseModel):
    summary: str | None = None
    raw_text: str | None = None


class RiskSegmentUpdate(BaseModel):
    rewritten_text: str
