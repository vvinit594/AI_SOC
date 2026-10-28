"""Phase 9 persisted response workflow against a throwaway PostgreSQL database.

Uses AISOC_POSTGRES_TEST_URL when set. Otherwise, if backend/.env points at
localhost PostgreSQL, creates and drops `aisoc_phase9_verify` on that cluster.
Never writes to the live `aisoc` database.
"""

from __future__ import annotations

import os
import re
import uuid
import warnings
from collections.abc import Generator
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import OperationalError

from app.core.config import Settings, get_settings
from app.db.models import AuditLog, Incident, ResponseAction, SecurityEvent
from app.main import create_app
from app.tests.helpers import build_settings
from app.tests.test_investigations import _open_incident

VERIFY_DB = "aisoc_phase9_verify"
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_PROTECTED_DB_NAMES = frozenset({"aisoc", "postgres", "template0", "template1"})
_SAFE_DB_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


class UnsafePostgresTarget(ValueError):
    """Raised when a PostgreSQL URL is not a local disposable verify database."""


def _replace_database(url: str, name: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(path=f"/{name}"))


def _maintenance_url(url: str) -> str:
    return _replace_database(url, "postgres")


def _database_name(url: str) -> str:
    return urlparse(url).path.lstrip("/").split("?")[0]


def _validate_disposable_target(url: str, *, expected_name: str = VERIFY_DB) -> str:
    """Return the database name if the URL is a local disposable verify target.

    Exception messages never include credentials or the raw URL.
    """
    parsed = urlparse(url)
    if not parsed.scheme.startswith("postgresql"):
        raise UnsafePostgresTarget("Phase 9 verify URL is not PostgreSQL")
    host = (parsed.hostname or "").lower()
    if host not in _LOCAL_HOSTS:
        raise UnsafePostgresTarget("Phase 9 verify URL host is not a local disposable cluster")
    name = _database_name(url)
    if name in _PROTECTED_DB_NAMES or name == "":
        raise UnsafePostgresTarget("Phase 9 verify URL targets a protected database name")
    if not _SAFE_DB_NAME.match(name):
        raise UnsafePostgresTarget("Phase 9 verify database name is not a safe identifier")
    if name != expected_name:
        raise UnsafePostgresTarget(
            f"Phase 9 verify URL must use the dedicated disposable database {expected_name}"
        )
    return name


def _resolve_verify_url() -> str | None:
    explicit = os.environ.get("AISOC_POSTGRES_TEST_URL", "").strip()
    if explicit:
        _validate_disposable_target(explicit)
        return explicit
    get_settings.cache_clear()
    live = Settings()
    parsed = urlparse(live.database_url)
    if not parsed.scheme.startswith("postgresql"):
        return None
    if (parsed.hostname or "").lower() not in _LOCAL_HOSTS:
        return None
    verify_url = _replace_database(live.database_url, VERIFY_DB)
    _validate_disposable_target(verify_url)
    return verify_url


def _exec_autocommit(url: str, statement: str, **params: object) -> None:
    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            connection.execute(text(statement), params)
    finally:
        engine.dispose()


def _require_verify_name(name: str) -> None:
    if name != VERIFY_DB:
        raise UnsafePostgresTarget(
            "Refusing to create or drop a database other than the Phase 9 verify database"
        )


def _drop_verify_database(admin_url: str) -> None:
    _require_verify_name(VERIFY_DB)
    _exec_autocommit(
        admin_url,
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE datname = :name AND pid <> pg_backend_pid()",
        name=VERIFY_DB,
    )
    _exec_autocommit(admin_url, f'DROP DATABASE IF EXISTS "{VERIFY_DB}"')


def _create_verify_database(admin_url: str) -> None:
    _require_verify_name(VERIFY_DB)
    _exec_autocommit(admin_url, f'CREATE DATABASE "{VERIFY_DB}"')


def _cleanup_throwaway(admin_url: str) -> None:
    try:
        _drop_verify_database(admin_url)
    except Exception as exc:
        warnings.warn(
            f"Failed to drop disposable Phase 9 database {VERIFY_DB} "
            f"({type(exc).__name__}). Remove it manually if it remains.",
            RuntimeWarning,
            stacklevel=2,
        )


def _upgrade_schema(url: str) -> None:
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()
    try:
        config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        command.upgrade(config, "head")
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        get_settings.cache_clear()


def test_validate_disposable_target_refuses_live_aisoc() -> None:
    with pytest.raises(UnsafePostgresTarget, match="protected database name"):
        _validate_disposable_target("postgresql+psycopg://user:secret@localhost:55432/aisoc")


def test_validate_disposable_target_refuses_remote_hosts() -> None:
    with pytest.raises(UnsafePostgresTarget, match="not a local disposable cluster"):
        _validate_disposable_target(
            f"postgresql+psycopg://user:secret@db.example.com:5432/{VERIFY_DB}"
        )


def test_validate_disposable_target_refuses_maintenance_database() -> None:
    with pytest.raises(UnsafePostgresTarget, match="protected database name"):
        _validate_disposable_target("postgresql+psycopg://user:secret@127.0.0.1:5432/postgres")


def test_validate_disposable_target_accepts_local_verify_db() -> None:
    assert (
        _validate_disposable_target(f"postgresql+psycopg://user:secret@127.0.0.1:55432/{VERIFY_DB}")
        == VERIFY_DB
    )


def test_validate_disposable_target_hides_credentials() -> None:
    with pytest.raises(UnsafePostgresTarget) as exc_info:
        _validate_disposable_target(
            "postgresql+psycopg://secretuser:secretpass@evil.example.com:5432/aisoc"
        )
    message = str(exc_info.value)
    assert "secretpass" not in message
    assert "secretuser" not in message
    assert "evil.example.com" not in message


def test_require_verify_name_refuses_other_databases() -> None:
    with pytest.raises(UnsafePostgresTarget, match="other than the Phase 9 verify database"):
        _require_verify_name("aisoc")


@pytest.fixture(scope="module")
def postgres_client() -> Generator[TestClient]:
    try:
        verify_url = _resolve_verify_url()
    except UnsafePostgresTarget as exc:
        pytest.skip(str(exc))
    if verify_url is None:
        pytest.skip("No local PostgreSQL URL configured for Phase 9 verification")

    admin_url = _maintenance_url(verify_url)
    created = False
    application = None
    try:
        try:
            _drop_verify_database(admin_url)
            _create_verify_database(admin_url)
            created = True
            _upgrade_schema(verify_url)
        except OperationalError as exc:
            pytest.skip(f"PostgreSQL Phase 9 verify DB unavailable ({type(exc).__name__})")

        application = create_app(build_settings(database_url=verify_url))
        application.state.test_database_url = verify_url
        with TestClient(application) as client:
            yield client
    finally:
        if application is not None:
            application.state.engine.dispose()
        if created:
            _cleanup_throwaway(admin_url)


def _ensure_two_actions(client: TestClient, incident_id: str) -> tuple[str, str]:
    detail = client.get(f"/api/incidents/{incident_id}").json()
    ids = [item["id"] for item in detail["actions"]]
    needed = max(0, 2 - len(ids))
    if needed:
        session = client.app.state.session_factory()
        try:
            for index in range(needed):
                extra = ResponseAction(
                    incident_id=uuid.UUID(incident_id),
                    action_type="flag_ip_for_review",
                    target=f"192.0.2.{10 + index}",
                    reason="phase9 sibling",
                    risk_level="medium",
                    approval_status="proposed",
                    execution_status="not_executed",
                    simulated=True,
                )
                session.add(extra)
                session.flush()
                ids.append(str(extra.id))
            session.commit()
        finally:
            session.close()
    return ids[0], ids[1]


def test_postgres_phase9_persisted_response_workflow(postgres_client: TestClient) -> None:
    client = postgres_client
    incident_id = _open_incident(client)
    investigated = client.post(f"/api/incidents/{incident_id}/investigate")
    assert investigated.status_code == 200, investigated.text

    listed = client.get("/api/incidents")
    assert listed.status_code == 200
    assert any(item["id"] == incident_id for item in listed.json()["items"])

    detail = client.get(f"/api/incidents/{incident_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == incident_id
    event_ids = list(body["event_ids"])
    assert event_ids
    first_id, second_id = _ensure_two_actions(client, incident_id)
    assert first_id != second_id

    approve = client.post(f"/api/actions/{first_id}/approve")
    assert approve.status_code == 200, approve.text
    assert approve.json()["approval_status"] == "approved"
    assert approve.json()["simulated"] is True
    assert approve.json()["execution_status"] == "not_executed"

    session = client.app.state.session_factory()
    try:
        stored = session.get(ResponseAction, uuid.UUID(first_id))
        assert stored is not None
        assert stored.approval_status == "approved"
        assert stored.actor == "unverified"
        assert stored.decided_at is not None
        assert stored.simulated is True
        assert stored.execution_status == "not_executed"
        sibling = session.get(ResponseAction, uuid.UUID(second_id))
        assert sibling is not None
        assert sibling.approval_status == "proposed"
        audits = list(
            session.scalars(select(AuditLog).where(AuditLog.incident_id == uuid.UUID(incident_id)))
        )
        assert len(audits) == 1
        assert audits[0].event_type == "response_action.approved"
        incident = session.get(Incident, uuid.UUID(incident_id))
        assert incident is not None
        event_uuids = [uuid.UUID(item) for item in event_ids]
        evidence = list(
            session.scalars(select(SecurityEvent).where(SecurityEvent.id.in_(event_uuids)))
        )
        assert len(evidence) == len(event_ids)
    finally:
        session.close()

    retry = client.post(f"/api/actions/{first_id}/approve")
    assert retry.status_code == 200
    assert retry.json()["decided_at"] == approve.json()["decided_at"]
    conflict = client.post(f"/api/actions/{first_id}/reject")
    assert conflict.status_code == 409

    session = client.app.state.session_factory()
    try:
        audits = list(
            session.scalars(select(AuditLog).where(AuditLog.incident_id == uuid.UUID(incident_id)))
        )
        assert len(audits) == 1
    finally:
        session.close()

    rejected = client.post(f"/api/actions/{second_id}/reject")
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["approval_status"] == "rejected"

    history = client.get(f"/api/incidents/{incident_id}/audit-logs")
    assert history.status_code == 200
    items = history.json()["items"]
    assert history.json()["total"] == 2
    assert [item["event_type"] for item in items] == [
        "response_action.rejected",
        "response_action.approved",
    ]

    report = client.get(f"/api/incidents/{incident_id}/report")
    assert report.status_code == 200
    assert report.headers["content-type"].startswith("text/html")
    assert (
        report.headers["content-disposition"]
        == f'attachment; filename="incident-{incident_id}-report.html"'
    )
    document = report.text
    assert "approved" in document
    assert "rejected" in document
    assert "response_action.approved" in document
    assert "Not performed" in document
    assert "no live containment occurred" in document
    assert "was executed" not in document.lower()

    after = client.get(f"/api/incidents/{incident_id}")
    assert after.status_code == 200
    assert after.json()["event_ids"] == event_ids
    assert after.json()["id"] == incident_id


def test_postgres_production_empty_token_denies_protected_routes(
    postgres_client: TestClient,
) -> None:
    incident_id = _open_incident(postgres_client)
    verify_url = postgres_client.app.state.test_database_url
    application = create_app(
        build_settings(database_url=verify_url, app_env="production", analyst_api_token=None)
    )
    try:
        with TestClient(application) as client:
            report = client.get(f"/api/incidents/{incident_id}/report")
            audits = client.get(f"/api/incidents/{incident_id}/audit-logs")
            missing = uuid.uuid4()
            approve = client.post(f"/api/actions/{missing}/approve")
            assert report.status_code == 403
            assert audits.status_code == 403
            assert approve.status_code == 403
            assert "ANALYST_API_TOKEN is required in production" in report.text
    finally:
        application.state.engine.dispose()
