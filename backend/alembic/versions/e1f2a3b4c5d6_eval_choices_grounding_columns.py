"""eval choices_grounding_score and avg_choices_grounding

Revision ID: e1f2a3b4c5d6
Revises: 0a67355a0ae2
Create Date: 2026-03-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "0a67355a0ae2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "eval_results",
        sa.Column("choices_grounding_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "eval_runs",
        sa.Column("avg_choices_grounding", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("eval_runs", "avg_choices_grounding")
    op.drop_column("eval_results", "choices_grounding_score")
