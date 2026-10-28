"""Approve and reject persisted response actions.

Decisions are simulated only. Phase 8A records a human decision; it never
invokes containment or any external response function. ``execution_status``
stays ``not_executed`` because ``simulated`` on the row already marks the
recommendation as non-live.

Incident status policy: investigating sets ``awaiting_approval``. Approving or
rejecting an individual action does not change incident status, including when
other actions on the same incident remain ``proposed``. Action-level
``approval_status`` is the source of truth. Incidents are never auto-resolved.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AnalystAuthError, resolve_actor
from app.core.config import Settings
from app.core.time import utc_now
from app.db.models import Incident, ResponseAction
from app.schemas.actions import ActionDecisionResponse, ResponseActionRead
from app.services.incident_lock import lock_incident

logger = logging.getLogger(__name__)

_DECIDED = frozenset({"approved", "rejected"})


class ActionError(ValueError):
    def __init__(self, detail: str, *, status_code: int) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def decide_action(
    session: Session,
    settings: Settings,
    action_id: uuid.UUID,
    decision: str,
    authorization: str | None,
) -> ActionDecisionResponse:
    if decision not in _DECIDED:
        raise ActionError("Unsupported action decision", status_code=400)
    try:
        actor = resolve_actor(settings, authorization)
    except AnalystAuthError as exc:
        raise ActionError(exc.detail, status_code=exc.status_code) from exc

    action = session.get(ResponseAction, action_id)
    if action is None:
        raise ActionError("Action not found", status_code=404)

    with lock_incident(session, action.incident_id):
        try:
            return _apply_decision(session, action_id, decision, actor)
        except ActionError:
            session.rollback()
            raise


def _apply_decision(
    session: Session,
    action_id: uuid.UUID,
    decision: str,
    actor: str,
) -> ActionDecisionResponse:
    session.expire_all()
    action = session.scalar(
        select(ResponseAction).where(ResponseAction.id == action_id).with_for_update()
    )
    if action is None:
        raise ActionError("Action not found", status_code=404)

    if action.approval_status == decision:
        incident = session.get(Incident, action.incident_id)
        return _to_response(action, incident)

    if action.approval_status in _DECIDED:
        raise ActionError(
            f"Action already {action.approval_status}",
            status_code=409,
        )

    action.approval_status = decision
    action.decided_at = utc_now()
    action.actor = actor
    action.simulated = True
    action.execution_status = "not_executed"
    incident = session.get(Incident, action.incident_id)
    session.commit()
    logger.info(
        "Response action decided action_id=%s decision=%s actor=%s",
        action_id,
        decision,
        actor,
    )
    return _to_response(action, incident)


def _to_response(action: ResponseAction, incident: Incident | None) -> ActionDecisionResponse:
    payload = ResponseActionRead.model_validate(action)
    status = incident.status if incident is not None else "awaiting_approval"
    data = payload.model_dump()
    data["incident_status"] = status
    data["simulated"] = True
    return ActionDecisionResponse.model_validate(data)
