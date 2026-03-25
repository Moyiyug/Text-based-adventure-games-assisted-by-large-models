"""评测 API 请求/响应。参照 BACKEND_STRUCTURE §2.9。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EvalRunCreate(BaseModel):
    rag_config_id: int
    story_version_id: int
    generate_cases: bool = False
    case_ids: list[int] | None = None


class EvalSampleSessionsRequest(BaseModel):
    session_id: int
    max_turns: int = Field(default=8, ge=1, le=50)


class EvalRunOut(BaseModel):
    id: int
    rag_config_id: int
    story_version_id: int
    status: str
    total_cases: int
    avg_faithfulness: float | None
    avg_story_quality: float | None
    avg_choices_grounding: float | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class EvalRunsListResponse(BaseModel):
    items: list[EvalRunOut]
    total: int


class EvalCaseBrief(BaseModel):
    id: int
    story_version_id: int
    case_type: str
    question: str
    evidence_spans: list[Any]
    rubric: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class EvalResultOut(BaseModel):
    id: int
    eval_run_id: int
    eval_case_id: int
    generated_answer: str
    retrieved_context: list[Any]
    structured_facts_used: list[Any]
    faithfulness_score: float | None
    story_quality_score: float | None
    choices_grounding_score: float | None
    judge_reasoning: str | None
    created_at: datetime
    case: EvalCaseBrief | None = None

    model_config = {"from_attributes": True}


class EvalRunTriggerResponse(BaseModel):
    run_id: int
    message: str = "评测任务已排队"


class EvalResultsListResponse(BaseModel):
    items: list[EvalResultOut]
    total: int
