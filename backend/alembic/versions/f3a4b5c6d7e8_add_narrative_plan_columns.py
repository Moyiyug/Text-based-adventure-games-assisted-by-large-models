"""sessions narrative_status and narrative_plan (Phase 11)

Revision ID: f3a4b5c6d7e8
Revises: e1f2a3b4c5d6
Create Date: 2026-03-25

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f3a4b5c6d7e8"
down_revision: Union[str, Sequence[str], None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column(
            "narrative_status",
            sa.String(length=20),
            nullable=False,
            server_default="opening_pending",
        ),
    )
    op.add_column(
        "sessions",
        sa.Column(
            "narrative_plan",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.alter_column("sessions", "narrative_status", server_default=None)
    op.alter_column("sessions", "narrative_plan", server_default=None)


def downgrade() -> None:
    op.drop_column("sessions", "narrative_plan")
    op.drop_column("sessions", "narrative_status")
