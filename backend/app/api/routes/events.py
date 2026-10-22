from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.events import EventListResponse, SecurityEventRead
from app.services import events as event_service

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=EventListResponse, summary="List security events")
def list_security_events(
    event_type: str | None = None,
    source_ip: str | None = None,
    username: str | None = None,
    scenario: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db),
) -> EventListResponse:
    items, total = event_service.list_events(
        session,
        event_type=event_type,
        source_ip=source_ip,
        username=username,
        scenario=scenario,
        limit=limit,
        offset=offset,
    )
    return EventListResponse(
        items=[SecurityEventRead.model_validate(item) for item in items],
        total=total,
    )
