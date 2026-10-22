import uuid

from fastapi.testclient import TestClient

from app.db.demo_data import INCIDENT_BRUTE_ID


def test_list_incidents_empty(client: TestClient) -> None:
    response = client.get("/api/incidents")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_list_incidents_returns_seeded_demo_data(
    client: TestClient, seed_db: dict[str, int]
) -> None:
    response = client.get("/api/incidents")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == seed_db["incidents"]
    titles = {item["title"] for item in body["items"]}
    assert "Brute-force login followed by success on demo_user" in titles
    brute = next(item for item in body["items"] if item["id"] == str(INCIDENT_BRUTE_ID))
    assert brute["severity"] == "critical"
    assert brute["status"] == "awaiting_approval"
    assert len(brute["event_ids"]) == 13


def test_get_incident_includes_event_ids(client: TestClient, seed_db: dict[str, int]) -> None:
    response = client.get(f"/api/incidents/{INCIDENT_BRUTE_ID}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(INCIDENT_BRUTE_ID)
    assert body["scenario"] == "A"
    assert len(body["event_ids"]) == 13


def test_get_incident_unknown_id_returns_json_404(client: TestClient) -> None:
    missing = uuid.UUID("00000000-0000-4000-8000-000000000099")
    response = client.get(f"/api/incidents/{missing}")
    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "not_found"
    assert body["code"] == "not_found"
    assert body["detail"] == "Incident not found"


def test_get_incident_invalid_uuid_returns_validation_error(client: TestClient) -> None:
    response = client.get("/api/incidents/not-a-uuid")
    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


def test_list_incidents_filters_by_severity(
    client: TestClient, seed_db: dict[str, int]
) -> None:
    response = client.get("/api/incidents", params={"severity": "low"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["severity"] == "low"


def test_list_incidents_rejects_unknown_status(client: TestClient) -> None:
    response = client.get("/api/incidents", params={"status": "unknown"})
    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


def test_list_incidents_paginates(client: TestClient, seed_db: dict[str, int]) -> None:
    response = client.get("/api/incidents", params={"limit": 1, "offset": 0})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == seed_db["incidents"]
    assert len(body["items"]) == 1
