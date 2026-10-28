"""Approve and reject simulated response actions."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.actions import ActionDecisionResponse
from app.services.actions import ActionError, decide_action

router = APIRouter(prefix="/actions", tags=["actions"])


def _decide(
    action_id: uuid.UUID,
    decision: str,
    session: Session,
    settings: Settings,
    authorization: str | None,
) -> ActionDecisionResponse:
    try:
        return decide_action(session, settings, action_id, decision, authorization)
    except ActionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post(
    "/{action_id}/approve",
    response_model=ActionDecisionResponse,
    summary="Approve a proposed simulated response action",
)
def approve_action(
    action_id: uuid.UUID,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    authorization: Annotated[str | None, Header()] = None,
) -> ActionDecisionResponse:
    return _decide(action_id, "approved", session, settings, authorization)


@router.post(
    "/{action_id}/reject",
    response_model=ActionDecisionResponse,
    summary="Reject a proposed simulated response action",
)
def reject_action(
    action_id: uuid.UUID,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    authorization: Annotated[str | None, Header()] = None,
) -> ActionDecisionResponse:
    return _decide(action_id, "rejected", session, settings, authorization)
