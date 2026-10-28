"""Add decision actor and timestamp to response_actions.

Revision ID: 0003_action_decisions
Revises: 0002_investigation_id
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_action_decisions"
down_revision: str | None = "0002_investigation_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "response_actions",
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "response_actions",
        sa.Column("actor", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("response_actions", "actor")
    op.drop_column("response_actions", "decided_at")
