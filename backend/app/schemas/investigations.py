from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import AgentName, AgentRunStatus, Confidence, RiskLevel

FactKind = Literal["verified", "unavailable", "assessment"]
IntelStatus = Literal["ok", "unavailable"]
AssessmentSource = Literal["deterministic_rules", "llm"]


class Fact(BaseModel):
    kind: FactKind
    statement: str
    event_ids: list[uuid.UUID] = Field(default_factory=list)


class AgentFinding(BaseModel):
    finding: str
    evidence_event_ids: list[uuid.UUID]
    confidence: Confidence
    reasoning_summary: str
    recommended_next_step: str
    facts: list[Fact] = Field(default_factory=list)
    techniques: list[str] = Field(default_factory=list)
    assessment_source: AssessmentSource = "deterministic_rules"
    llm_status: Literal["ok", "unavailable", "not_requested"] = "not_requested"
    used_fallback: bool = False


class ThreatIntelRecord(BaseModel):
    indicator: str
    indicator_type: Literal["ip"] = "ip"
    status: IntelStatus
    provider: str
    source: str
    fetched_at: datetime
    summary: str
    score: int | None = None
    classification: str | None = None
    cache_hit: bool = False


class RecommendedAction(BaseModel):
    action_type: str
    target: str | None = None
    reason: str
    risk_level: RiskLevel
    simulated: bool = True
    priority: int = 1


class AgentRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    investigation_id: uuid.UUID
    incident_id: uuid.UUID
    agent_name: AgentName
    status: AgentRunStatus
    structured_output: dict[str, Any]
    started_at: datetime | None
    completed_at: datetime | None
    error: str | None


class InvestigationRead(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    status: AgentRunStatus
    nodes: list[AgentRunRead]
    assessment_source: AssessmentSource = "deterministic_rules"


class InvestigateResponse(BaseModel):
    investigation: InvestigationRead
    created: bool
