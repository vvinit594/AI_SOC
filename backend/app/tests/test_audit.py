from __future__ import annotations

import logging
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import AuditLog, ResponseAction
from app.services.audit import AuditError, record_event
from app.tests.test_actions import SECRET_TOKEN, _app_client, _insert_proposed, _reload_action

_SAFE_DETAILS = {
    "decision": "approved",
    "previous_approval_status": "proposed",
    "resulting_approval_status": "approved",
    "action_type": "force_password_reset",
}


def _list_audits(client: TestClient, incident_id: uuid.UUID) -> list[AuditLog]:
    session = client.app.state.session_factory()
    try:
        return list(
            session.scalars(
                select(AuditLog)
                .where(AuditLog.incident_id == incident_id)
                .order_by(AuditLog.occurred_at, AuditLog.id)
            ).all()
        )
    finally:
        session.close()


def test_approve_writes_one_audit_event(client: TestClient) -> None:
    incident_id, action_id = _insert_proposed(client)
    response = client.post(f"/api/actions/{action_id}/approve")
    assert response.status_code == 200, response.text
    rows = _list_audits(client, incident_id)
    assert len(rows) == 1
    row = rows[0]
    assert row.event_type == "response_action.approved"
    assert row.actor == "unverified"
    assert row.resource_type == "response_action"
    assert row.resource_id == action_id
    assert row.incident_id == incident_id
    assert row.details["decision"] == "approved"
    assert row.details["previous_approval_status"] == "proposed"
    assert row.details["resulting_approval_status"] == "approved"
    assert "authorization" not in row.details
    assert "token" not in row.details
    listed = client.get(f"/api/incidents/{incident_id}/audit-logs")
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(row.id)
    assert body["items"][0]["event_type"] == "response_action.approved"


def test_reject_writes_one_audit_event(client: TestClient) -> None:
    incident_id, action_id = _insert_proposed(client)
    response = client.post(f"/api/actions/{action_id}/reject")
    assert response.status_code == 200, response.text
    rows = _list_audits(client, incident_id)
    assert len(rows) == 1
    assert rows[0].event_type == "response_action.rejected"
    assert rows[0].details["decision"] == "rejected"


def test_duplicate_decision_does_not_write_second_audit(client: TestClient) -> None:
    incident_id, action_id = _insert_proposed(client)
    first = client.post(f"/api/actions/{action_id}/approve")
    second = client.post(f"/api/actions/{action_id}/approve")
    assert first.status_code == 200
    assert second.status_code == 200
    assert len(_list_audits(client, incident_id)) == 1


def test_conflict_does_not_write_success_audit(client: TestClient) -> None:
    incident_id, action_id = _insert_proposed(client)
    assert client.post(f"/api/actions/{action_id}/approve").status_code == 200
    conflict = client.post(f"/api/actions/{action_id}/reject")
    assert conflict.status_code == 409
    rows = _list_audits(client, incident_id)
    assert len(rows) == 1
    assert rows[0].event_type == "response_action.approved"


def test_unknown_action_does_not_write_audit(client: TestClient) -> None:
    missing = uuid.UUID("00000000-0000-4000-8000-000000000099")
    response = client.post(f"/api/actions/{missing}/approve")
    assert response.status_code == 404
    session = client.app.state.session_factory()
    try:
        count = len(list(session.scalars(select(AuditLog)).all()))
        assert count == 0
    finally:
        session.close()


def test_audit_survives_new_session(client: TestClient) -> None:
    incident_id, action_id = _insert_proposed(client)
    assert client.post(f"/api/actions/{action_id}/approve").status_code == 200
    rows = _list_audits(client, incident_id)
    assert len(rows) == 1
    assert rows[0].occurred_at is not None
    assert rows[0].actor == "unverified"


def test_failed_audit_rolls_back_decision(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("audit insert failed")

    monkeypatch.setattr("app.services.actions.record_event", _boom)
    _, action_id = _insert_proposed(client)
    with pytest.raises(RuntimeError, match="audit insert failed"):
        client.post(f"/api/actions/{action_id}/approve")
    stored = _reload_action(client, action_id)
    assert stored.approval_status == "proposed"
    assert stored.actor is None
    session = client.app.state.session_factory()
    try:
        assert list(session.scalars(select(AuditLog)).all()) == []
        action = session.get(ResponseAction, action_id)
        assert action is not None
        assert action.approval_status == "proposed"
    finally:
        session.close()


def test_audit_history_is_newest_first_and_paginated(client: TestClient) -> None:
    incident_id, first_id = _insert_proposed(
        client, extra_actions=[("flag_ip_for_review", "192.0.2.10")]
    )
    session = client.app.state.session_factory()
    try:
        second = next(
            row
            for row in session.scalars(
                select(ResponseAction).where(ResponseAction.incident_id == incident_id)
            )
            if row.id != first_id
        )
        second_id = second.id
    finally:
        session.close()
    assert client.post(f"/api/actions/{first_id}/approve").status_code == 200
    assert client.post(f"/api/actions/{second_id}/reject").status_code == 200
    listed = client.get(f"/api/incidents/{incident_id}/audit-logs")
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert listed.json()["total"] == 2
    assert [item["event_type"] for item in items] == [
        "response_action.rejected",
        "response_action.approved",
    ]
    page = client.get(
        f"/api/incidents/{incident_id}/audit-logs",
        params={"limit": 1, "offset": 0},
    )
    assert page.json()["total"] == 2
    assert len(page.json()["items"]) == 1
    assert page.json()["items"][0]["event_type"] == "response_action.rejected"


def test_audit_history_is_isolated_to_the_requested_incident(client: TestClient) -> None:
    first_incident, first_action = _insert_proposed(client)
    second_incident, second_action = _insert_proposed(client)
    assert client.post(f"/api/actions/{first_action}/approve").status_code == 200
    assert client.post(f"/api/actions/{second_action}/reject").status_code == 200
    listed = client.get(f"/api/incidents/{first_incident}/audit-logs")
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    assert body["items"][0]["incident_id"] == str(first_incident)
    assert body["items"][0]["event_type"] == "response_action.approved"
    assert str(second_action) not in listed.text
    assert "response_action.rejected" not in listed.text


def test_configured_token_rejects_missing_audit_read() -> None:
    with _app_client(app_env="development", analyst_api_token=SECRET_TOKEN) as client:
        incident_id, _action_id = _insert_proposed(client)
        missing = client.get(f"/api/incidents/{incident_id}/audit-logs")
        valid = client.get(
            f"/api/incidents/{incident_id}/audit-logs",
            headers={"Authorization": f"Bearer {SECRET_TOKEN}"},
        )
        assert missing.status_code == 401
        assert missing.json()["detail"] == "Invalid or missing analyst token"
        assert SECRET_TOKEN not in missing.text
        assert valid.status_code == 200
        assert valid.json()["total"] == 0


def test_audit_logs_unknown_incident_404(client: TestClient) -> None:
    missing = uuid.UUID("00000000-0000-4000-8000-000000000099")
    response = client.get(f"/api/incidents/{missing}/audit-logs")
    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "not_found"
    assert body["detail"] == "Incident not found"


def test_audit_logs_invalid_uuid_422(client: TestClient) -> None:
    response = client.get("/api/incidents/not-a-uuid/audit-logs")
    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


def test_production_audit_read_requires_token() -> None:
    with _app_client(app_env="production", analyst_api_token=None) as client:
        incident_id, _action_id = _insert_proposed(client)
        response = client.get(f"/api/incidents/{incident_id}/audit-logs")
        assert response.status_code == 403


def test_configured_token_actor_is_recorded_without_leaking_secret(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with _app_client(app_env="development", analyst_api_token=SECRET_TOKEN) as client:
        incident_id, action_id = _insert_proposed(client)
        with caplog.at_level(logging.DEBUG):
            response = client.post(
                f"/api/actions/{action_id}/approve",
                headers={"Authorization": f"Bearer {SECRET_TOKEN}"},
            )
            listed = client.get(
                f"/api/incidents/{incident_id}/audit-logs",
                headers={"Authorization": f"Bearer {SECRET_TOKEN}"},
            )
        assert response.status_code == 200, response.text
        assert listed.status_code == 200
        item = listed.json()["items"][0]
        assert item["actor"] == "analyst"
        assert SECRET_TOKEN not in listed.text
        assert SECRET_TOKEN not in response.text
        assert SECRET_TOKEN not in caplog.text
        assert SECRET_TOKEN not in str(item["details"])


def test_x_analyst_id_is_not_used_as_audit_actor(client: TestClient) -> None:
    incident_id, action_id = _insert_proposed(client)
    response = client.post(
        f"/api/actions/{action_id}/approve",
        headers={"X-Analyst-Id": "alice@example.com"},
    )
    assert response.status_code == 200
    rows = _list_audits(client, incident_id)
    assert rows[0].actor == "unverified"
    assert "alice" not in str(rows[0].details)


def test_deleting_incident_does_not_delete_audit_rows(client: TestClient) -> None:
    incident_id, action_id = _insert_proposed(client)
    assert client.post(f"/api/actions/{action_id}/approve").status_code == 200
    session = client.app.state.session_factory()
    try:
        from app.db.models import Incident

        incident = session.get(Incident, incident_id)
        assert incident is not None
        session.delete(incident)
        session.commit()
        remaining = list(session.scalars(select(AuditLog)).all())
        assert len(remaining) == 1
        assert remaining[0].incident_id is None
        assert remaining[0].resource_id == action_id
    finally:
        session.close()


def test_same_resource_can_store_repeated_event_type(client: TestClient) -> None:
    incident_id, action_id = _insert_proposed(client)
    session = client.app.state.session_factory()
    try:
        record_event(
            session,
            event_type="response_action.approved",
            actor="unverified",
            resource_type="response_action",
            resource_id=action_id,
            incident_id=incident_id,
            details=_SAFE_DETAILS,
        )
        record_event(
            session,
            event_type="response_action.approved",
            actor="analyst",
            resource_type="response_action",
            resource_id=action_id,
            incident_id=incident_id,
            details=_SAFE_DETAILS,
        )
        session.commit()
        rows = list(
            session.scalars(select(AuditLog).where(AuditLog.resource_id == action_id)).all()
        )
        assert len(rows) == 2
        assert {row.event_type for row in rows} == {"response_action.approved"}
        assert {row.actor for row in rows} == {"unverified", "analyst"}
    finally:
        session.close()


def test_safe_decision_metadata_is_persisted(client: TestClient) -> None:
    incident_id, action_id = _insert_proposed(client)
    assert client.post(f"/api/actions/{action_id}/approve").status_code == 200
    row = _list_audits(client, incident_id)[0]
    assert row.details == {
        "decision": "approved",
        "previous_approval_status": "proposed",
        "resulting_approval_status": "approved",
        "action_type": "force_password_reset",
    }


def test_unexpected_metadata_key_is_rejected(client: TestClient) -> None:
    incident_id, action_id = _insert_proposed(client)
    session = client.app.state.session_factory()
    try:
        with pytest.raises(AuditError, match="Invalid audit event details"):
            record_event(
                session,
                event_type="response_action.approved",
                actor="unverified",
                resource_type="response_action",
                resource_id=action_id,
                incident_id=incident_id,
                details={**_SAFE_DETAILS, "token": "should-not-be-stored"},
            )
        session.rollback()
        assert list(session.scalars(select(AuditLog)).all()) == []
    finally:
        session.close()


def test_invalid_metadata_value_is_rejected(client: TestClient) -> None:
    incident_id, action_id = _insert_proposed(client)
    session = client.app.state.session_factory()
    try:
        with pytest.raises(AuditError, match="Invalid audit event details"):
            record_event(
                session,
                event_type="response_action.approved",
                actor="unverified",
                resource_type="response_action",
                resource_id=action_id,
                incident_id=incident_id,
                details={**_SAFE_DETAILS, "decision": "maybe"},
            )
        session.rollback()
    finally:
        session.close()


def test_oversized_metadata_string_is_rejected(client: TestClient) -> None:
    incident_id, action_id = _insert_proposed(client)
    session = client.app.state.session_factory()
    try:
        with pytest.raises(AuditError, match="Invalid audit event details"):
            record_event(
                session,
                event_type="response_action.approved",
                actor="unverified",
                resource_type="response_action",
                resource_id=action_id,
                incident_id=incident_id,
                details={**_SAFE_DETAILS, "action_type": "x" * 65},
            )
        session.rollback()
        assert list(session.scalars(select(AuditLog)).all()) == []
    finally:
        session.close()


def test_audit_validation_failure_rolls_back_decision(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = record_event

    def _poisoned(
        session: object,
        *,
        event_type: str,
        actor: str,
        resource_type: str,
        resource_id: uuid.UUID,
        incident_id: uuid.UUID | None = None,
        details: dict[str, object] | None = None,
    ) -> AuditLog:
        payload = dict(details or {})
        payload["authorization"] = "Bearer should-not-persist"
        return original(
            session,  # type: ignore[arg-type]
            event_type=event_type,  # type: ignore[arg-type]
            actor=actor,
            resource_type=resource_type,  # type: ignore[arg-type]
            resource_id=resource_id,
            incident_id=incident_id,
            details=payload,
        )

    monkeypatch.setattr("app.services.actions.record_event", _poisoned)
    _, action_id = _insert_proposed(client)
    with pytest.raises(AuditError, match="Invalid audit event details"):
        client.post(f"/api/actions/{action_id}/approve")
    stored = _reload_action(client, action_id)
    assert stored.approval_status == "proposed"
    assert stored.decided_at is None
    session = client.app.state.session_factory()
    try:
        assert list(session.scalars(select(AuditLog)).all()) == []
    finally:
        session.close()


def test_postgres_drops_audit_event_uniqueness_without_losing_rows() -> None:
    import json
    import os
    from datetime import UTC, datetime
    from pathlib import Path
    from urllib.parse import urlparse

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import OperationalError

    from app.core.config import get_settings
    from app.tests.test_phase5_postgres import (
        _exec_autocommit,
        _local_cluster_url,
        _maintenance_url,
        _replace_database,
    )

    cluster_url = _local_cluster_url()
    if cluster_url is None:
        pytest.skip("No local PostgreSQL URL configured for audit migration verification")

    db_name = "aisoc_audit_mig_verify"
    verify_url = _replace_database(cluster_url, db_name)
    if urlparse(verify_url).path.lstrip("/") == "aisoc":
        pytest.skip("Refusing to run migration verification against live aisoc")
    admin_url = _maintenance_url(cluster_url)
    alembic_ini = str(Path(__file__).resolve().parents[2] / "alembic.ini")

    def _alembic(revision: str, *, downgrade: bool = False) -> None:
        previous = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = verify_url
        get_settings.cache_clear()
        try:
            config = Config(alembic_ini)
            if downgrade:
                command.downgrade(config, revision)
            else:
                command.upgrade(config, revision)
        finally:
            if previous is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = previous
            get_settings.cache_clear()
            logging.getLogger().disabled = False
            for logger in logging.Logger.manager.loggerDict.values():
                if isinstance(logger, logging.Logger):
                    logger.disabled = False

    def _constraint_names(engine) -> set[str]:
        with engine.connect() as connection:
            rows = connection.execute(
                text("SELECT conname FROM pg_constraint WHERE conrelid = 'audit_logs'::regclass")
            )
            return {row[0] for row in rows}

    def _index_names(engine) -> set[str]:
        with engine.connect() as connection:
            rows = connection.execute(
                text("SELECT indexname FROM pg_indexes WHERE tablename = 'audit_logs'")
            )
            return {row[0] for row in rows}

    try:
        _exec_autocommit(
            admin_url,
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = :name AND pid <> pg_backend_pid()",
            name=db_name,
        )
        _exec_autocommit(admin_url, f'DROP DATABASE IF EXISTS "{db_name}"')
        _exec_autocommit(admin_url, f'CREATE DATABASE "{db_name}"')
    except OperationalError as exc:
        pytest.skip(f"PostgreSQL audit migration verify DB unavailable ({type(exc).__name__})")

    engine = create_engine(verify_url)
    incident_id = uuid.uuid4()
    resource_id = uuid.uuid4()
    first_id = uuid.uuid4()
    second_id = uuid.uuid4()
    now = datetime.now(UTC)
    details = json.dumps(_SAFE_DETAILS)
    try:
        _alembic("0004_audit_logs")
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO incidents (id, title, severity, status, summary, created_at) "
                    "VALUES (:id, 'mig', 'low', 'open', 'mig', :created)"
                ),
                {"id": incident_id, "created": now},
            )
            connection.execute(
                text(
                    "INSERT INTO audit_logs "
                    "(id, occurred_at, event_type, actor, resource_type, resource_id, "
                    "incident_id, details) "
                    "VALUES (:id, :occurred, 'response_action.approved', 'unverified', "
                    "'response_action', :resource_id, :incident_id, CAST(:details AS json))"
                ),
                {
                    "id": first_id,
                    "occurred": now,
                    "resource_id": resource_id,
                    "incident_id": incident_id,
                    "details": details,
                },
            )
        assert "uq_audit_logs_resource_event" in _constraint_names(engine)

        _alembic("0005_drop_audit_event_uniqueness")
        names = _constraint_names(engine)
        assert "uq_audit_logs_resource_event" not in names
        indexes = _index_names(engine)
        assert {
            "ix_audit_logs_occurred_at",
            "ix_audit_logs_incident_id",
            "ix_audit_logs_resource",
            "ix_audit_logs_event_type",
        } <= indexes
        with engine.begin() as connection:
            remaining = connection.execute(
                text("SELECT id FROM audit_logs WHERE id = :id"), {"id": first_id}
            ).scalar()
            assert remaining == first_id
            connection.execute(
                text(
                    "INSERT INTO audit_logs "
                    "(id, occurred_at, event_type, actor, resource_type, resource_id, "
                    "incident_id, details) "
                    "VALUES (:id, :occurred, 'response_action.approved', 'analyst', "
                    "'response_action', :resource_id, :incident_id, CAST(:details AS json))"
                ),
                {
                    "id": second_id,
                    "occurred": now,
                    "resource_id": resource_id,
                    "incident_id": incident_id,
                    "details": details,
                },
            )
            count = connection.execute(text("SELECT count(*) FROM audit_logs")).scalar()
            assert count == 2
            fk = connection.execute(
                text(
                    "SELECT confdeltype FROM pg_constraint "
                    "WHERE conrelid = 'audit_logs'::regclass AND contype = 'f'"
                )
            ).scalar()
            assert fk == "n"
            connection.execute(text("DELETE FROM audit_logs WHERE id = :id"), {"id": second_id})

        _alembic("0004_audit_logs", downgrade=True)
        assert "uq_audit_logs_resource_event" in _constraint_names(engine)
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT id FROM audit_logs WHERE id = :id"), {"id": first_id}
                ).scalar()
                == first_id
            )

        _alembic("head")
        assert "uq_audit_logs_resource_event" not in _constraint_names(engine)
    finally:
        engine.dispose()
        try:
            _exec_autocommit(
                admin_url,
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = :name AND pid <> pg_backend_pid()",
                name=db_name,
            )
            _exec_autocommit(admin_url, f'DROP DATABASE IF EXISTS "{db_name}"')
        except Exception:
            pass
