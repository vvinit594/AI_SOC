import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.time import require_aware_utc
from app.schemas.enums import DemoScenario


class SecurityEventCreate(BaseModel):
    timestamp: datetime
    event_type: str = Field(min_length=1, max_length=64)
    source_ip: str | None = Field(default=None, max_length=45)
    destination_ip: str | None = Field(default=None, max_length=45)
    username: str | None = Field(default=None, max_length=128)
    hostname: str | None = Field(default=None, max_length=255)
    action: str | None = Field(default=None, max_length=128)
    source: str = Field(min_length=1, max_length=64)
    raw_message: str = Field(min_length=1)
    scenario: DemoScenario | None = None
    id: uuid.UUID | None = None

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_aware(cls, value: datetime) -> datetime:
        return require_aware_utc(value)


class SecurityEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    timestamp: datetime
    event_type: str
    source_ip: str | None
    destination_ip: str | None
    username: str | None
    hostname: str | None
    action: str | None
    source: str
    raw_message: str
    scenario: str | None
    created_at: datetime


class EventListResponse(BaseModel):
    items: list[SecurityEventRead]
    total: int
