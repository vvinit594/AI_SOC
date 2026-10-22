import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models import Incident
from app.db.session import get_db
from app.schemas.enums import IncidentStatus, Severity
from app.schemas.incidents import IncidentListResponse, IncidentRead
from app.services import incidents as incident_service

router = APIRouter(prefix="/incidents", tags=["incidents"])


def _to_read(incident: Incident) -> IncidentRead:
    payload = IncidentRead.model_validate(incident)
    event_ids = incident_service.incident_event_ids(incident)
    return payload.model_copy(update={"event_ids": event_ids})


@router.get("", response_model=IncidentListResponse, summary="List incidents")
def list_incidents(
    status: IncidentStatus | None = None,
    severity: Severity | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db),
) -> IncidentListResponse:
    items, total = incident_service.list_incidents(
        session,
        status=status,
        severity=severity,
        limit=limit,
        offset=offset,
    )
    return IncidentListResponse(items=[_to_read(item) for item in items], total=total)


@router.get("/{incident_id}", response_model=IncidentRead, summary="Get incident details")
def get_incident(
    incident_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> IncidentRead:
    incident = incident_service.get_incident(session, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return _to_read(incident)
