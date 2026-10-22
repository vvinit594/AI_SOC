import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.db.demo_data import BRUTE_SUCCESS_ID
from app.db.models import SecurityEvent


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


def test_list_events_rejects_unknown_scenario(client: TestClient) -> None:
    response = client.get("/api/events", params={"scenario": "Z"})
    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


def test_list_events_paginates_with_stable_id_order(
    client: TestClient, seed_db: dict[str, int]
) -> None:
    first = client.get("/api/events", params={"limit": 5, "offset": 0}).json()
    second = client.get("/api/events", params={"limit": 5, "offset": 5}).json()
    assert first["total"] == seed_db["events"]
    assert len(first["items"]) == 5
    assert len(second["items"]) == 5
    first_ids = [item["id"] for item in first["items"]]
    second_ids = [item["id"] for item in second["items"]]
    assert set(first_ids).isdisjoint(second_ids)
    timestamps = [item["timestamp"] for item in first["items"] + second["items"]]
    assert timestamps == sorted(timestamps)


def test_list_events_pages_identical_timestamps_by_id(client: TestClient) -> None:
    shared_ts = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
    event_ids = [
        uuid.UUID("aaaaaaaa-0001-4000-8000-000000000001"),
        uuid.UUID("aaaaaaaa-0002-4000-8000-000000000002"),
        uuid.UUID("aaaaaaaa-0003-4000-8000-000000000003"),
        uuid.UUID("aaaaaaaa-0004-4000-8000-000000000004"),
        uuid.UUID("aaaaaaaa-0005-4000-8000-000000000005"),
    ]
    insert_order = [event_ids[4], event_ids[2], event_ids[0], event_ids[3], event_ids[1]]
    session = client.app.state.session_factory()
    try:
        for event_id in insert_order:
            session.add(
                SecurityEvent(
                    id=event_id,
                    timestamp=shared_ts,
                    event_type="login_failure",
                    source_ip="192.0.2.10",
                    source="linux_auth",
                    raw_message=f"identical-timestamp event {event_id}",
                )
            )
        session.commit()
    finally:
        session.close()

    pages = [
        client.get("/api/events", params={"limit": 2, "offset": offset}).json()
        for offset in (0, 2, 4)
    ]
    paged_ids = [item["id"] for page in pages for item in page["items"]]
    expected_ids = [str(event_id) for event_id in event_ids]

    assert pages[0]["total"] == 5
    assert [len(page["items"]) for page in pages] == [2, 2, 1]
    assert paged_ids == expected_ids
    assert len(paged_ids) == len(set(paged_ids))
    assert set(paged_ids) == set(expected_ids)
    first_timestamp = pages[0]["items"][0]["timestamp"]
    for page in pages:
        for item in page["items"]:
            assert item["timestamp"] == first_timestamp
