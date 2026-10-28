"""Drop unique (resource, event_type) on audit_logs.

Revision ID: 0005_drop_audit_event_uniqueness
Revises: 0004_audit_logs
Create Date: 2026-10-28

Repeated event types for one resource are allowed. Approve/reject idempotency
is enforced by the response-action state machine, not this table.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005_drop_audit_event_uniqueness"
down_revision: str | None = "0004_audit_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_audit_logs_resource_event", "audit_logs", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_audit_logs_resource_event",
        "audit_logs",
        ["resource_type", "resource_id", "event_type"],
    )
