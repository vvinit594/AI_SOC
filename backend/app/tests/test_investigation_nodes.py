import uuid
from datetime import UTC, datetime

import httpx
from fastapi.testclient import TestClient
from langchain_core.runnables import RunnableConfig

from app.agents.graph import build_investigation_graph
from app.agents.nodes import (
    NODE_NAMES,
    analysis_node,
    investigation_node,
    response_planner_node,
    threat_intelligence_node,
)
from app.db.models import AgentRun, Incident
from app.schemas.investigations import AgentFinding, ThreatIntelRecord
from app.services.llm import LLMError, OpenAICompatibleLLM
from app.services.threat_intel import AbuseIPDBClient, CachingThreatIntel
from app.tests.test_investigations import _open_incident


class MemoryRecorder:
    def __init__(self) -> None:
        self.started: list[str] = []
        self.completed: dict[str, dict] = {}
        self.failed: dict[str, str] = {}

    def start(self, agent_name: str) -> None:
        self.started.append(agent_name)

    def complete(self, agent_name: str, output: dict) -> None:
        self.completed[agent_name] = output

    def fail(self, agent_name: str, error: str) -> None:
        self.failed[agent_name] = error


def _incident_ctx(client: TestClient, incident_id: str) -> dict:
    session = client.app.state.session_factory()
    incident = session.get(Incident, uuid.UUID(incident_id))
    assert incident is not None
    return {
        "id": str(incident.id),
        "title": incident.title,
        "severity": incident.severity,
        "status": incident.status,
        "summary": incident.summary,
        "scenario": incident.scenario,
        "_session": session,
        "incident": incident,
    }


def test_graph_transitions_are_linear_and_complete() -> None:
    compiled = build_investigation_graph()
    edges = {(edge.source, edge.target) for edge in compiled.get_graph().edges}
    assert ("__start__", "investigation") in edges
    assert ("investigation", "threat_intelligence") in edges
    assert ("threat_intelligence", "analysis") in edges
    assert ("analysis", "response_planner") in edges
    assert ("response_planner", "__end__") in edges
    assert NODE_NAMES == (
        "investigation",
        "threat_intelligence",
        "analysis",
        "response_planner",
    )


def test_investigation_node_loads_verified_evidence(client: TestClient) -> None:
    incident_id = _open_incident(client)
    ctx = _incident_ctx(client, incident_id)
    session = ctx.pop("_session")
    recorder = MemoryRecorder()
    try:
        result = investigation_node(
            {"incident_id": incident_id},
            RunnableConfig(
                configurable={
                    "recorder": recorder,
                    "session": session,
                    "incident": ctx,
                }
            ),
        )
        assert len(result["events"]) == 1
        assert result["indicators"] == ["192.0.2.10"]
        assert "investigation" in recorder.completed
        facts = recorder.completed["investigation"]["facts"]
        assert facts[0]["kind"] == "verified"
    finally:
        session.close()


def test_threat_intelligence_node_records_unavailable(client: TestClient) -> None:
    recorder = MemoryRecorder()
    event_id = str(uuid.uuid4())

    class Disabled:
        def lookup_ip(self, ip: str) -> ThreatIntelRecord:
            return ThreatIntelRecord(
                indicator=ip,
                status="unavailable",
                provider="none",
                source="none",
                fetched_at=datetime.now(UTC),
                summary="disabled",
            )

    result = threat_intelligence_node(
        {"indicators": ["192.0.2.10"], "event_ids": [event_id]},
        RunnableConfig(configurable={"recorder": recorder, "intel": Disabled()}),
    )
    assert result["threat_intel"][0]["status"] == "unavailable"
    assert recorder.completed["threat_intelligence"]["facts"][0]["kind"] == "unavailable"


def test_threat_intelligence_node_survives_provider_exception() -> None:
    recorder = MemoryRecorder()

    class Boom:
        def lookup_ip(self, ip: str) -> ThreatIntelRecord:
            raise RuntimeError("provider exploded")

    result = threat_intelligence_node(
        {"indicators": ["192.0.2.10"], "event_ids": []},
        RunnableConfig(configurable={"recorder": recorder, "intel": Boom()}),
    )
    assert result["threat_intel"] == []
    assert "threat_intelligence" in result["node_errors"]
    assert "threat_intelligence" in recorder.failed


def test_analysis_node_maps_brute_force_from_evidence() -> None:
    recorder = MemoryRecorder()
    event_id = str(uuid.uuid4())
    events = [
        {
            "id": event_id,
            "event_type": "login_failure",
            "username": "demo_user",
            "source_ip": "192.0.2.10",
        }
        for _ in range(5)
    ]
    events[0] = {**events[0], "id": event_id}
    for index in range(1, 5):
        events[index]["id"] = str(uuid.uuid4())
    events.append(
        {
            "id": str(uuid.uuid4()),
            "event_type": "login_success",
            "username": "demo_user",
            "source_ip": "192.0.2.10",
        }
    )

    class NoLLM:
        def generate(self, **_kwargs: object) -> AgentFinding:
            raise LLMError("disabled")

    result = analysis_node(
        {
            "events": events,
            "event_ids": [item["id"] for item in events],
            "threat_intel": [{"status": "unavailable", "indicator": "192.0.2.10"}],
        },
        RunnableConfig(configurable={"recorder": recorder, "llm": NoLLM()}),
    )
    analysis = result["analysis"]
    assert "T1110" in analysis["techniques"]
    assert "T1078" in analysis["techniques"]
    assert analysis["assessment_source"] == "deterministic_rules"
    kinds = {fact["kind"] for fact in analysis["facts"]}
    assert "verified" in kinds
    assert "unavailable" in kinds
    assert "assessment" in kinds


def test_analysis_filters_invented_techniques_and_event_ids() -> None:
    recorder = MemoryRecorder()
    real_id = uuid.uuid4()
    invented_id = uuid.uuid4()

    class InventLLM:
        def generate(self, **_kwargs: object) -> AgentFinding:
            return AgentFinding(
                finding="invented attribution",
                evidence_event_ids=[invented_id, real_id],
                confidence="high",
                reasoning_summary="model output",
                recommended_next_step="ignore extra ids",
                techniques=["T9999", "T1110"],
            )

    result = analysis_node(
        {
            "events": [{"id": str(real_id), "event_type": "login_failure"}],
            "event_ids": [str(real_id)],
            "threat_intel": [],
        },
        RunnableConfig(configurable={"recorder": recorder, "llm": InventLLM()}),
    )
    analysis = result["analysis"]
    assert analysis["techniques"] == ["T1110"]
    assert analysis["evidence_event_ids"] == [str(real_id)]
    assert analysis["assessment_source"] == "llm"


def test_response_planner_actions_are_simulated() -> None:
    recorder = MemoryRecorder()
    persisted: list = []
    event_id = str(uuid.uuid4())

    class NoLLM:
        def generate(self, **_kwargs: object) -> AgentFinding:
            raise LLMError("disabled")

    result = response_planner_node(
        {
            "events": [
                {
                    "id": event_id,
                    "event_type": "login_failure",
                    "username": "demo_user",
                    "source_ip": "192.0.2.10",
                }
            ],
            "event_ids": [event_id],
            "analysis": {"techniques": ["T1110"], "finding": "brute force"},
        },
        RunnableConfig(
            configurable={
                "recorder": recorder,
                "llm": NoLLM(),
                "persist_actions": persisted.extend,
            }
        ),
    )
    assert result["recommendations"]
    assert all(item["simulated"] is True for item in result["recommendations"])
    assert persisted
    assert all(item.simulated is True for item in persisted)


def test_abuseipdb_failures_are_unavailable(monkeypatch) -> None:
    missing_key = AbuseIPDBClient(None, 1).lookup_ip("8.8.8.8")
    assert missing_key.status == "unavailable"

    def boom(*_args: object, **_kwargs: object) -> httpx.Response:
        raise httpx.ConnectError("unreachable")

    monkeypatch.setattr("app.services.threat_intel.httpx.get", boom)
    failed = AbuseIPDBClient("test-key", 1).lookup_ip("8.8.8.8")
    assert failed.status == "unavailable"
    assert "unavailable" in failed.summary.lower() or "failed" in failed.summary.lower()

    cached = CachingThreatIntel(AbuseIPDBClient("test-key", 1), ttl_seconds=60)
    first = cached.lookup_ip("8.8.8.8")
    second = cached.lookup_ip("8.8.8.8")
    assert first.status == "unavailable"
    assert second.cache_hit is True


def test_openai_invalid_json_raises_llm_error(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"choices": [{"message": {"content": "not-json{"}}]}

    monkeypatch.setattr("app.services.llm.httpx.post", lambda *_args, **_kwargs: FakeResponse())
    client = OpenAICompatibleLLM("key", "gpt-4o-mini", timeout_seconds=1, max_retries=0)
    try:
        client.generate(system="s", user="u", schema=AgentFinding)
        raise AssertionError("expected LLMError")
    except LLMError as exc:
        assert "invalid" in str(exc).lower() or "unavailable" in str(exc).lower()


def test_failed_investigation_can_be_retried(client: TestClient) -> None:
    incident_id = _open_incident(client)
    previous = uuid.uuid4()
    session = client.app.state.session_factory()
    try:
        for name in NODE_NAMES:
            session.add(
                AgentRun(
                    investigation_id=previous,
                    incident_id=uuid.UUID(incident_id),
                    agent_name=name,
                    status="failed",
                    structured_output={},
                    error="previous run failed",
                )
            )
        session.commit()
    finally:
        session.close()
    response = client.post(f"/api/incidents/{incident_id}/investigate")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["created"] is True
    assert body["investigation"]["id"] != str(previous)
    assert body["investigation"]["status"] == "completed"
