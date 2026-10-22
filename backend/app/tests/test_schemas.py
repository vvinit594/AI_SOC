from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.events import SecurityEventCreate
from app.schemas.incidents import IncidentCreate


def test_security_event_create_requires_timezone() -> None:
    with pytest.raises(ValidationError) as exc_info:
        SecurityEventCreate(
            timestamp=datetime(2026, 10, 21, 10, 15),
            event_type="login_failure",
            source="linux_auth",
            raw_message="Failed password",
        )
    assert "timezone" in str(exc_info.value)


def test_security_event_create_accepts_aware_utc() -> None:
    event = SecurityEventCreate(
        timestamp=datetime(2026, 10, 21, 10, 15, tzinfo=UTC),
        event_type="login_failure",
        source_ip="192.0.2.10",
        source="linux_auth",
        raw_message="Failed password for demo_user from 192.0.2.10",
        scenario="A",
    )
    assert event.timestamp.tzinfo is not None
    assert event.event_type == "login_failure"


def test_incident_create_rejects_unknown_severity() -> None:
    with pytest.raises(ValidationError):
        IncidentCreate(
            title="Invalid severity",
            severity="informational",  # type: ignore[arg-type]
            summary="Severity must be the frozen scale",
        )


def test_incident_create_defaults_open_status() -> None:
    incident = IncidentCreate(
        title="Routine morning logins",
        severity="low",
        summary="Business-hours activity",
        scenario="C",
    )
    assert incident.status == "open"
    assert incident.event_ids == []
