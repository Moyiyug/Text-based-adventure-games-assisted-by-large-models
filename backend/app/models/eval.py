"""评测运行、用例与结果。参照 BACKEND_STRUCTURE §1.7。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rag_config_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("rag_configs.id", ondelete="RESTRICT"), nullable=False
    )
    story_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("story_versions.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(15), nullable=False, default="pending")
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_faithfulness: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_story_quality: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    results: Mapped[list["EvalResult"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )


class EvalCase(Base):
    __tablename__ = "eval_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    story_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("story_versions.id", ondelete="RESTRICT"), nullable=False
    )
    case_type: Mapped[str] = mapped_column(String(30), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_spans: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    rubric: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    results: Mapped[list["EvalResult"]] = relationship(back_populates="case")


class EvalResult(Base):
    __tablename__ = "eval_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    eval_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False
    )
    eval_case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("eval_cases.id", ondelete="RESTRICT"), nullable=False
    )

    run: Mapped["EvalRun"] = relationship(back_populates="results")
    case: Mapped["EvalCase"] = relationship(back_populates="results")
    generated_answer: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_context: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    structured_facts_used: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    faithfulness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    story_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    judge_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
