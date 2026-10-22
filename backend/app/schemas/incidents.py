import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.time import require_aware_utc
from app.schemas.enums import DemoScenario, IncidentStatus, Severity


class IncidentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    severity: Severity
    status: IncidentStatus = "open"
    summary: str = Field(min_length=1)
    scenario: DemoScenario | None = None
    created_at: datetime | None = None
    event_ids: list[uuid.UUID] = Field(default_factory=list)

    @field_validator("created_at")
    @classmethod
    def created_at_must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        return require_aware_utc(value)


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    severity: Severity
    status: IncidentStatus
    summary: str
    scenario: str | None
    created_at: datetime
    event_ids: list[uuid.UUID] = Field(default_factory=list)


class IncidentListResponse(BaseModel):
    items: list[IncidentRead]
    total: int
