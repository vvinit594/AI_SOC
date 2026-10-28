from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.enums import ActionStatus, ExecutionStatus, IncidentStatus, RiskLevel


class ResponseActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    incident_id: uuid.UUID
    action_type: str
    target: str | None
    reason: str
    risk_level: RiskLevel
    approval_status: ActionStatus
    execution_status: ExecutionStatus
    simulated: bool
    created_at: datetime
    decided_at: datetime | None
    actor: str | None


class ActionDecisionResponse(ResponseActionRead):
    incident_status: IncidentStatus
