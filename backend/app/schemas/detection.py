import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.enums import Severity
from app.schemas.incidents import IncidentRead


class DetectionMatch(BaseModel):
    rule_id: str
    severity: Severity
    event_ids: list[uuid.UUID]
    reason: str
    matched_threshold: str
    timestamp: datetime
    incident_id: uuid.UUID


class DetectResponse(BaseModel):
    matches: list[DetectionMatch] = Field(default_factory=list)
    incidents: list[IncidentRead] = Field(default_factory=list)
    created: int = 0
    updated: int = 0
