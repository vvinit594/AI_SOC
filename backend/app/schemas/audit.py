from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.enums import ActionStatus, AuditEventType, AuditResourceType

_ACTION_TYPE_MAX_LEN = 64


class ResponseActionDecisionDetails(BaseModel):
    """Allowlisted metadata for response_action.approved / .rejected."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected"]
    previous_approval_status: ActionStatus
    resulting_approval_status: Literal["approved", "rejected"]
    action_type: str = Field(min_length=1, max_length=_ACTION_TYPE_MAX_LEN)

    @model_validator(mode="after")
    def decision_matches_result(self) -> ResponseActionDecisionDetails:
        if self.decision != self.resulting_approval_status:
            raise ValueError("decision must match resulting_approval_status")
        return self


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    occurred_at: datetime
    event_type: AuditEventType
    actor: str
    resource_type: AuditResourceType
    resource_id: uuid.UUID
    incident_id: uuid.UUID | None
    details: dict[str, Any] = Field(default_factory=dict)


class AuditLogListResponse(BaseModel):
    items: list[AuditLogRead]
    total: int
