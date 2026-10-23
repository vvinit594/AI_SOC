"""Phase 5 scenario A/B/C verification against a throwaway PostgreSQL database.

Uses AISOC_POSTGRES_TEST_URL when set. Otherwise, if backend/.env points at
localhost PostgreSQL, creates and drops `aisoc_phase5_verify` on that cluster.
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
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.core.config import Settings, get_settings
from app.db.demo_data import BRUTE_FAILURE_IDS, BRUTE_SUCCESS_ID, OUTBOUND_IDS
from app.db.models import Incident
from app.main import create_app
from app.tests.helpers import build_settings

VERIFY_DB = "aisoc_phase5_verify"
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _replace_database(url: str, name: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(path=f"/{name}"))


def _maintenance_url(url: str) -> str:
    return _replace_database(url, "postgres")


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


@pytest.fixture(scope="module")
def postgres_client() -> Generator[TestClient]:
    cluster_url = _local_cluster_url()
    if cluster_url is None:
        pytest.skip("No local PostgreSQL URL configured for Phase 5 verification")

    verify_url = os.environ.get("AISOC_POSTGRES_TEST_URL", "").strip() or _replace_database(
        cluster_url, VERIFY_DB
    )
    if urlparse(verify_url).path.lstrip("/") == "aisoc":
        verify_url = _replace_database(verify_url, VERIFY_DB)
    using_throwaway = urlparse(verify_url).path.lstrip("/") == VERIFY_DB
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
        pytest.skip(f"PostgreSQL Phase 5 verify DB unavailable ({type(exc).__name__})")

    application = create_app(build_settings(database_url=verify_url))
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


def test_postgres_phase5_scenarios_a_b_c(postgres_client: TestClient) -> None:
    client = postgres_client

    load_a = client.post("/api/scenarios/A/load")
    assert load_a.status_code == 200, load_a.text
    assert load_a.json()["accepted"] == 13

    detect_a = client.post("/api/incidents/detect")
    assert detect_a.status_code == 200, detect_a.text
    body_a = detect_a.json()
    assert body_a["created"] == 1
    assert {match["rule_id"] for match in body_a["matches"]} == {"R1", "R2"}
    incident_a = body_a["incidents"][0]
    assert incident_a["severity"] == "critical"
    assert incident_a["status"] == "open"
    assert "T1110" in incident_a["summary"]
    assert "T1078" in incident_a["summary"]
    evidence_a = set(incident_a["event_ids"])
    assert str(BRUTE_SUCCESS_ID) in evidence_a
    assert {str(event_id) for event_id in BRUTE_FAILURE_IDS} <= evidence_a
    assert len(evidence_a) == 13
    brute_id = incident_a["id"]

    repeat = client.post("/api/incidents/detect").json()
    assert repeat["created"] == 0
    assert repeat["updated"] == 1
    assert repeat["skipped"] == 0
    assert client.get("/api/incidents").json()["total"] == 1
    assert client.get(f"/api/incidents/{brute_id}").json()["event_ids"] == incident_a["event_ids"]

    load_b = client.post("/api/scenarios/B/load")
    assert load_b.status_code == 200, load_b.text
    assert load_b.json()["accepted"] == 10
    detect_b = client.post("/api/incidents/detect").json()
    assert detect_b["created"] == 1
    assert detect_b["updated"] == 1
    outbound = next(item for item in detect_b["incidents"] if item["scenario"] == "B")
    assert outbound["severity"] == "high"
    outbound_rules = {
        match["rule_id"] for match in detect_b["matches"] if match["incident_id"] == outbound["id"]
    }
    assert outbound_rules == {"R3"}
    assert {str(event_id) for event_id in OUTBOUND_IDS} <= set(outbound["event_ids"])

    load_c = client.post("/api/scenarios/C/load")
    assert load_c.status_code == 200, load_c.text
    assert load_c.json()["accepted"] == 5
    detect_c = client.post("/api/incidents/detect").json()
    assert detect_c["created"] == 0
    listed = client.get("/api/incidents").json()
    assert listed["total"] == 2
    assert {item["scenario"] for item in listed["items"]} == {"A", "B"}

    session = client.app.state.session_factory()
    try:
        incident = session.get(Incident, uuid.UUID(brute_id))
        assert incident is not None
        incident.status = "resolved"
        incident.summary = "Analyst closed after postgres verification"
        session.commit()
    finally:
        session.close()
    skipped = client.post("/api/incidents/detect").json()
    assert skipped["created"] == 0
    assert skipped["skipped"] == 1
    closed = client.get(f"/api/incidents/{brute_id}").json()
    assert closed["status"] == "resolved"
    assert closed["summary"] == "Analyst closed after postgres verification"


def test_postgres_phase6_investigation_persists_agent_runs(postgres_client: TestClient) -> None:
    client = postgres_client
    assert client.post("/api/scenarios/B/load").status_code == 200
    detect = client.post("/api/incidents/detect").json()
    listed = client.get("/api/incidents").json()["items"]
    outbound = next(item for item in listed if item.get("scenario") == "B")
    response = client.post(f"/api/incidents/{outbound['id']}/investigate")
    assert response.status_code == 200, response.text
    body = response.json()["investigation"]
    assert len(body["nodes"]) == 4
    assert all(node["status"] == "completed" for node in body["nodes"])
    analysis = next(node for node in body["nodes"] if node["agent_name"] == "analysis")
    assert "T1071" in analysis["structured_output"]["techniques"]
    fetched = client.get(f"/api/investigations/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["incident_id"] == outbound["id"]
    assert detect["created"] in {0, 1}
