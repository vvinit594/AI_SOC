"""Stage 2 auth-workspace migration against a throwaway PostgreSQL database.

Creates and drops `aisoc_stage2_verify` on a local cluster derived from
backend/.env. Never writes to the live `aisoc` database and never downgrades.
"""

from __future__ import annotations

import os
import re
import uuid
import warnings
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.core.config import Settings, get_settings
from app.core.security_constants import LEGACY_WORKSPACE_ID
from app.main import create_app
from app.tests.helpers import CookieClient, build_settings, register_user

VERIFY_DB = "aisoc_stage2_verify"
PRE_AUTH_REVISION = "0005_drop_audit_event_uniqueness"
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
    parsed = urlparse(url)
    if not parsed.scheme.startswith("postgresql"):
        raise UnsafePostgresTarget("Stage 2 verify URL is not PostgreSQL")
    host = (parsed.hostname or "").lower()
    if host not in _LOCAL_HOSTS:
        raise UnsafePostgresTarget("Stage 2 verify URL host is not a local disposable cluster")
    name = _database_name(url)
    if name in _PROTECTED_DB_NAMES or name == "":
        raise UnsafePostgresTarget("Stage 2 verify URL targets a protected database name")
    if not _SAFE_DB_NAME.match(name):
        raise UnsafePostgresTarget("Stage 2 verify database name is not a safe identifier")
    if name != expected_name:
        raise UnsafePostgresTarget(
            f"Stage 2 verify URL must use the dedicated disposable database {expected_name}"
        )
    return name


def _resolve_verify_url() -> str | None:
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
            "Refusing to create or drop a database other than the Stage 2 verify database"
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
            f"Failed to drop disposable Stage 2 database {VERIFY_DB} "
            f"({type(exc).__name__}). Remove it manually if it remains.",
            RuntimeWarning,
            stacklevel=2,
        )


def _upgrade_schema(url: str, revision: str) -> None:
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()
    try:
        config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        command.upgrade(config, revision)
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        get_settings.cache_clear()


def test_validate_disposable_target_refuses_live_aisoc() -> None:
    with pytest.raises(UnsafePostgresTarget, match="protected database name"):
        _validate_disposable_target("postgresql+psycopg://user:secret@localhost:56000/aisoc")


def test_require_verify_name_refuses_other_databases() -> None:
    with pytest.raises(UnsafePostgresTarget, match="other than the Stage 2 verify database"):
        _require_verify_name("aisoc")


@pytest.fixture
def stage2_verify_url() -> Generator[str]:
    try:
        verify_url = _resolve_verify_url()
    except UnsafePostgresTarget as exc:
        pytest.skip(str(exc))
    if verify_url is None:
        pytest.skip("No local PostgreSQL URL configured for Stage 2 verification")

    admin_url = _maintenance_url(verify_url)
    created = False
    try:
        try:
            _drop_verify_database(admin_url)
            _create_verify_database(admin_url)
            created = True
        except OperationalError as exc:
            pytest.skip(f"PostgreSQL Stage 2 verify DB unavailable ({type(exc).__name__})")
        yield verify_url
    finally:
        if created:
            _cleanup_throwaway(admin_url)


def test_auth_workspace_migration_preserves_legacy_rows(stage2_verify_url: str) -> None:
    event_id = uuid.uuid4()
    incident_id = uuid.uuid4()
    audit_id = uuid.uuid4()
    now = datetime.now(UTC)

    _upgrade_schema(stage2_verify_url, PRE_AUTH_REVISION)
    engine = create_engine(stage2_verify_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO security_events "
                    "(id, timestamp, event_type, source, raw_message, created_at) "
                    "VALUES (:id, :ts, 'login_failure', 'linux_auth', 'legacy event', :ts)"
                ),
                {"id": event_id, "ts": now},
            )
            connection.execute(
                text(
                    "INSERT INTO incidents "
                    "(id, title, severity, status, summary, created_at) "
                    "VALUES (:id, 'Legacy incident', 'high', 'open', 'historical', :ts)"
                ),
                {"id": incident_id, "ts": now},
            )
            connection.execute(
                text(
                    "INSERT INTO audit_logs "
                    "(id, occurred_at, event_type, actor, resource_type, resource_id, "
                    "incident_id, details) "
                    "VALUES (:id, :ts, 'incident.created', 'unverified', 'incident', "
                    ":incident_id, :incident_id, CAST(:details AS json))"
                ),
                {
                    "id": audit_id,
                    "ts": now,
                    "incident_id": incident_id,
                    "details": "{}",
                },
            )
            events_before = connection.execute(
                text("SELECT count(*) FROM security_events")
            ).scalar()
            incidents_before = connection.execute(text("SELECT count(*) FROM incidents")).scalar()
            audits_before = connection.execute(text("SELECT count(*) FROM audit_logs")).scalar()
    finally:
        engine.dispose()

    _upgrade_schema(stage2_verify_url, "head")

    engine = create_engine(stage2_verify_url)
    application = None
    try:
        with engine.connect() as connection:
            version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
            assert version == "0006_auth_workspaces"
            events_after = connection.execute(text("SELECT count(*) FROM security_events")).scalar()
            incidents_after = connection.execute(text("SELECT count(*) FROM incidents")).scalar()
            audits_after = connection.execute(text("SELECT count(*) FROM audit_logs")).scalar()
            assert events_after == events_before == 1
            assert incidents_after == incidents_before == 1
            assert audits_after == audits_before == 1
            event_workspace = connection.execute(
                text("SELECT workspace_id FROM security_events WHERE id = :id"),
                {"id": event_id},
            ).scalar()
            incident_workspace = connection.execute(
                text("SELECT workspace_id FROM incidents WHERE id = :id"),
                {"id": incident_id},
            ).scalar()
            audit_workspace = connection.execute(
                text("SELECT workspace_id FROM audit_logs WHERE id = :id"),
                {"id": audit_id},
            ).scalar()
            assert event_workspace == LEGACY_WORKSPACE_ID
            assert incident_workspace == LEGACY_WORKSPACE_ID
            assert audit_workspace == LEGACY_WORKSPACE_ID
            memberships = connection.execute(
                text(
                    "SELECT count(*) FROM workspace_memberships "
                    "WHERE workspace_id = CAST(:id AS uuid)"
                ),
                {"id": str(LEGACY_WORKSPACE_ID)},
            ).scalar()
            assert memberships == 0

        application = create_app(build_settings(database_url=stage2_verify_url))
        with CookieClient(application) as client:
            body = register_user(client, email="first-migrated@example.com")
            assert body["workspace"]["id"] != str(LEGACY_WORKSPACE_ID)
            listed = client.get("/api/events").json()
            assert listed["total"] == 0
            assert client.get(f"/api/incidents/{incident_id}").status_code == 404
            assert client.get("/api/incidents").json()["total"] == 0
    finally:
        if application is not None:
            application.state.engine.dispose()
        engine.dispose()
