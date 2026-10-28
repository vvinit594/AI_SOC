"""Phase 9 persisted response workflow against a throwaway PostgreSQL database.

Uses AISOC_POSTGRES_TEST_URL when set. Otherwise, if backend/.env points at
localhost PostgreSQL, creates and drops `aisoc_phase9_verify` on that cluster.
Never writes to the live `aisoc` database.
"""

from __future__ import annotations

import os
import uuid
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
_LIVE_DB = "aisoc"


def _replace_database(url: str, name: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(path=f"/{name}"))


def _maintenance_url(url: str) -> str:
    return _replace_database(url, "postgres")


def _database_name(url: str) -> str:
    return urlparse(url).path.lstrip("/").split("?")[0]


def _local_cluster_url() -> str | None:
    explicit = os.environ.get("AISOC_POSTGRES_TEST_URL", "").strip()
    if explicit:
        return explicit
    get_settings.cache_clear()
    live = Settings()
    parsed = urlparse(live.database_url)
    if not parsed.scheme.startswith("postgresql"):
        return None
    if (parsed.hostname or "") not in _LOCAL_HOSTS:
        return None
    return live.database_url


def _exec_autocommit(url: str, statement: str, **params: object) -> None:
    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            connection.execute(text(statement), params)
    finally:
        engine.dispose()


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


def test_phase9_postgres_url_refuses_live_aisoc() -> None:
    assert _database_name("postgresql+psycopg://aisoc:aisoc@localhost:55432/aisoc") == _LIVE_DB


@pytest.fixture(scope="module")
def postgres_client() -> Generator[TestClient]:
    cluster_url = _local_cluster_url()
    if cluster_url is None:
        pytest.skip("No local PostgreSQL URL configured for Phase 9 verification")

    explicit = os.environ.get("AISOC_POSTGRES_TEST_URL", "").strip()
    verify_url = explicit or _replace_database(cluster_url, VERIFY_DB)
    if _database_name(verify_url) == _LIVE_DB:
        pytest.skip("Refusing PostgreSQL Phase 9 tests against the live aisoc database")

    using_throwaway = _database_name(verify_url) == VERIFY_DB
    admin_url = _maintenance_url(cluster_url if using_throwaway else verify_url)

    try:
        if using_throwaway:
            _exec_autocommit(
                admin_url,
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = :name AND pid <> pg_backend_pid()",
                name=VERIFY_DB,
            )
            _exec_autocommit(admin_url, f'DROP DATABASE IF EXISTS "{VERIFY_DB}"')
            _exec_autocommit(admin_url, f'CREATE DATABASE "{VERIFY_DB}"')
        _upgrade_schema(verify_url)
    except OperationalError as exc:
        pytest.skip(f"PostgreSQL Phase 9 verify DB unavailable ({type(exc).__name__})")

    application = create_app(build_settings(database_url=verify_url))
    application.state.test_database_url = verify_url
    with TestClient(application) as client:
        yield client

    if using_throwaway:
        try:
            application.state.engine.dispose()
            _exec_autocommit(
                admin_url,
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = :name AND pid <> pg_backend_pid()",
                name=VERIFY_DB,
            )
            _exec_autocommit(admin_url, f'DROP DATABASE IF EXISTS "{VERIFY_DB}"')
        except Exception:
            pass


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
