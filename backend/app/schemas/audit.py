from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import AuditEventType, AuditResourceType


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
