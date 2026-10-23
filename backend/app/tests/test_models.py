import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from app.db.models import AgentRun, Incident, IncidentEvent, ResponseAction, SecurityEvent


def test_metadata_registers_v1_tables() -> None:
    from app.db.base import Base

    assert set(Base.metadata.tables) == {
        "security_events",
        "incidents",
        "incident_events",
        "agent_runs",
        "response_actions",
    }


def test_sqlite_schema_matches_models(client: TestClient) -> None:
    inspector = inspect(client.app.state.engine)
    assert set(inspector.get_table_names()) == {
        "security_events",
        "incidents",
        "incident_events",
        "agent_runs",
        "response_actions",
    }


def test_event_incident_and_action_round_trip(client: TestClient) -> None:
    session = client.app.state.session_factory()
    try:
        event_id = uuid.uuid4()
        incident_id = uuid.uuid4()
        timestamp = datetime(2026, 10, 21, 10, 15, tzinfo=UTC)
        event = SecurityEvent(
            id=event_id,
            timestamp=timestamp,
            event_type="login_failure",
            source_ip="192.0.2.10",
            username="demo_user",
            hostname="demo-server-01",
            action="authentication_failed",
            source="linux_auth",
            raw_message="Failed password for demo_user from 192.0.2.10",
            scenario="A",
        )
        incident = Incident(
            id=incident_id,
            title="Brute-force login",
            severity="high",
            status="open",
            summary="Repeated failures from 192.0.2.10",
            scenario="A",
        )
        session.add_all([event, incident])
        session.flush()
        session.add(
            IncidentEvent(
                incident_id=incident_id,
                event_id=event_id,
                link_type="evidence",
            )
        )
        session.add(
            AgentRun(
                incident_id=incident_id,
                agent_name="investigation",
                status="completed",
                structured_output={"finding": "repeated failures"},
            )
        )
        session.add(
            ResponseAction(
                incident_id=incident_id,
                action_type="force_password_reset",
                target="demo_user",
                reason="Successful login after brute-force pattern",
                risk_level="medium",
                simulated=True,
            )
        )
        session.commit()

        stored_event = session.get(SecurityEvent, event_id)
        stored_incident = session.scalar(select(Incident).where(Incident.id == incident_id))
        assert stored_event is not None
        assert stored_event.timestamp.tzinfo is not None
        assert stored_event.timestamp.astimezone(UTC) == timestamp
        assert stored_incident is not None
        run = session.scalar(select(AgentRun).where(AgentRun.incident_id == incident_id))
        action = session.scalar(
            select(ResponseAction).where(ResponseAction.incident_id == incident_id)
        )
        assert run is not None
        assert run.structured_output == {"finding": "repeated failures"}
        assert action is not None
        assert action.simulated is True
        assert action.approval_status == "proposed"
    finally:
        session.close()


def test_incident_event_pair_is_unique(client: TestClient) -> None:
    from sqlalchemy.exc import IntegrityError

    session = client.app.state.session_factory()
    try:
        event = SecurityEvent(
            timestamp=datetime(2026, 10, 21, 8, 0, tzinfo=UTC),
            event_type="login_success",
            source="linux_auth",
            raw_message="Accepted publickey",
        )
        incident = Incident(
            title="Unique constraint check",
            severity="low",
            status="open",
            summary="Duplicate evidence link must fail",
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
        session.flush()
        session.add(
            IncidentEvent(
                incident_id=incident.id,
                event_id=event.id,
                link_type="evidence",
            )
        )
        try:
            session.flush()
            raise AssertionError("expected unique constraint on incident_events")
        except IntegrityError:
            session.rollback()
    finally:
        session.close()


def test_incident_event_rejects_missing_event_foreign_key(client: TestClient) -> None:
    from sqlalchemy.exc import IntegrityError

    session = client.app.state.session_factory()
    try:
        incident = Incident(
            title="Missing event FK",
            severity="low",
            status="open",
            summary="Link must reference an existing event",
        )
        session.add(incident)
        session.flush()
        session.add(
            IncidentEvent(
                incident_id=incident.id,
                event_id=uuid.uuid4(),
                link_type="evidence",
            )
        )
        try:
            session.flush()
            raise AssertionError("expected foreign key on incident_events.event_id")
        except IntegrityError:
            session.rollback()
    finally:
        session.close()


def test_deleting_incident_cascades_event_links(client: TestClient) -> None:
    from sqlalchemy import func

    session = client.app.state.session_factory()
    try:
        event = SecurityEvent(
            timestamp=datetime(2026, 10, 21, 8, 0, tzinfo=UTC),
            event_type="login_success",
            source="linux_auth",
            raw_message="Accepted publickey",
        )
        incident = Incident(
            title="Cascade check",
            severity="low",
            status="open",
            summary="Deleting an incident must remove evidence links",
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
        event_id = event.id
        session.delete(incident)
        session.commit()
        remaining_links = session.scalar(select(func.count()).select_from(IncidentEvent))
        assert remaining_links == 0
        assert session.get(SecurityEvent, event_id) is not None
    finally:
        session.close()
