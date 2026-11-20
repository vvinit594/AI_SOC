"""Approve and reject simulated response actions."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import Access, workspace_action_or_404
from app.core.config import Settings, get_settings
from app.db.models import ResponseAction
from app.db.session import get_db
from app.schemas.actions import ActionDecisionResponse
from app.services.actions import ActionError, decide_action

router = APIRouter(prefix="/actions", tags=["actions"])


def _decide(
    action_id: uuid.UUID,
    decision: str,
    session: Session,
    settings: Settings,
    access: Access,
) -> ActionDecisionResponse:
    action = session.get(ResponseAction, action_id)
    workspace_action_or_404(session, action, access)
    try:
        return decide_action(
            session,
            settings,
            action_id,
            decision,
            authorization=None,
            actor=access.actor,
            workspace_id=access.workspace_id,
        )
    except ActionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post(
    "/{action_id}/approve",
    response_model=ActionDecisionResponse,
    summary="Approve a proposed simulated response action",
)
def approve_action(
    action_id: uuid.UUID,
    access: Access,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ActionDecisionResponse:
    return _decide(action_id, "approved", session, settings, access)


@router.post(
    "/{action_id}/reject",
    response_model=ActionDecisionResponse,
    summary="Reject a proposed simulated response action",
)
def reject_action(
    action_id: uuid.UUID,
    access: Access,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ActionDecisionResponse:
    return _decide(action_id, "rejected", session, settings, access)
