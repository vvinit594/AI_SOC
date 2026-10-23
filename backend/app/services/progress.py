"""Investigation progress fan-out for SSE. Database rows are the source of truth."""

from __future__ import annotations

import json
import logging
import queue
import re
import threading
import uuid
from collections.abc import Callable, Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.agents.nodes import NODE_NAMES
from app.core.time import utc_now
from app.db.models import AgentRun
from app.schemas.investigations import InvestigationProgressEvent

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 0.2
HEARTBEAT_INTERVAL_SECONDS = 15.0

_SAFE_ERROR = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_TERMINAL = frozenset({"investigation_completed", "investigation_failed"})


def public_error(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if _SAFE_ERROR.fullmatch(text):
        return text
    return "Error"


class ProgressBroker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[uuid.UUID, list[queue.Queue[object]]] = {}

    def subscribe(self, investigation_id: uuid.UUID) -> queue.Queue[object]:
        waiter: queue.Queue[object] = queue.Queue(maxsize=32)
        with self._lock:
            self._subscribers.setdefault(investigation_id, []).append(waiter)
        return waiter

    def unsubscribe(self, investigation_id: uuid.UUID, waiter: queue.Queue[object]) -> None:
        with self._lock:
            holders = self._subscribers.get(investigation_id, [])
            if waiter in holders:
                holders.remove(waiter)
            if not holders:
                self._subscribers.pop(investigation_id, None)

    def notify(self, investigation_id: uuid.UUID) -> None:
        with self._lock:
            holders = list(self._subscribers.get(investigation_id, ()))
        for waiter in holders:
            try:
                waiter.put_nowait(True)
            except queue.Full:
                pass


broker = ProgressBroker()


def notify_progress(investigation_id: uuid.UUID) -> None:
    try:
        broker.notify(investigation_id)
    except Exception:
        logger.warning("Progress notify failed")


def events_from_runs(
    investigation_id: uuid.UUID, runs: list[AgentRun]
) -> list[InvestigationProgressEvent]:
    by_name = {row.agent_name: row for row in runs}
    events: list[InvestigationProgressEvent] = []
    any_failed = False
    all_terminal = bool(by_name)
    for name in NODE_NAMES:
        run = by_name.get(name)
        if run is None:
            all_terminal = False
            continue
        if run.status in {"running", "completed", "failed"}:
            events.append(
                InvestigationProgressEvent(
                    investigation_id=investigation_id,
                    event="node_started",
                    agent_name=name,  # type: ignore[arg-type]
                    status="running",
                    timestamp=run.started_at or utc_now(),
                    event_id=f"{name}:started",
                )
            )
        if run.status == "completed":
            events.append(
                InvestigationProgressEvent(
                    investigation_id=investigation_id,
                    event="node_completed",
                    agent_name=name,  # type: ignore[arg-type]
                    status="completed",
                    timestamp=run.completed_at or utc_now(),
                    event_id=f"{name}:completed",
                )
            )
        elif run.status == "failed":
            any_failed = True
            events.append(
                InvestigationProgressEvent(
                    investigation_id=investigation_id,
                    event="node_failed",
                    agent_name=name,  # type: ignore[arg-type]
                    status="failed",
                    timestamp=run.completed_at or utc_now(),
                    error=public_error(run.error),
                    event_id=f"{name}:failed",
                )
            )
        else:
            all_terminal = False
    if all_terminal:
        terminal = "investigation_failed" if any_failed else "investigation_completed"
        events.append(
            InvestigationProgressEvent(
                investigation_id=investigation_id,
                event=terminal,  # type: ignore[arg-type]
                status="failed" if any_failed else "completed",
                timestamp=utc_now(),
                event_id="workflow:failed" if any_failed else "workflow:completed",
            )
        )
    return events


def load_progress_events(
    session: Session, investigation_id: uuid.UUID
) -> list[InvestigationProgressEvent] | None:
    rows = list(
        session.scalars(select(AgentRun).where(AgentRun.investigation_id == investigation_id)).all()
    )
    if not rows:
        return None
    return events_from_runs(investigation_id, rows)


def format_sse(event: InvestigationProgressEvent) -> str:
    payload = event.model_dump(mode="json", exclude={"event_id"})
    return (
        f"id: {event.event_id}\nevent: {event.event}\ndata: {json.dumps(payload, default=str)}\n\n"
    )


def connected_event(investigation_id: uuid.UUID) -> InvestigationProgressEvent:
    return InvestigationProgressEvent(
        investigation_id=investigation_id,
        event="connected",
        status="connected",
        timestamp=utc_now(),
        event_id="connected",
    )


def iter_sse_events(
    session_factory: sessionmaker[Session],
    investigation_id: uuid.UUID,
    *,
    last_event_id: str | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> Iterator[str]:
    """Yield SSE chunks. Opens a short-lived session per snapshot; never holds a transaction."""
    emitted: set[str] = set()
    yield format_sse(connected_event(investigation_id))
    emitted.add("connected")
    waiter = broker.subscribe(investigation_id)
    idle = 0.0
    applied_cursor = last_event_id in {None, "", "connected"}
    try:
        while True:
            if should_stop is not None and should_stop():
                return
            session = session_factory()
            try:
                events = load_progress_events(session, investigation_id)
            finally:
                session.close()
            if events is None:
                return
            start = 0
            if not applied_cursor and last_event_id:
                ids = [item.event_id for item in events]
                if last_event_id in ids:
                    start = ids.index(last_event_id) + 1
                    emitted.update(ids[:start])
                applied_cursor = True
            else:
                applied_cursor = True
            for event in events[start:]:
                if event.event_id in emitted:
                    continue
                emitted.add(event.event_id)
                yield format_sse(event)
                idle = 0.0
                if event.event in _TERMINAL:
                    return
            try:
                waiter.get(timeout=POLL_INTERVAL_SECONDS)
            except queue.Empty:
                idle += POLL_INTERVAL_SECONDS
                if idle >= HEARTBEAT_INTERVAL_SECONDS:
                    yield ": heartbeat\n\n"
                    idle = 0.0
    finally:
        broker.unsubscribe(investigation_id, waiter)
