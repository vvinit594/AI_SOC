import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.time import utc_now
from app.db.base import Base
from app.db.types import UTCDateTime


class User(Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_email", "email", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)

    memberships: Mapped[list["WorkspaceMembership"]] = relationship(back_populates="user")
    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user")


class Workspace(Base):
    __tablename__ = "workspaces"
    __table_args__ = (Index("ix_workspaces_kind", "kind"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="personal")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)

    memberships: Mapped[list["WorkspaceMembership"]] = relationship(back_populates="workspace")


class WorkspaceMembership(Base):
    __tablename__ = "workspace_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "workspace_id", name="uq_workspace_memberships_user_workspace"),
        Index("ix_workspace_memberships_workspace_id", "workspace_id"),
        Index("ix_workspace_memberships_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="owner")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)

    user: Mapped[User] = relationship(back_populates="memberships")
    workspace: Mapped[Workspace] = relationship(back_populates="memberships")


class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (
        Index("ix_user_sessions_token_hash", "token_hash", unique=True),
        Index("ix_user_sessions_user_id", "user_id"),
        Index("ix_user_sessions_expires_at", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    csrf_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)
    user_agent: Mapped[str | None] = mapped_column(String(255))
    ip_address: Mapped[str | None] = mapped_column(String(45))

    user: Mapped[User] = relationship(back_populates="sessions")
    workspace: Mapped[Workspace] = relationship()


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    __table_args__ = (
        Index("ix_login_attempts_email_attempted_at", "email", "attempted_at"),
        Index("ix_login_attempts_ip_attempted_at", "ip_address", "attempted_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attempted_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)


class PasswordRecoveryToken(Base):
    __tablename__ = "password_recovery_tokens"
    __table_args__ = (
        Index("ix_password_recovery_tokens_token_hash", "token_hash", unique=True),
        Index("ix_password_recovery_tokens_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)

    user: Mapped[User] = relationship()


class SecurityEvent(Base):
    __tablename__ = "security_events"
    __table_args__ = (
        Index("ix_security_events_timestamp", "timestamp"),
        Index("ix_security_events_event_type", "event_type"),
        Index("ix_security_events_source_ip", "source_ip"),
        Index("ix_security_events_username", "username"),
        Index("ix_security_events_hostname", "hostname"),
        Index("ix_security_events_workspace_id", "workspace_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_ip: Mapped[str | None] = mapped_column(String(45))
    destination_ip: Mapped[str | None] = mapped_column(String(45))
    username: Mapped[str | None] = mapped_column(String(128))
    hostname: Mapped[str | None] = mapped_column(String(255))
    action: Mapped[str | None] = mapped_column(String(128))
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_message: Mapped[str] = mapped_column(Text, nullable=False)
    scenario: Mapped[str | None] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)

    incident_links: Mapped[list["IncidentEvent"]] = relationship(back_populates="event")
    workspace: Mapped[Workspace] = relationship()


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        Index("ix_incidents_created_at", "created_at"),
        Index("ix_incidents_severity", "severity"),
        Index("ix_incidents_status", "status"),
        Index("ix_incidents_workspace_id", "workspace_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    scenario: Mapped[str | None] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)

    event_links: Mapped[list["IncidentEvent"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )
    agent_runs: Mapped[list["AgentRun"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )
    response_actions: Mapped[list["ResponseAction"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )
    workspace: Mapped[Workspace] = relationship()


class IncidentEvent(Base):
    __tablename__ = "incident_events"
    __table_args__ = (
        UniqueConstraint("incident_id", "event_id", name="uq_incident_events_pair"),
        Index("ix_incident_events_incident_id", "incident_id"),
        Index("ix_incident_events_event_id", "event_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("security_events.id", ondelete="CASCADE"), nullable=False
    )
    link_type: Mapped[str] = mapped_column(
        "relationship", String(32), nullable=False, default="evidence"
    )

    incident: Mapped[Incident] = relationship(back_populates="event_links")
    event: Mapped[SecurityEvent] = relationship(back_populates="incident_links")


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        UniqueConstraint(
            "investigation_id", "agent_name", name="uq_agent_runs_investigation_agent"
        ),
        Index("ix_agent_runs_incident_id", "incident_id"),
        Index("ix_agent_runs_investigation_id", "investigation_id"),
        Index("ix_agent_runs_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    structured_output: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    error: Mapped[str | None] = mapped_column(Text)

    incident: Mapped[Incident] = relationship(back_populates="agent_runs")


class ResponseAction(Base):
    __tablename__ = "response_actions"
    __table_args__ = (
        Index("ix_response_actions_incident_id", "incident_id"),
        Index("ix_response_actions_approval_status", "approval_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str | None] = mapped_column(String(255))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    approval_status: Mapped[str] = mapped_column(String(32), nullable=False, default="proposed")
    execution_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="not_executed"
    )
    simulated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    actor: Mapped[str | None] = mapped_column(String(64))

    incident: Mapped[Incident] = relationship(back_populates="response_actions")


class AuditLog(Base):
    """Append-only application audit event. Do not update or delete via services."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_occurred_at", "occurred_at"),
        Index("ix_audit_logs_incident_id", "incident_id"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index("ix_audit_logs_event_type", "event_type"),
        Index("ix_audit_logs_workspace_id", "workspace_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("incidents.id", ondelete="SET NULL")
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="SET NULL")
    )
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
