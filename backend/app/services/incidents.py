import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Incident, IncidentEvent


def _event_ids(incident: Incident) -> list[uuid.UUID]:
    return [link.event_id for link in incident.event_links]


def list_incidents(
    session: Session,
    *,
    status: str | None = None,
    severity: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Incident], int]:
    filters = []
    if status:
        filters.append(Incident.status == status)
    if severity:
        filters.append(Incident.severity == severity)

    total = session.scalar(select(func.count()).select_from(Incident).where(*filters)) or 0
    items = list(
        session.scalars(
            select(Incident)
            .options(selectinload(Incident.event_links))
            .where(*filters)
            .order_by(Incident.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return items, total


def get_incident(session: Session, incident_id: uuid.UUID) -> Incident | None:
    return session.scalar(
        select(Incident)
        .options(selectinload(Incident.event_links))
        .where(Incident.id == incident_id)
    )


def incident_event_ids(incident: Incident) -> list[uuid.UUID]:
    return _event_ids(incident)


def link_incident_event(
    session: Session,
    incident_id: uuid.UUID,
    event_id: uuid.UUID,
    link_type: str = "evidence",
) -> IncidentEvent:
    link = IncidentEvent(
        incident_id=incident_id,
        event_id=event_id,
        link_type=link_type,
    )
    session.add(link)
    return link
