"""Add users, workspaces, sessions, and tenant workspace columns.

Revision ID: 0006_auth_workspaces
Revises: 0005_drop_audit_event_uniqueness
Create Date: 2026-11-20

Existing security_events, incidents, and audit_logs are assigned to a
system legacy workspace. That workspace has no memberships, so the first
public registrant cannot see historical rows.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_auth_workspaces"
down_revision: str | None = "0005_drop_audit_event_uniqueness"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_WORKSPACE_ID = "a15ec000-0000-4000-8000-0000000000ce"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workspaces_kind", "workspaces", ["kind"])

    op.create_table(
        "workspace_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "workspace_id",
            name="uq_workspace_memberships_user_workspace",
        ),
    )
    op.create_index(
        "ix_workspace_memberships_workspace_id",
        "workspace_memberships",
        ["workspace_id"],
    )
    op.create_index("ix_workspace_memberships_user_id", "workspace_memberships", ["user_id"])

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_sessions_token_hash", "user_sessions", ["token_hash"], unique=True)
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"])

    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_login_attempts_email_attempted_at",
        "login_attempts",
        ["email", "attempted_at"],
    )
    op.create_index(
        "ix_login_attempts_ip_attempted_at",
        "login_attempts",
        ["ip_address", "attempted_at"],
    )

    op.create_table(
        "password_recovery_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_password_recovery_tokens_token_hash",
        "password_recovery_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index("ix_password_recovery_tokens_user_id", "password_recovery_tokens", ["user_id"])

    op.execute(
        sa.text(
            "INSERT INTO workspaces (id, name, kind, created_at) "
            "VALUES (CAST(:id AS uuid), :name, :kind, CURRENT_TIMESTAMP)"
        ).bindparams(
            id=LEGACY_WORKSPACE_ID,
            name="Legacy data (unassigned)",
            kind="legacy",
        )
    )

    op.add_column("security_events", sa.Column("workspace_id", sa.Uuid(), nullable=True))
    op.add_column("incidents", sa.Column("workspace_id", sa.Uuid(), nullable=True))
    op.add_column("audit_logs", sa.Column("workspace_id", sa.Uuid(), nullable=True))

    op.execute(
        sa.text(
            "UPDATE security_events SET workspace_id = CAST(:id AS uuid) WHERE workspace_id IS NULL"
        ).bindparams(id=LEGACY_WORKSPACE_ID)
    )
    op.execute(
        sa.text(
            "UPDATE incidents SET workspace_id = CAST(:id AS uuid) WHERE workspace_id IS NULL"
        ).bindparams(id=LEGACY_WORKSPACE_ID)
    )
    op.execute(
        sa.text(
            "UPDATE audit_logs AS audit SET workspace_id = incidents.workspace_id "
            "FROM incidents WHERE audit.incident_id = incidents.id AND audit.workspace_id IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE audit_logs SET workspace_id = CAST(:id AS uuid) WHERE workspace_id IS NULL"
        ).bindparams(id=LEGACY_WORKSPACE_ID)
    )

    op.alter_column("security_events", "workspace_id", nullable=False)
    op.alter_column("incidents", "workspace_id", nullable=False)

    op.create_foreign_key(
        "fk_security_events_workspace_id",
        "security_events",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_incidents_workspace_id",
        "incidents",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_audit_logs_workspace_id",
        "audit_logs",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_security_events_workspace_id", "security_events", ["workspace_id"])
    op.create_index("ix_incidents_workspace_id", "incidents", ["workspace_id"])
    op.create_index("ix_audit_logs_workspace_id", "audit_logs", ["workspace_id"])

    op.alter_column(
        "response_actions",
        "actor",
        existing_type=sa.String(length=32),
        type_=sa.String(length=64),
        existing_nullable=True,
    )
    op.alter_column(
        "audit_logs",
        "actor",
        existing_type=sa.String(length=32),
        type_=sa.String(length=64),
        existing_nullable=False,
    )


def downgrade() -> None:
    raise NotImplementedError("Forward-only migration")
