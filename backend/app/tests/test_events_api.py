from fastapi.testclient import TestClient

from app.db.demo_data import BRUTE_SUCCESS_ID


def test_list_events_empty(client: TestClient) -> None:
    response = client.get("/api/events")
    assert response.status_code == 200
    body = response.json()
    assert body == {"items": [], "total": 0}


def test_list_events_returns_seeded_demo_data(client: TestClient, seed_db: dict[str, int]) -> None:
    response = client.get("/api/events")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == seed_db["events"]
    assert len(body["items"]) == seed_db["events"]
    types = {item["event_type"] for item in body["items"]}
    assert "login_failure" in types
    assert "outbound_connection" in types
    allowed_prefixes = ("192.0.2.", "198.51.100.", "203.0.113.")
    for item in body["items"]:
        for field in ("source_ip", "destination_ip"):
            value = item[field]
            if value is not None:
                assert value.startswith(allowed_prefixes)
    ids = {item["id"] for item in body["items"]}
    assert str(BRUTE_SUCCESS_ID) in ids


def test_list_events_filters_by_scenario(client: TestClient, seed_db: dict[str, int]) -> None:
    response = client.get("/api/events", params={"scenario": "A"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 13
    assert all(item["scenario"] == "A" for item in body["items"])


def test_list_events_filters_by_source_ip(client: TestClient, seed_db: dict[str, int]) -> None:
    response = client.get("/api/events", params={"source_ip": "192.0.2.10"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 13
    assert all(item["source_ip"] == "192.0.2.10" for item in body["items"])


def test_list_events_rejects_oversized_limit(client: TestClient) -> None:
    response = client.get("/api/events", params={"limit": 501})
    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"
