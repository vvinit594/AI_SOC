import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import SecurityEvent


def list_events(
    session: Session,
    *,
    event_type: str | None = None,
    source_ip: str | None = None,
    username: str | None = None,
    scenario: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[SecurityEvent], int]:
    filters = []
    if event_type:
        filters.append(SecurityEvent.event_type == event_type)
    if source_ip:
        filters.append(SecurityEvent.source_ip == source_ip)
    if username:
        filters.append(SecurityEvent.username == username)
    if scenario:
        filters.append(SecurityEvent.scenario == scenario)

    total = session.scalar(select(func.count()).select_from(SecurityEvent).where(*filters)) or 0
    items = list(
        session.scalars(
            select(SecurityEvent)
            .where(*filters)
            .order_by(SecurityEvent.timestamp.asc(), SecurityEvent.id.asc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return items, total


def get_event(session: Session, event_id: uuid.UUID) -> SecurityEvent | None:
    return session.get(SecurityEvent, event_id)


def upsert_events(session: Session, payloads: list[dict[str, object]]) -> list[uuid.UUID]:
    ids: list[uuid.UUID] = []
    for payload in payloads:
        fields = dict(payload)
        event_id = fields.get("id")
        if event_id is None:
            fields["id"] = uuid.uuid4()
        merged = session.merge(SecurityEvent(**fields))
        ids.append(merged.id)
    session.commit()
    return ids
