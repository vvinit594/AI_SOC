from __future__ import annotations

import logging
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import AuditLog, ResponseAction
from app.tests.test_actions import SECRET_TOKEN, _app_client, _insert_proposed, _reload_action


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
