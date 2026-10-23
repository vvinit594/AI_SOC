"""Serialize investigation work per incident across commits.

PostgreSQL uses session-level advisory locks so the lock survives the per-node
commits. SQLite (and in-process callers) use a threading lock.
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_GUARD = threading.Lock()
_THREAD_LOCKS: dict[uuid.UUID, threading.Lock] = {}


def _thread_lock(incident_id: uuid.UUID) -> threading.Lock:
    with _GUARD:
        return _THREAD_LOCKS.setdefault(incident_id, threading.Lock())


def _advisory_keys(incident_id: uuid.UUID) -> tuple[int, int]:
    bits = incident_id.int
    return _i32(bits >> 96), _i32(bits & 0xFFFFFFFF)


def _i32(value: int) -> int:
    value &= 0xFFFFFFFF
    if value >= 2**31:
        value -= 2**32
    return value


@contextmanager
def lock_incident(session: Session, incident_id: uuid.UUID) -> Iterator[None]:
    lock = _thread_lock(incident_id)
    lock.acquire()
    pg_keys: tuple[int, int] | None = None
    try:
        bind = session.get_bind()
        if bind is not None and bind.dialect.name == "postgresql":
            pg_keys = _advisory_keys(incident_id)
            session.execute(
                text("SELECT pg_advisory_lock(:k1, :k2)"),
                {"k1": pg_keys[0], "k2": pg_keys[1]},
            )
        yield
    finally:
        if pg_keys is not None:
            try:
                session.execute(
                    text("SELECT pg_advisory_unlock(:k1, :k2)"),
                    {"k1": pg_keys[0], "k2": pg_keys[1]},
                )
            except SQLAlchemyError:
                logger.warning("Advisory unlock failed for incident")
        lock.release()
