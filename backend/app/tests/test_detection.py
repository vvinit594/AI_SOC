import json
import uuid

from fastapi.testclient import TestClient

from app.db.demo_data import BRUTE_SUCCESS_ID, INCIDENT_BRUTE_ID, OUTBOUND_IDS
from app.main import create_app
from app.tests.helpers import build_settings


def _upload_events(client: TestClient, events: list[dict[str, object]]):
    return client.post(
        "/api/logs/upload",
        files={
            "file": (
                "events.json",
                json.dumps(events).encode("utf-8"),
                "application/json",
            )
        },
    )


def _failure(
    minute: int,
    *,
    event_id: str | None = None,
    source_ip: str = "192.0.2.10",
    username: str = "demo_user",
) -> dict[str, object]:
    return {
        "id": event_id or str(uuid.uuid4()),
        "timestamp": f"2026-10-21T12:{minute:02d}:00Z",
        "event_type": "login_failure",
        "source_ip": source_ip,
        "username": username,
        "source": "linux_auth",
        "raw_message": f"Failed password for {username} from {source_ip}",
    }


def _success(
    minute: int,
    *,
    source_ip: str = "192.0.2.10",
    username: str = "demo_user",
) -> dict[str, object]:
    return {
        "id": str(uuid.uuid4()),
        "timestamp": f"2026-10-21T12:{minute:02d}:00Z",
        "event_type": "login_success",
        "source_ip": source_ip,
        "username": username,
        "source": "linux_auth",
        "raw_message": f"Accepted password for {username} from {source_ip}",
    }


def _outbound(
    index: int,
    *,
    dest: str = "203.0.113.10",
    host: str = "demo-server-02",
) -> dict[str, object]:
    second = index * 20
    return {
        "id": str(uuid.uuid4()),
        "timestamp": f"2026-10-21T13:{second // 60:02d}:{second % 60:02d}Z",
        "event_type": "outbound_connection",
        "source_ip": "192.0.2.50",
        "destination_ip": dest,
        "hostname": host,
        "source": "firewall",
        "raw_message": f"Outbound TCP 192.0.2.50 -> {dest}",
    }


def test_r1_does_not_fire_below_threshold(client: TestClient) -> None:
    _upload_events(client, [_failure(minute) for minute in range(4)])
    response = client.post("/api/incidents/detect")
    assert response.status_code == 200
    body = response.json()
    assert body["matches"] == []
    assert body["created"] == 0
    assert client.get("/api/incidents").json()["total"] == 0


def test_r1_fires_at_threshold(client: TestClient) -> None:
    _upload_events(client, [_failure(minute) for minute in range(5)])
    response = client.post("/api/incidents/detect")
    assert response.status_code == 200
    body = response.json()
    assert body["created"] == 1
    assert {match["rule_id"] for match in body["matches"]} == {"R1"}
    incident = body["incidents"][0]
    assert incident["severity"] == "high"
    assert incident["status"] == "open"
    assert len(incident["event_ids"]) == 5
    assert "T1110" in incident["summary"]


def test_r1_respects_time_window() -> None:
    settings = build_settings(rule_auth_failure_window_minutes=5)
    from app.db.base import Base

    application = create_app(settings)
    Base.metadata.create_all(application.state.engine)
    with TestClient(application) as client:
        _upload_events(client, [_failure(minute) for minute in (0, 2, 4, 6, 8)])
        body = client.post("/api/incidents/detect").json()
        assert body["created"] == 0
        assert client.get("/api/incidents").json()["total"] == 0


def test_r1_threshold_is_configurable() -> None:
    from app.db.base import Base

    settings = build_settings(rule_auth_failure_threshold=6)
    application = create_app(settings)
    Base.metadata.create_all(application.state.engine)
    with TestClient(application) as client:
        _upload_events(client, [_failure(minute) for minute in range(5)])
        body = client.post("/api/incidents/detect").json()
        assert body["created"] == 0
        _upload_events(client, [_failure(5)])
        body = client.post("/api/incidents/detect").json()
        assert body["created"] == 1
        assert body["incidents"][0]["severity"] == "high"


def test_r2_requires_prior_r1_match(client: TestClient) -> None:
    _upload_events(client, [_failure(0), _success(1)])
    body = client.post("/api/incidents/detect").json()
    assert body["created"] == 0
    assert body["matches"] == []


def test_r1_and_r2_create_one_critical_incident(client: TestClient) -> None:
    events = [_failure(minute) for minute in range(5)] + [_success(5)]
    _upload_events(client, events)
    body = client.post("/api/incidents/detect").json()
    assert body["created"] == 1
    assert {match["rule_id"] for match in body["matches"]} == {"R1", "R2"}
    incident = body["incidents"][0]
    assert incident["severity"] == "critical"
    assert len(incident["event_ids"]) == 6
    assert "T1078" in incident["summary"]


def test_r3_does_not_fire_below_threshold_for_unseeded_ip(client: TestClient) -> None:
    _upload_events(client, [_outbound(minute) for minute in range(9)])
    body = client.post("/api/incidents/detect").json()
    assert body["created"] == 0


def test_r3_fires_at_volume_threshold(client: TestClient) -> None:
    _upload_events(client, [_outbound(minute) for minute in range(10)])
    body = client.post("/api/incidents/detect").json()
    assert body["created"] == 1
    assert body["matches"][0]["rule_id"] == "R3"
    assert body["incidents"][0]["severity"] == "high"
    assert len(body["incidents"][0]["event_ids"]) == 10


def test_r3_fires_on_seeded_indicator_with_medium_severity(client: TestClient) -> None:
    _upload_events(client, [_outbound(0, dest="198.51.100.88")])
    body = client.post("/api/incidents/detect").json()
    assert body["created"] == 1
    assert body["incidents"][0]["severity"] == "medium"
    assert "seeded suspicious indicator" in body["matches"][0]["reason"]


def test_detect_is_idempotent(client: TestClient) -> None:
    _upload_events(client, [_failure(minute) for minute in range(5)])
    first = client.post("/api/incidents/detect").json()
    second = client.post("/api/incidents/detect").json()
    assert first["created"] == 1
    assert second["created"] == 0
    assert second["updated"] == 1
    assert first["incidents"][0]["id"] == second["incidents"][0]["id"]
    assert client.get("/api/incidents").json()["total"] == 1


def test_scenario_a_raises_critical_brute_force(client: TestClient) -> None:
    assert client.post("/api/scenarios/A/load").status_code == 200
    body = client.post("/api/incidents/detect").json()
    assert body["created"] == 1
    assert {match["rule_id"] for match in body["matches"]} == {"R1", "R2"}
    incident = body["incidents"][0]
    assert incident["severity"] == "critical"
    assert incident["scenario"] == "A"
    assert str(BRUTE_SUCCESS_ID) in incident["event_ids"]
    assert len(incident["event_ids"]) == 13


def test_scenario_b_raises_high_outbound(client: TestClient) -> None:
    assert client.post("/api/scenarios/B/load").status_code == 200
    body = client.post("/api/incidents/detect").json()
    assert body["created"] == 1
    assert body["matches"][0]["rule_id"] == "R3"
    incident = body["incidents"][0]
    assert incident["severity"] == "high"
    assert incident["scenario"] == "B"
    assert {str(event_id) for event_id in OUTBOUND_IDS} <= set(incident["event_ids"])


def test_scenario_c_creates_no_incident(client: TestClient) -> None:
    assert client.post("/api/scenarios/C/load").status_code == 200
    body = client.post("/api/incidents/detect").json()
    assert body["created"] == 0
    assert body["matches"] == []
    assert client.get("/api/incidents").json()["total"] == 0


def test_detect_does_not_duplicate_seeded_incidents(
    client: TestClient, seed_db: dict[str, int]
) -> None:
    first = client.post("/api/incidents/detect").json()
    second = client.post("/api/incidents/detect").json()
    assert first["created"] == 0
    assert first["updated"] == 2
    assert second["created"] == 0
    listed = client.get("/api/incidents").json()
    assert listed["total"] == 3
    brute = client.get(f"/api/incidents/{INCIDENT_BRUTE_ID}").json()
    assert brute["id"] == str(INCIDENT_BRUTE_ID)
    assert brute["severity"] == "critical"
