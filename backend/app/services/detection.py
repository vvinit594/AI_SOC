from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Incident, IncidentEvent, SecurityEvent
from app.schemas.detection import DetectionMatch, DetectResponse
from app.schemas.enums import Severity
from app.schemas.incidents import IncidentRead
from app.services import incidents as incident_service

INCIDENT_NAMESPACE = uuid.UUID("a15ec005-0000-4000-8000-000000000005")


@dataclass
class _Match:
    rule_id: str
    severity: Severity
    event_ids: list[uuid.UUID]
    reason: str
    matched_threshold: str
    timestamp: datetime


@dataclass
class _Plan:
    fingerprint: str
    title: str
    severity: Severity
    summary: str
    scenario: str | None
    created_at: datetime
    event_ids: list[uuid.UUID]
    matches: list[_Match] = field(default_factory=list)

    @property
    def incident_id(self) -> uuid.UUID:
        return uuid.uuid5(INCIDENT_NAMESPACE, self.fingerprint)


def detect_incidents(session: Session, settings: Settings) -> DetectResponse:
    events = list(
        session.scalars(
            select(SecurityEvent).order_by(SecurityEvent.timestamp.asc(), SecurityEvent.id.asc())
        ).all()
    )
    plans = _build_plans(events, settings)
    created = 0
    updated = 0
    incidents: list[Incident] = []
    api_matches: list[DetectionMatch] = []

    for plan in plans:
        incident = _existing_incident(session, plan)
        if incident is None:
            incident = Incident(
                id=plan.incident_id,
                title=plan.title,
                severity=plan.severity,
                status="open",
                summary=plan.summary,
                scenario=plan.scenario,
                created_at=plan.created_at,
            )
            session.add(incident)
            session.flush()
            created += 1
        else:
            incident.title = plan.title
            incident.severity = plan.severity
            incident.summary = plan.summary
            if plan.scenario and not incident.scenario:
                incident.scenario = plan.scenario
            updated += 1
        _ensure_links(session, incident.id, plan.event_ids)
        session.flush()
        loaded = incident_service.get_incident(session, incident.id)
        assert loaded is not None
        incidents.append(loaded)
        for match in plan.matches:
            api_matches.append(
                DetectionMatch(
                    rule_id=match.rule_id,
                    severity=match.severity,
                    event_ids=match.event_ids,
                    reason=match.reason,
                    matched_threshold=match.matched_threshold,
                    timestamp=match.timestamp,
                    incident_id=loaded.id,
                )
            )

    try:
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise
    return DetectResponse(
        matches=api_matches,
        incidents=[_to_read(item) for item in incidents],
        created=created,
        updated=updated,
    )


def _to_read(incident: Incident) -> IncidentRead:
    payload = IncidentRead.model_validate(incident)
    return payload.model_copy(update={"event_ids": incident_service.incident_event_ids(incident)})


def _existing_incident(session: Session, plan: _Plan) -> Incident | None:
    by_id = session.get(Incident, plan.incident_id)
    if by_id is not None:
        return by_id
    if not plan.event_ids:
        return None
    links = list(
        session.scalars(
            select(IncidentEvent).where(IncidentEvent.event_id.in_(plan.event_ids))
        ).all()
    )
    if not links:
        return None
    counts: dict[uuid.UUID, int] = defaultdict(int)
    for link in links:
        counts[link.incident_id] += 1
    best_id = max(counts, key=lambda key: counts[key])
    return session.get(Incident, best_id)


def _ensure_links(session: Session, incident_id: uuid.UUID, event_ids: list[uuid.UUID]) -> None:
    existing = set(
        session.scalars(
            select(IncidentEvent.event_id).where(IncidentEvent.incident_id == incident_id)
        ).all()
    )
    for event_id in event_ids:
        if event_id not in existing:
            incident_service.link_incident_event(session, incident_id, event_id)


def _build_plans(events: list[SecurityEvent], settings: Settings) -> list[_Plan]:
    auth_window = timedelta(minutes=settings.rule_auth_failure_window_minutes)
    outbound_window = timedelta(minutes=settings.rule_outbound_window_minutes)
    auth_n = settings.rule_auth_failure_threshold
    outbound_m = settings.rule_outbound_connection_threshold
    seeded = settings.seeded_suspicious_ips

    plans = [
        *_auth_plans(events, auth_n, auth_window),
        *_outbound_plans(events, outbound_m, outbound_window, seeded),
    ]
    return plans


def _auth_plans(
    events: list[SecurityEvent],
    threshold: int,
    window: timedelta,
) -> list[_Plan]:
    failures = [event for event in events if event.event_type == "login_failure"]
    clusters: list[list[SecurityEvent]] = []
    by_ip: dict[str, list[SecurityEvent]] = defaultdict(list)
    by_user: dict[str, list[SecurityEvent]] = defaultdict(list)
    for event in failures:
        if event.source_ip:
            by_ip[event.source_ip].append(event)
        if event.username:
            by_user[event.username].append(event)
    for group in (*by_ip.values(), *by_user.values()):
        clusters.extend(_cluster_by_window(group, threshold, window))
    merged = _merge_overlapping(clusters)

    successes = [event for event in events if event.event_type == "login_success"]
    plans: list[_Plan] = []
    for cluster in merged:
        event_ids = [event.id for event in cluster]
        source_ips = sorted({event.source_ip for event in cluster if event.source_ip})
        usernames = sorted({event.username for event in cluster if event.username})
        pairs = {
            (event.source_ip, event.username)
            for event in cluster
            if event.source_ip and event.username
        }
        start = cluster[0].timestamp
        end = cluster[-1].timestamp
        follow_on = [
            event
            for event in successes
            if (event.source_ip, event.username) in pairs
            and start <= event.timestamp <= end + window
        ]
        rules = ["R1"]
        severity: Severity = "high"
        if follow_on:
            rules.append("R2")
            severity = "critical"
            event_ids.extend(event.id for event in follow_on)
        entity = source_ips[0] if source_ips else usernames[0]
        user_label = usernames[0] if usernames else "unknown user"
        r1_reason = (
            f"{len(cluster)} login_failure events for {user_label} "
            f"from {entity} within {int(window.total_seconds() // 60)} minutes"
        )
        matches = [
            _Match(
                rule_id="R1",
                severity="high",
                event_ids=[event.id for event in cluster],
                reason=r1_reason,
                matched_threshold=(
                    f"{len(cluster)}>={threshold}/{int(window.total_seconds() // 60)}m"
                ),
                timestamp=end,
            )
        ]
        summary = f"R1: {r1_reason}. ATT&CK T1110 Brute Force."
        title = f"Repeated authentication failures from {entity}"
        if follow_on:
            r2_reason = (
                f"login_success for {user_label} from {entity} within "
                f"{int(window.total_seconds() // 60)} minutes after the R1 match"
            )
            matches.append(
                _Match(
                    rule_id="R2",
                    severity="critical",
                    event_ids=[event.id for event in follow_on],
                    reason=r2_reason,
                    matched_threshold=f"R1 then success/{int(window.total_seconds() // 60)}m",
                    timestamp=follow_on[-1].timestamp,
                )
            )
            summary = (
                f"R1: {r1_reason}. R2: {r2_reason}. "
                "ATT&CK T1110 Brute Force, T1078 Valid Accounts."
            )
            title = f"Brute-force login followed by success on {user_label}"
        scenario = _shared_scenario(cluster + follow_on)
        fingerprint = f"{'+'.join(rules)}|{entity}|{start.astimezone(UTC).isoformat()}"
        plans.append(
            _Plan(
                fingerprint=fingerprint,
                title=title,
                severity=severity,
                summary=summary,
                scenario=scenario,
                created_at=end if not follow_on else follow_on[-1].timestamp,
                event_ids=_unique_ids(event_ids),
                matches=matches,
            )
        )
    return plans


def _outbound_plans(
    events: list[SecurityEvent],
    threshold: int,
    window: timedelta,
    seeded: set[str],
) -> list[_Plan]:
    outbound = [
        event
        for event in events
        if event.event_type == "outbound_connection" and event.destination_ip
    ]
    grouped: dict[tuple[str, str], list[SecurityEvent]] = defaultdict(list)
    for event in outbound:
        host = event.hostname or event.source_ip or "unknown-host"
        grouped[(host, event.destination_ip)].append(event)

    plans: list[_Plan] = []
    for (host, dest_ip), group in grouped.items():
        indicator_hit = dest_ip in seeded
        clusters = _cluster_by_window(group, threshold, window)
        if indicator_hit and not clusters:
            clusters = [sorted(group, key=lambda event: (event.timestamp, event.id))]
        elif indicator_hit:
            clusters = [_merge_overlapping([*clusters, group])[0]]
        for cluster in clusters:
            count = len(cluster)
            volume_hit = count >= threshold
            if not volume_hit and not indicator_hit:
                continue
            severity: Severity = "high" if volume_hit else "medium"
            minutes = int(window.total_seconds() // 60)
            reason_parts = []
            rules = []
            if volume_hit:
                rules.append("R3")
                reason_parts.append(
                    f"{count} outbound connections from {host} to {dest_ip} "
                    f"within {minutes} minutes"
                )
            if indicator_hit:
                if "R3" not in rules:
                    rules.append("R3")
                reason_parts.append(f"{dest_ip} matches a seeded suspicious indicator")
            reason = "; ".join(reason_parts)
            start = cluster[0].timestamp
            end = cluster[-1].timestamp
            event_ids = [event.id for event in cluster]
            fingerprint = f"R3|{host}|{dest_ip}|{start.astimezone(UTC).isoformat()}"
            plans.append(
                _Plan(
                    fingerprint=fingerprint,
                    title=f"Repeated outbound connections to {dest_ip}",
                    severity=severity,
                    summary=f"R3: {reason}. ATT&CK T1071 Application Layer Protocol.",
                    scenario=_shared_scenario(cluster),
                    created_at=end,
                    event_ids=event_ids,
                    matches=[
                        _Match(
                            rule_id="R3",
                            severity=severity,
                            event_ids=event_ids,
                            reason=reason,
                            matched_threshold=(
                                f"{count}>={threshold}/{minutes}m"
                                + ("+indicator" if indicator_hit else "")
                            ),
                            timestamp=end,
                        )
                    ],
                )
            )
    return plans


def _cluster_by_window(
    events: list[SecurityEvent],
    min_count: int,
    window: timedelta,
) -> list[list[SecurityEvent]]:
    if len(events) < min_count:
        return []
    ordered = sorted(events, key=lambda event: (event.timestamp, event.id))
    windows: list[list[SecurityEvent]] = []
    left = 0
    for right, event in enumerate(ordered):
        while event.timestamp - ordered[left].timestamp > window:
            left += 1
        if right - left + 1 >= min_count:
            windows.append(ordered[left : right + 1])
    return _merge_overlapping(windows)


def _merge_overlapping(windows: list[list[SecurityEvent]]) -> list[list[SecurityEvent]]:
    if not windows:
        return []
    merged: list[dict[uuid.UUID, SecurityEvent]] = []
    for window in windows:
        ids = {event.id for event in window}
        if merged and ids & set(merged[-1]):
            for event in window:
                merged[-1][event.id] = event
        else:
            merged.append({event.id: event for event in window})
    return [
        sorted(group.values(), key=lambda event: (event.timestamp, event.id)) for group in merged
    ]


def _shared_scenario(events: list[SecurityEvent]) -> str | None:
    scenarios = {event.scenario for event in events if event.scenario}
    if len(scenarios) == 1:
        return scenarios.pop()
    return None


def _unique_ids(event_ids: list[uuid.UUID]) -> list[uuid.UUID]:
    seen: dict[uuid.UUID, None] = {}
    for event_id in event_ids:
        seen.setdefault(event_id, None)
    return list(seen)
