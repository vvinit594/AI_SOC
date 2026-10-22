"""Initial security event and incident tables.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "security_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("source_ip", sa.String(length=45), nullable=True),
        sa.Column("destination_ip", sa.String(length=45), nullable=True),
        sa.Column("username", sa.String(length=128), nullable=True),
        sa.Column("hostname", sa.String(length=255), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("raw_message", sa.Text(), nullable=False),
        sa.Column("scenario", sa.String(length=8), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_security_events_timestamp", "security_events", ["timestamp"])
    op.create_index("ix_security_events_event_type", "security_events", ["event_type"])
    op.create_index("ix_security_events_source_ip", "security_events", ["source_ip"])
    op.create_index("ix_security_events_username", "security_events", ["username"])
    op.create_index("ix_security_events_hostname", "security_events", ["hostname"])

    op.create_table(
        "incidents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("scenario", sa.String(length=8), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incidents_created_at", "incidents", ["created_at"])
    op.create_index("ix_incidents_severity", "incidents", ["severity"])
    op.create_index("ix_incidents_status", "incidents", ["status"])

    op.create_table(
        "incident_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("relationship", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["security_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("incident_id", "event_id", name="uq_incident_events_pair"),
    )
    op.create_index("ix_incident_events_incident_id", "incident_events", ["incident_id"])
    op.create_index("ix_incident_events_event_id", "incident_events", ["event_id"])

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("agent_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("structured_output", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_runs_incident_id", "agent_runs", ["incident_id"])
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])

    op.create_table(
        "response_actions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("target", sa.String(length=255), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("approval_status", sa.String(length=32), nullable=False),
        sa.Column("execution_status", sa.String(length=32), nullable=False),
        sa.Column("simulated", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_response_actions_incident_id", "response_actions", ["incident_id"]
    )
    op.create_index(
        "ix_response_actions_approval_status", "response_actions", ["approval_status"]
    )


def downgrade() -> None:
    op.drop_index("ix_response_actions_approval_status", table_name="response_actions")
    op.drop_index("ix_response_actions_incident_id", table_name="response_actions")
    op.drop_table("response_actions")
    op.drop_index("ix_agent_runs_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_incident_id", table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_index("ix_incident_events_event_id", table_name="incident_events")
    op.drop_index("ix_incident_events_incident_id", table_name="incident_events")
    op.drop_table("incident_events")
    op.drop_index("ix_incidents_status", table_name="incidents")
    op.drop_index("ix_incidents_severity", table_name="incidents")
    op.drop_index("ix_incidents_created_at", table_name="incidents")
    op.drop_table("incidents")
    op.drop_index("ix_security_events_hostname", table_name="security_events")
    op.drop_index("ix_security_events_username", table_name="security_events")
    op.drop_index("ix_security_events_source_ip", table_name="security_events")
    op.drop_index("ix_security_events_event_type", table_name="security_events")
    op.drop_index("ix_security_events_timestamp", table_name="security_events")
    op.drop_table("security_events")
