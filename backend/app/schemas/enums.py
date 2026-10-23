from typing import Literal

Severity = Literal["critical", "high", "medium", "low"]
Confidence = Literal["low", "medium", "high"]
IncidentStatus = Literal[
    "open",
    "investigating",
    "awaiting_approval",
    "resolved",
    "dismissed",
]
DemoScenario = Literal["A", "B", "C"]
AgentName = Literal[
    "investigation",
    "threat_intelligence",
    "analysis",
    "response_planner",
]
AgentRunStatus = Literal[
    "queued",
    "running",
    "completed",
    "failed",
    "waiting_for_approval",
]
ActionStatus = Literal["proposed", "approved", "rejected"]
ExecutionStatus = Literal["not_executed", "simulated", "failed"]
RiskLevel = Literal["low", "medium", "high"]
