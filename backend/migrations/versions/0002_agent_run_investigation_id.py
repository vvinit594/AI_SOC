"""Add investigation_id to agent_runs for Phase 6 workflow grouping.

Revision ID: 0002_investigation_id
Revises: 0001_initial
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_investigation_id"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_runs", sa.Column("investigation_id", sa.Uuid(), nullable=True))
    op.execute(
        sa.text("UPDATE agent_runs SET investigation_id = id WHERE investigation_id IS NULL")
    )
    op.alter_column("agent_runs", "investigation_id", existing_type=sa.Uuid(), nullable=False)
    op.create_index("ix_agent_runs_investigation_id", "agent_runs", ["investigation_id"])
    op.create_unique_constraint(
        "uq_agent_runs_investigation_agent",
        "agent_runs",
        ["investigation_id", "agent_name"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_agent_runs_investigation_agent", "agent_runs", type_="unique")
    op.drop_index("ix_agent_runs_investigation_id", table_name="agent_runs")
    op.drop_column("agent_runs", "investigation_id")
