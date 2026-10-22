import uuid

from pydantic import BaseModel, Field

from app.schemas.enums import DemoScenario


class RecordError(BaseModel):
    index: int
    detail: str


class LogUploadResponse(BaseModel):
    accepted: int
    rejected: int
    event_ids: list[uuid.UUID] = Field(default_factory=list)
    errors: list[RecordError] = Field(default_factory=list)


class ScenarioLoadResponse(BaseModel):
    scenario: DemoScenario
    accepted: int
    event_ids: list[uuid.UUID]
