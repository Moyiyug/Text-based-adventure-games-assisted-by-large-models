"""检索器抽象与统一结果结构。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class StructuredHit:
    """结构化命中（实体/关系/时间线）。"""

    kind: str  # entity | relationship | timeline
    payload: dict[str, Any]


@dataclass(frozen=True)
class TimelineRetrievalBias:
    """
    回合检索时间线偏置：对命中当前/邻接时间线事件关联 chapter/scene 的 chunk 加分。
    naive_hybrid 已实现；parent_child / structured 首版忽略。
    """

    primary_chapter_id: int | None = None
    primary_scene_id: int | None = None
    neighbor_chapter_ids: frozenset[int] = field(default_factory=frozenset)
    neighbor_scene_ids: frozenset[int] = field(default_factory=frozenset)


@dataclass
class RetrievedChunk:
    text_chunk_id: int
    content: str
    score: float
    source: str  # bm25 | vector | fusion | parent_child | text
    chapter_id: int | None = None
    scene_id: int | None = None
    parent_context: str | None = None


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk] = field(default_factory=list)
    structured: list[StructuredHit] = field(default_factory=list)
    variant_type: str = ""


class BaseRetriever(ABC):
    @abstractmethod
    async def retrieve(
        self,
        db: AsyncSession,
        query: str,
        story_version_id: int,
        config: dict,
        *,
        timeline_bias: TimelineRetrievalBias | None = None,
    ) -> RetrievalResult:
        pass
