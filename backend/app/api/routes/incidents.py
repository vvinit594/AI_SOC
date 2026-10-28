import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.auth import AnalystAuthError, resolve_actor
from app.core.config import Settings, get_settings
from app.db.models import Incident
from app.db.session import get_db
from app.schemas.actions import ResponseActionRead
from app.schemas.audit import AuditLogListResponse, AuditLogRead
from app.schemas.detection import DetectResponse
from app.schemas.enums import IncidentStatus, Severity
from app.schemas.incidents import IncidentListResponse, IncidentRead
from app.schemas.investigations import InvestigateResponse
from app.services import incidents as incident_service
from app.services.audit import AuditError, list_incident_audit_logs
from app.services.detection import detect_incidents
from app.services.investigations import InvestigationError, start_investigation
from app.services.reports import ReportError, build_incident_report, content_disposition

router = APIRouter(prefix="/incidents", tags=["incidents"])


def _to_read(incident: Incident, *, include_actions: bool = False) -> IncidentRead:
    actions: list[ResponseActionRead] = []
    if include_actions:
        actions = [
            ResponseActionRead.model_validate(row)
            for row in sorted(
                incident.response_actions,
                key=lambda item: (item.created_at, item.id),
            )
        ]
    return IncidentRead.model_validate(
        {
            "id": incident.id,
            "title": incident.title,
            "severity": incident.severity,
            "status": incident.status,
            "summary": incident.summary,
            "scenario": incident.scenario,
            "created_at": incident.created_at,
            "event_ids": incident_service.incident_event_ids(incident),
            "actions": actions,
        }
    )


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


@router.post("/detect", response_model=DetectResponse, summary="Run detection rules")
def run_detection(
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DetectResponse:
    return detect_incidents(session, settings)


@router.post(
    "/{incident_id}/investigate",
    response_model=InvestigateResponse,
    summary="Run the LangGraph investigation workflow",
)
def investigate_incident(
    incident_id: uuid.UUID,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> InvestigateResponse:
    try:
        return start_investigation(session, settings, incident_id)
    except InvestigationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get(
    "/{incident_id}/audit-logs",
    response_model=AuditLogListResponse,
    summary="List persisted audit events for an incident",
)
def get_incident_audit_logs(
    incident_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    authorization: Annotated[str | None, Header()] = None,
) -> AuditLogListResponse:
    try:
        resolve_actor(settings, authorization)
        items, total = list_incident_audit_logs(session, incident_id, limit=limit, offset=offset)
    except AnalystAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except AuditError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return AuditLogListResponse(
        items=[AuditLogRead.model_validate(item) for item in items],
        total=total,
    )


@router.get(
    "/{incident_id}/report",
    response_class=HTMLResponse,
    summary="Download a self-contained HTML incident report",
)
def download_incident_report(
    incident_id: uuid.UUID,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    authorization: Annotated[str | None, Header()] = None,
) -> HTMLResponse:
    try:
        resolve_actor(settings, authorization)
        html_doc, filename = build_incident_report(session, incident_id)
    except AnalystAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except ReportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return HTMLResponse(
        content=html_doc,
        headers={
            "Content-Disposition": content_disposition(filename),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.get("/{incident_id}", response_model=IncidentRead, summary="Get incident details")
def get_incident(
    incident_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> IncidentRead:
    incident = incident_service.get_incident(session, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return _to_read(incident, include_actions=True)
