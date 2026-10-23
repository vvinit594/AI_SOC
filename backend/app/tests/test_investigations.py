import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.agents.attck import get_attack_technique
from app.db.models import Incident, IncidentEvent, ResponseAction, SecurityEvent
from app.schemas.investigations import AgentFinding
from app.services.llm import LLMError
from app.services.threat_intel import NoneThreatIntel, is_documentation_ip


def _open_incident(client: TestClient) -> str:
    session = client.app.state.session_factory()
    try:
        event = SecurityEvent(
            timestamp=datetime(2026, 10, 21, 12, 0, tzinfo=UTC),
            event_type="login_failure",
            source_ip="192.0.2.10",
            username="demo_user",
            hostname="demo-server-01",
            action="authentication_failed",
            source="linux_auth",
            raw_message="Failed password",
            scenario="A",
        )
        incident = Incident(
            title="Test brute force",
            severity="high",
            status="open",
            summary="test",
            scenario="A",
        )
        session.add_all([event, incident])
        session.flush()
        session.add(
            IncidentEvent(
                incident_id=incident.id,
                event_id=event.id,
                link_type="evidence",
            )
        )
        session.commit()
        return str(incident.id)
    finally:
        session.close()


def test_unknown_technique_is_rejected() -> None:
    assert get_attack_technique("T1110") is not None
    assert get_attack_technique("T9999") is None


def test_documentation_ips_are_detected() -> None:
    assert is_documentation_ip("192.0.2.10")
    assert is_documentation_ip("198.51.100.88")
    assert not is_documentation_ip("8.8.8.8")


def test_none_threat_intel_is_unavailable() -> None:
    record = NoneThreatIntel().lookup_ip("192.0.2.10")
    assert record.status == "unavailable"
    assert "disabled" in record.summary.lower() or "none" in record.summary.lower()


def test_investigate_unknown_incident_404(client: TestClient) -> None:
    response = client.post(f"/api/incidents/{uuid.uuid4()}/investigate")
    assert response.status_code == 404


def test_investigate_closed_incident_409(client: TestClient) -> None:
    incident_id = _open_incident(client)
    session = client.app.state.session_factory()
    try:
        incident = session.get(Incident, uuid.UUID(incident_id))
        assert incident is not None
        incident.status = "resolved"
        session.commit()
    finally:
        session.close()
    response = client.post(f"/api/incidents/{incident_id}/investigate")
    assert response.status_code == 409


def test_end_to_end_investigation_scenario_a(client: TestClient) -> None:
    assert client.post("/api/scenarios/A/load").status_code == 200
    detect = client.post("/api/incidents/detect").json()
    incident_id = detect["incidents"][0]["id"]
    first = client.post(f"/api/incidents/{incident_id}/investigate")
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["created"] is True
    investigation = body["investigation"]
    assert investigation["status"] == "completed"
    assert {node["agent_name"] for node in investigation["nodes"]} == {
        "investigation",
        "threat_intelligence",
        "analysis",
        "response_planner",
    }
    assert all(node["status"] == "completed" for node in investigation["nodes"])
    analysis = next(node for node in investigation["nodes"] if node["agent_name"] == "analysis")
    techniques = analysis["structured_output"]["techniques"]
    assert "T1110" in techniques
    assert "T1078" in techniques
    intel = next(
        node for node in investigation["nodes"] if node["agent_name"] == "threat_intelligence"
    )
    assert all(
        record["status"] == "unavailable" for record in intel["structured_output"]["records"]
    )
    planner = next(
        node for node in investigation["nodes"] if node["agent_name"] == "response_planner"
    )
    actions = planner["structured_output"]["actions"]
    assert actions
    assert all(action["simulated"] is True for action in actions)
    detail = client.get(f"/api/investigations/{investigation['id']}")
    assert detail.status_code == 200
    assert detail.json()["id"] == investigation["id"]
    incident = client.get(f"/api/incidents/{incident_id}").json()
    assert incident["status"] == "awaiting_approval"
    session = client.app.state.session_factory()
    try:
        stored = list(
            session.scalars(
                select(ResponseAction).where(ResponseAction.incident_id == uuid.UUID(incident_id))
            ).all()
        )
        assert stored
        assert all(
            item.simulated is True and item.execution_status == "not_executed" for item in stored
        )
    finally:
        session.close()

    second = client.post(f"/api/incidents/{incident_id}/investigate")
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert second.json()["investigation"]["id"] == investigation["id"]


def test_scenario_c_does_not_claim_confirmed_attack(client: TestClient) -> None:
    assert client.post("/api/scenarios/C/load").status_code == 200
    session = client.app.state.session_factory()
    try:
        incident = Incident(
            title="Benign review",
            severity="low",
            status="open",
            summary="manual",
            scenario="C",
        )
        session.add(incident)
        session.flush()
        from app.db.demo_data import BENIGN_IDS

        for event_id in BENIGN_IDS:
            session.add(
                IncidentEvent(incident_id=incident.id, event_id=event_id, link_type="evidence")
            )
        session.commit()
        incident_id = str(incident.id)
    finally:
        session.close()

    response = client.post(f"/api/incidents/{incident_id}/investigate")
    assert response.status_code == 200, response.text
    analysis = next(
        node
        for node in response.json()["investigation"]["nodes"]
        if node["agent_name"] == "analysis"
    )
    assert analysis["structured_output"]["confidence"] == "low"
    assert "insufficient" in analysis["structured_output"]["finding"].lower()
    assert analysis["structured_output"]["techniques"] == []


def test_invalid_llm_output_falls_back_to_deterministic(client: TestClient, monkeypatch) -> None:
    from app.services import investigations as service

    class BoomLLM:
        def generate(self, **_kwargs: object) -> AgentFinding:
            raise LLMError("invalid json")

    original = service.build_llm_client

    def _client(settings, override=None):  # type: ignore[no-untyped-def]
        return BoomLLM()

    monkeypatch.setattr(service, "build_llm_client", _client)
    assert client.post("/api/scenarios/B/load").status_code == 200
    detect = client.post("/api/incidents/detect").json()
    incident_id = detect["incidents"][0]["id"]
    response = client.post(f"/api/incidents/{incident_id}/investigate")
    assert response.status_code == 200, response.text
    analysis = next(
        node
        for node in response.json()["investigation"]["nodes"]
        if node["agent_name"] == "analysis"
    )
    assert analysis["status"] == "completed"
    assert analysis["structured_output"]["llm_status"] == "unavailable"
    assert analysis["structured_output"]["assessment_source"] == "deterministic_rules"
    assert "T1071" in analysis["structured_output"]["techniques"]
    monkeypatch.setattr(service, "build_llm_client", original)


def test_sse_stream_is_not_implemented(client: TestClient) -> None:
    response = client.get(f"/api/investigations/{uuid.uuid4()}/stream")
    assert response.status_code == 501
    assert "Phase 7" in response.json()["detail"]
