"""Append-only audit history.

Application services may insert rows and read them. They must never update or
delete audit entries. Database administrators with direct SQL access can still
alter rows; this is application-level append-only behaviour, not tamper-proof
storage. Retention (how long to keep rows) is an operational decision and is
not automated in Phase 8B.

``details`` is schema-controlled per event type. Unsupported keys and invalid
values are rejected. Duplicate event types for one resource are allowed; the
approve/reject state machine, not a unique constraint, enforces decision
idempotency.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.db.models import AuditLog, Incident
from app.schemas.audit import ResponseActionDecisionDetails
from app.schemas.enums import AuditEventType, AuditResourceType

logger = logging.getLogger(__name__)

_ALLOWED_EVENTS: frozenset[str] = frozenset(
    {"response_action.approved", "response_action.rejected"}
)
_ALLOWED_RESOURCES: frozenset[str] = frozenset({"response_action"})


class AuditError(ValueError):
    def __init__(self, detail: str, *, status_code: int) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _decision_details(event_type: str, details: Mapping[str, Any] | None) -> dict[str, Any]:
    try:
        parsed = ResponseActionDecisionDetails.model_validate(dict(details or {}))
    except (ValidationError, TypeError, ValueError) as exc:
        logger.warning("Rejected audit details for event_type=%s", event_type)
        raise AuditError("Invalid audit event details", status_code=500) from exc
    expected = f"response_action.{parsed.decision}"
    if event_type != expected:
        raise AuditError("Invalid audit event details", status_code=500)
    return parsed.model_dump()


def record_event(
    session: Session,
    *,
    event_type: AuditEventType,
    actor: str,
    resource_type: AuditResourceType,
    resource_id: uuid.UUID,
    incident_id: uuid.UUID | None = None,
    details: Mapping[str, Any] | None = None,
) -> AuditLog:
    """Add an audit row to the current session. Does not commit.

    The caller must commit this row in the same transaction as the business
    change it describes. Failures must not be swallowed.
    """
    if event_type not in _ALLOWED_EVENTS:
        raise AuditError("Unsupported audit event type", status_code=500)
    if resource_type not in _ALLOWED_RESOURCES:
        raise AuditError("Unsupported audit resource type", status_code=500)
    if actor not in {"analyst", "unverified"}:
        raise AuditError("Unsupported audit actor", status_code=500)

    payload = _decision_details(event_type, details)

    row = AuditLog(
        occurred_at=utc_now(),
        event_type=event_type,
        actor=actor,
        resource_type=resource_type,
        resource_id=resource_id,
        incident_id=incident_id,
        details=payload,
    )
    session.add(row)
    logger.info(
        "Audit event queued event_type=%s actor=%s resource_type=%s resource_id=%s",
        event_type,
        actor,
        resource_type,
        resource_id,
    )
    return row


def list_incident_audit_logs(
    session: Session,
    incident_id: uuid.UUID,
    *,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[AuditLog], int]:
    incident = session.get(Incident, incident_id)
    if incident is None:
        raise AuditError("Incident not found", status_code=404)
    filters = [AuditLog.incident_id == incident_id]
    total = session.scalar(select(func.count()).select_from(AuditLog).where(*filters)) or 0
    items = list(
        session.scalars(
            select(AuditLog)
            .where(*filters)
            .order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return items, total
