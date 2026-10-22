"""Idempotent seed of the three demo scenarios into PostgreSQL (or the test database)."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.demo_data import demo_events, demo_incidents
from app.db.models import Incident, IncidentEvent, SecurityEvent
from app.db.session import create_engine_from_settings, create_session_factory

logger = logging.getLogger(__name__)


def seed_demo_data(session: Session) -> dict[str, int]:
    events = demo_events()
    incidents = demo_incidents()

    for payload in events:
        session.merge(SecurityEvent(**payload))
    session.flush()

    for payload in incidents:
        event_ids = list(payload["event_ids"])
        fields = {key: value for key, value in payload.items() if key != "event_ids"}
        session.merge(Incident(**fields))
        for event_id in event_ids:
            existing = session.scalar(
                select(IncidentEvent).where(
                    IncidentEvent.incident_id == payload["id"],
                    IncidentEvent.event_id == event_id,
                )
            )
            if existing is None:
                session.add(
                    IncidentEvent(
                        incident_id=payload["id"],
                        event_id=event_id,
                        link_type="evidence",
                    )
                )

    session.commit()
    return {"events": len(events), "incidents": len(incidents)}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    engine = create_engine_from_settings(settings)
    factory = create_session_factory(engine)
    session = factory()
    try:
        summary = seed_demo_data(session)
        logger.info("Seeded demo data: %s", summary)
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    main()
