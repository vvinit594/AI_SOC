from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.demo_data import INCIDENT_BRUTE_ID, demo_events, demo_incidents
from app.db.models import Incident, IncidentEvent, SecurityEvent
from app.db.seed import seed_demo_data


def test_seed_is_idempotent(client: TestClient) -> None:
    session = client.app.state.session_factory()
    try:
        first = seed_demo_data(session)
        second = seed_demo_data(session)
        assert first == second
        assert first["events"] == len(demo_events())
        assert first["incidents"] == len(demo_incidents())

        event_count = session.scalar(select(func.count()).select_from(SecurityEvent))
        incident_count = session.scalar(select(func.count()).select_from(Incident))
        link_count = session.scalar(select(func.count()).select_from(IncidentEvent))
        assert event_count == len(demo_events())
        assert incident_count == len(demo_incidents())
        expected_links = sum(len(item["event_ids"]) for item in demo_incidents())
        assert link_count == expected_links

        brute = session.get(Incident, INCIDENT_BRUTE_ID)
        assert brute is not None
        assert brute.severity == "critical"
    finally:
        session.close()


def test_demo_data_uses_documentation_ips() -> None:
    allowed_prefixes = ("192.0.2.", "198.51.100.", "203.0.113.")
    for event in demo_events():
        for field in ("source_ip", "destination_ip"):
            value = event[field]
            if value is None:
                continue
            assert str(value).startswith(allowed_prefixes)
