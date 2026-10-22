import json
import uuid

from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.demo_data import BRUTE_SUCCESS_ID, demo_events
from app.main import create_app
from app.tests.helpers import build_settings


def _client_with_settings(**overrides: object) -> TestClient:
    settings = build_settings(**overrides)
    application = create_app(settings)
    Base.metadata.create_all(application.state.engine)
    return TestClient(application)

VALID_EVENT = {
    "timestamp": "2026-10-21T12:00:00Z",
    "event_type": "login_failure",
    "source_ip": "192.0.2.10",
    "username": "demo_user",
    "hostname": "demo-server-01",
    "action": "authentication_failed",
    "source": "linux_auth",
    "raw_message": "Failed password for demo_user from 192.0.2.10",
}


def _upload(client: TestClient, name: str, content: str, content_type: str):
    return client.post(
        "/api/logs/upload",
        files={"file": (name, content.encode("utf-8"), content_type)},
    )


def test_json_upload_persists_valid_event(client: TestClient) -> None:
    event_id = str(uuid.uuid4())
    response = _upload(
        client,
        "events.json",
        json.dumps([{**VALID_EVENT, "id": event_id}]),
        "application/json",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] == 1
    assert body["rejected"] == 0
    assert body["event_ids"] == [event_id]

    listed = client.get("/api/events").json()
    assert listed["total"] == 1
    assert listed["items"][0]["id"] == event_id
    assert listed["items"][0]["source_ip"] == "192.0.2.10"


def test_csv_upload_persists_valid_event(client: TestClient) -> None:
    csv_body = (
        "timestamp,event_type,source_ip,username,source,raw_message\n"
        "2026-10-21T12:00:00Z,login_success,192.0.2.40,j.patel,linux_auth,"
        "Accepted publickey for j.patel\n"
    )
    response = _upload(client, "events.csv", csv_body, "text/csv")
    assert response.status_code == 200
    assert response.json()["accepted"] == 1
    listed = client.get("/api/events").json()
    assert listed["total"] == 1
    assert listed["items"][0]["event_type"] == "login_success"


def test_json_upload_accepts_camel_case_aliases(client: TestClient) -> None:
    payload = {
        "timestamp": "2026-10-21T12:00:00Z",
        "eventType": "outbound_connection",
        "sourceIp": "192.0.2.50",
        "destinationIp": "198.51.100.88",
        "source": "firewall",
        "rawMessage": "Outbound TCP 192.0.2.50 -> 198.51.100.88",
    }
    response = _upload(client, "events.json", json.dumps([payload]), "application/json")
    assert response.status_code == 200
    item = client.get("/api/events").json()["items"][0]
    assert item["event_type"] == "outbound_connection"
    assert item["destination_ip"] == "198.51.100.88"


def test_mixed_upload_persists_only_valid_records(client: TestClient) -> None:
    payload = [
        VALID_EVENT,
        {
            "timestamp": "2026-10-21T12:01:00",
            "event_type": "login_failure",
            "source": "linux_auth",
            "raw_message": "naive timestamp must be rejected",
        },
    ]
    response = _upload(client, "events.json", json.dumps(payload), "application/json")
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] == 1
    assert body["rejected"] == 1
    assert body["errors"][0]["index"] == 1
    assert client.get("/api/events").json()["total"] == 1


def test_all_invalid_records_persist_nothing(client: TestClient) -> None:
    payload = [{"event_type": "login_failure", "source": "linux_auth", "raw_message": "no ts"}]
    response = _upload(client, "events.json", json.dumps(payload), "application/json")
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "ingest_error"
    assert body["errors"][0]["index"] == 0
    assert client.get("/api/events").json()["total"] == 0


def test_malformed_json_is_rejected(client: TestClient) -> None:
    response = _upload(client, "events.json", "{not-json", "application/json")
    assert response.status_code == 400
    assert response.json()["error"] == "http_error"
    assert client.get("/api/events").json()["total"] == 0


def test_unsupported_file_type_is_rejected(client: TestClient) -> None:
    response = _upload(client, "events.txt", "hello", "text/plain")
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_empty_upload_is_rejected(client: TestClient) -> None:
    response = _upload(client, "events.json", "   ", "application/json")
    assert response.status_code == 400
    assert response.json()["detail"] == "Upload is empty"


def test_too_many_events_are_rejected_without_persist() -> None:
    with _client_with_settings(max_events_per_upload=1) as client:
        payload = [VALID_EVENT, {**VALID_EVENT, "timestamp": "2026-10-21T12:01:00Z"}]
        response = _upload(client, "events.json", json.dumps(payload), "application/json")
        assert response.status_code == 400
        assert "more than 1 events" in response.json()["detail"]
        assert client.get("/api/events").json()["total"] == 0


def test_oversize_upload_is_rejected() -> None:
    with _client_with_settings(max_upload_size_mb=1) as client:
        oversized = b"{" + (b"a" * (1024 * 1024 + 1))
        response = client.post(
            "/api/logs/upload",
            files={"file": ("events.json", oversized, "application/json")},
        )
        assert response.status_code == 413
        assert response.json()["error"] == "http_error"
        assert client.get("/api/events").json()["total"] == 0


def test_duplicate_id_upload_is_idempotent(client: TestClient) -> None:
    event_id = str(uuid.uuid4())
    payload = json.dumps([{**VALID_EVENT, "id": event_id}])
    first = _upload(client, "events.json", payload, "application/json")
    second = _upload(client, "events.json", payload, "application/json")
    assert first.status_code == 200
    assert second.status_code == 200
    assert client.get("/api/events").json()["total"] == 1


def test_load_scenario_a_persists_demo_events(client: TestClient) -> None:
    expected = [event for event in demo_events() if event["scenario"] == "A"]
    response = client.post("/api/scenarios/A/load")
    assert response.status_code == 200
    body = response.json()
    assert body["scenario"] == "A"
    assert body["accepted"] == len(expected)
    assert str(BRUTE_SUCCESS_ID) in body["event_ids"]
    listed = client.get("/api/events", params={"scenario": "A"}).json()
    assert listed["total"] == len(expected)
    assert client.get("/api/incidents").json()["total"] == 0


def test_load_scenario_is_idempotent(client: TestClient) -> None:
    first = client.post("/api/scenarios/C/load")
    second = client.post("/api/scenarios/C/load")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["accepted"] == second.json()["accepted"]
    assert client.get("/api/events", params={"scenario": "C"}).json()["total"] == 5


def test_unknown_scenario_is_rejected(client: TestClient) -> None:
    response = client.post("/api/scenarios/Z/load")
    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"

