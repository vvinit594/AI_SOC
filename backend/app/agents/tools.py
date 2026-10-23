"""Bounded agent tools. No shell, no raw SQL, no arbitrary HTTP."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.agents.attck import AttackTechnique, get_attack_technique
from app.core.errors import exception_label
from app.core.time import utc_now
from app.db.models import SecurityEvent
from app.schemas.investigations import ThreatIntelRecord
from app.services import incidents as incident_service
from app.services.threat_intel import ThreatIntelClient, is_documentation_ip

logger = logging.getLogger(__name__)


def search_incident_events(session: Session, incident_id: uuid.UUID) -> list[dict[str, Any]]:
    incident = incident_service.get_incident(session, incident_id)
    if incident is None:
        return []
    event_ids = incident_service.incident_event_ids(incident)
    events: list[SecurityEvent] = []
    for event_id in event_ids:
        event = session.get(SecurityEvent, event_id)
        if event is not None:
            events.append(event)
    events.sort(key=lambda item: (item.timestamp, item.id))
    return [_event_payload(event) for event in events]


def lookup_ip_reputation(client: ThreatIntelClient, ip: str) -> ThreatIntelRecord:
    try:
        record = client.lookup_ip(ip)
    except Exception as exc:
        logger.warning("IP reputation lookup failed: %s", exception_label(exc))
        record = ThreatIntelRecord(
            indicator=ip,
            status="unavailable",
            provider="unknown",
            source="lookup",
            fetched_at=utc_now(),
            summary="Reputation lookup failed; result is unavailable.",
        )
    if not is_documentation_ip(ip):
        return record
    summary = record.summary
    note = (
        " Indicator is in an RFC 5737 documentation range and must not be treated "
        "as a confirmed malicious internet host."
    )
    if note.strip() not in summary:
        summary = summary + note
    updates: dict[str, Any] = {"summary": summary}
    if record.status == "ok":
        updates["classification"] = "documentation"
    return record.model_copy(update=updates)


def get_attack_technique_tool(technique_id: str) -> AttackTechnique | None:
    return get_attack_technique(technique_id)


def extract_ip_indicators(events: list[dict[str, Any]]) -> list[str]:
    seen: dict[str, None] = {}
    for event in events:
        for key in ("source_ip", "destination_ip"):
            value = event.get(key)
            if isinstance(value, str) and value.strip():
                seen.setdefault(value.strip(), None)
    return list(seen)


def _event_payload(event: SecurityEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "timestamp": event.timestamp.isoformat(),
        "event_type": event.event_type,
        "source_ip": event.source_ip,
        "destination_ip": event.destination_ip,
        "username": event.username,
        "hostname": event.hostname,
        "action": event.action,
        "source": event.source,
        "raw_message": event.raw_message,
        "scenario": event.scenario,
    }
