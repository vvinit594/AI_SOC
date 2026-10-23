from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.agents.graph import run_investigation_graph
from app.agents.nodes import NODE_NAMES
from app.core.config import Settings
from app.core.errors import exception_label
from app.core.time import utc_now
from app.db.models import AgentRun, Incident, ResponseAction
from app.schemas.enums import AgentName, AgentRunStatus
from app.schemas.investigations import (
    AgentRunRead,
    InvestigateResponse,
    InvestigationRead,
    RecommendedAction,
)
from app.services import incidents as incident_service
from app.services.incident_lock import lock_incident
from app.services.llm import build_llm_client
from app.services.progress import notify_progress
from app.services.threat_intel import build_threat_intel_client

logger = logging.getLogger(__name__)

_CLOSED = frozenset({"resolved", "dismissed"})
_IN_FLIGHT = frozenset({"queued", "running"})


class InvestigationError(ValueError):
    def __init__(self, detail: str, *, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class RunRecorder:
    def __init__(
        self, session: Session, investigation_id: uuid.UUID, incident_id: uuid.UUID
    ) -> None:
        self.session = session
        self.investigation_id = investigation_id
        self.incident_id = incident_id

    def start(self, agent_name: AgentName) -> AgentRun:
        run = self._row(agent_name)
        run.status = "running"
        run.started_at = utc_now()
        run.error = None
        self.session.commit()
        notify_progress(self.investigation_id)
        return run

    def complete(self, agent_name: AgentName, output: dict[str, Any]) -> AgentRun:
        run = self._row(agent_name)
        run.status = "completed"
        run.structured_output = output
        run.completed_at = utc_now()
        self.session.commit()
        notify_progress(self.investigation_id)
        return run

    def fail(self, agent_name: AgentName, error: str) -> AgentRun:
        run = self._row(agent_name)
        run.status = "failed"
        run.error = error
        run.completed_at = utc_now()
        self.session.commit()
        notify_progress(self.investigation_id)
        return run

    def _row(self, agent_name: AgentName) -> AgentRun:
        run = self.session.scalar(
            select(AgentRun).where(
                AgentRun.investigation_id == self.investigation_id,
                AgentRun.agent_name == agent_name,
            )
        )
        if run is None:
            raise InvestigationError(f"Missing agent run for {agent_name}", status_code=500)
        return run


def get_investigation(session: Session, investigation_id: uuid.UUID) -> InvestigationRead | None:
    rows = list(
        session.scalars(
            select(AgentRun)
            .where(AgentRun.investigation_id == investigation_id)
            .order_by(AgentRun.started_at.asc(), AgentRun.agent_name.asc())
        ).all()
    )
    if not rows:
        return None
    return _to_read(investigation_id, rows)


def start_investigation(
    session: Session,
    settings: Settings,
    incident_id: uuid.UUID,
    *,
    llm=None,
    intel=None,
) -> InvestigateResponse:
    incident = incident_service.get_incident(session, incident_id)
    if incident is None:
        raise InvestigationError("Incident not found", status_code=404)
    if incident.status in _CLOSED:
        raise InvestigationError("Closed incidents cannot be investigated", status_code=409)

    with lock_incident(session, incident_id):
        session.refresh(incident)
        if incident.status in _CLOSED:
            raise InvestigationError("Closed incidents cannot be investigated", status_code=409)

        existing = _latest_investigation(session, incident_id)
        if existing is not None and existing.status == "completed":
            return InvestigateResponse(investigation=existing, created=False)
        if existing is not None and existing.status in _IN_FLIGHT:
            _fail_open_nodes(session, existing.id, "StaleInvestigation")

        investigation_id = uuid.uuid4()
        recorder = RunRecorder(session, investigation_id, incident_id)
        try:
            _queue_nodes(session, investigation_id, incident_id)
            if incident.status == "open":
                incident.status = "investigating"
            session.commit()
            notify_progress(investigation_id)

            def persist_actions(actions: list[RecommendedAction]) -> None:
                _store_actions(session, incident_id, actions)

            run_investigation_graph(
                {"incident_id": str(incident_id), "investigation_id": str(investigation_id)},
                {
                    "configurable": {
                        "session": session,
                        "settings": settings,
                        "recorder": recorder,
                        "llm": build_llm_client(settings, llm),
                        "intel": build_threat_intel_client(settings, intel),
                        "incident": {
                            "id": str(incident.id),
                            "title": incident.title,
                            "severity": incident.severity,
                            "status": incident.status,
                            "summary": incident.summary,
                            "scenario": incident.scenario,
                        },
                        "persist_actions": persist_actions,
                    }
                },
            )
            loaded = get_investigation(session, investigation_id)
            assert loaded is not None
            if loaded.status == "completed" and incident.status == "investigating":
                incident.status = "awaiting_approval"
                session.commit()
                loaded = get_investigation(session, investigation_id)
                assert loaded is not None
            if loaded.status == "failed":
                _reopen_if_investigating(session, incident)
            notify_progress(investigation_id)
            return InvestigateResponse(investigation=loaded, created=True)
        except InvestigationError:
            raise
        except Exception as exc:
            logger.warning("Investigation workflow failed: %s", exception_label(exc))
            _fail_open_nodes(session, investigation_id, exception_label(exc))
            _reopen_if_investigating(session, incident)
            notify_progress(investigation_id)
            raise InvestigationError("Investigation workflow failed", status_code=500) from exc


def _queue_nodes(session: Session, investigation_id: uuid.UUID, incident_id: uuid.UUID) -> None:
    for name in NODE_NAMES:
        session.add(
            AgentRun(
                investigation_id=investigation_id,
                incident_id=incident_id,
                agent_name=name,
                status="queued",
                structured_output={},
            )
        )
    session.flush()


def _latest_investigation(session: Session, incident_id: uuid.UUID) -> InvestigationRead | None:
    rows = list(session.scalars(select(AgentRun).where(AgentRun.incident_id == incident_id)).all())
    if not rows:
        return None
    groups: dict[uuid.UUID, list[AgentRun]] = {}
    for row in rows:
        groups.setdefault(row.investigation_id, []).append(row)

    def _sort_key(investigation_id: uuid.UUID) -> tuple:
        members = groups[investigation_id]
        timestamps = [item.completed_at or item.started_at for item in members]
        latest = max((stamp for stamp in timestamps if stamp is not None), default=utc_now())
        return (latest, investigation_id)

    latest_id = max(groups, key=_sort_key)
    return get_investigation(session, latest_id)


def _to_read(investigation_id: uuid.UUID, rows: list[AgentRun]) -> InvestigationRead:
    statuses = {row.status for row in rows}
    status: AgentRunStatus
    if "failed" in statuses:
        status = "failed"
    elif "running" in statuses:
        status = "running"
    elif "queued" in statuses:
        status = "queued"
    else:
        status = "completed"
    sources = [
        str(row.structured_output.get("assessment_source"))
        for row in rows
        if isinstance(row.structured_output, dict)
    ]
    assessment = "llm" if "llm" in sources else "deterministic_rules"
    return InvestigationRead(
        id=investigation_id,
        incident_id=rows[0].incident_id,
        status=status,
        nodes=[AgentRunRead.model_validate(row) for row in rows],
        assessment_source=assessment,  # type: ignore[arg-type]
    )


def _store_actions(
    session: Session, incident_id: uuid.UUID, actions: list[RecommendedAction]
) -> None:
    session.execute(
        delete(ResponseAction).where(
            ResponseAction.incident_id == incident_id,
            ResponseAction.approval_status == "proposed",
            ResponseAction.execution_status == "not_executed",
            ResponseAction.simulated.is_(True),
        )
    )
    for action in actions:
        session.add(
            ResponseAction(
                incident_id=incident_id,
                action_type=action.action_type,
                target=action.target,
                reason=action.reason,
                risk_level=action.risk_level,
                approval_status="proposed",
                execution_status="not_executed",
                simulated=True,
            )
        )
    session.commit()


def _fail_open_nodes(session: Session, investigation_id: uuid.UUID, error: str) -> None:
    rows = list(
        session.scalars(select(AgentRun).where(AgentRun.investigation_id == investigation_id)).all()
    )
    now = utc_now()
    for row in rows:
        if row.status in {"queued", "running"}:
            row.status = "failed"
            row.error = error
            row.completed_at = now
    try:
        session.commit()
        notify_progress(investigation_id)
    except SQLAlchemyError:
        session.rollback()


def _reopen_if_investigating(session: Session, incident: Incident) -> None:
    if getattr(incident, "status", None) == "investigating":
        incident.status = "open"
        try:
            session.commit()
        except SQLAlchemyError:
            session.rollback()
