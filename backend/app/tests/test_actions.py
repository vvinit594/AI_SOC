from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.base import Base
from app.db.models import AgentRun, Incident, ResponseAction
from app.main import create_app
from app.schemas.investigations import RecommendedAction
from app.services.actions import decide_action
from app.services.investigations import _store_actions
from app.tests.helpers import build_settings
from app.tests.test_investigations import _open_incident

SECRET_TOKEN = "phase8a-test-token-not-for-production"


def _app_client(**overrides: object) -> TestClient:
    application = create_app(build_settings(**overrides))
    Base.metadata.create_all(application.state.engine)
    return TestClient(application)


def _insert_proposed(
    client: TestClient,
    *,
    action_type: str = "force_password_reset",
    target: str | None = "demo_user",
    status: str = "awaiting_approval",
    extra_actions: list[tuple[str, str | None]] | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    session = client.app.state.session_factory()
    try:
        incident = Incident(
            title="Action decision fixture",
            severity="high",
            status=status,
            summary="fixture",
        )
        session.add(incident)
        session.flush()
        action = ResponseAction(
            incident_id=incident.id,
            action_type=action_type,
            target=target,
            reason="fixture reason",
            risk_level="high",
            approval_status="proposed",
            execution_status="not_executed",
            simulated=True,
        )
        session.add(action)
        for extra_type, extra_target in extra_actions or []:
            session.add(
                ResponseAction(
                    incident_id=incident.id,
                    action_type=extra_type,
                    target=extra_target,
                    reason="sibling fixture",
                    risk_level="medium",
                    approval_status="proposed",
                    execution_status="not_executed",
                    simulated=True,
                )
            )
        session.commit()
        return incident.id, action.id
    finally:
        session.close()


def _reload_action(client: TestClient, action_id: uuid.UUID) -> ResponseAction:
    session = client.app.state.session_factory()
    try:
        stored = session.get(ResponseAction, action_id)
        assert stored is not None
        session.expunge(stored)
        return stored
    finally:
        session.close()


def test_development_without_token_records_unverified() -> None:
    with _app_client(app_env="development", analyst_api_token=None) as client:
        _, action_id = _insert_proposed(client)
        response = client.post(f"/api/actions/{action_id}/approve")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["actor"] == "unverified"
        assert body["approval_status"] == "approved"
        assert body["simulated"] is True
        assert SECRET_TOKEN not in response.text


def test_development_configured_token_rejects_missing_and_invalid(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with _app_client(app_env="development", analyst_api_token=SECRET_TOKEN) as client:
        _, action_id = _insert_proposed(client)
        with caplog.at_level(logging.DEBUG):
            missing = client.post(f"/api/actions/{action_id}/approve")
            invalid = client.post(
                f"/api/actions/{action_id}/approve",
                headers={"Authorization": f"Bearer {SECRET_TOKEN}-wrong"},
            )
        assert missing.status_code == 401
        assert invalid.status_code == 401
        for body in (missing.json(), invalid.json()):
            assert body["error"] == "http_error"
            assert body["code"] == "http_error"
            assert body["detail"] == "Invalid or missing analyst token"
            assert SECRET_TOKEN not in str(body)
        assert SECRET_TOKEN not in caplog.text
        stored = _reload_action(client, action_id)
        assert stored.approval_status == "proposed"
        assert stored.actor is None
        assert stored.decided_at is None


def test_development_valid_token_records_analyst() -> None:
    with _app_client(app_env="development", analyst_api_token=SECRET_TOKEN) as client:
        _, action_id = _insert_proposed(client)
        response = client.post(
            f"/api/actions/{action_id}/approve",
            headers={"Authorization": f"Bearer {SECRET_TOKEN}"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["actor"] == "analyst"
        assert SECRET_TOKEN not in response.text
        assert "X-Analyst-Id" not in response.text


def test_production_without_token_returns_403() -> None:
    with _app_client(app_env="production", analyst_api_token=None) as client:
        _, action_id = _insert_proposed(client)
        response = client.post(
            f"/api/actions/{action_id}/approve",
            headers={"Authorization": "Bearer anything"},
        )
        assert response.status_code == 403
        body = response.json()
        assert body["error"] == "http_error"
        assert body["detail"] == "ANALYST_API_TOKEN is required in production"
        assert "anything" not in response.text
        stored = _reload_action(client, action_id)
        assert stored.approval_status == "proposed"


def test_production_configured_token_requires_bearer() -> None:
    with _app_client(app_env="production", analyst_api_token=SECRET_TOKEN) as client:
        _, action_id = _insert_proposed(client)
        missing = client.post(f"/api/actions/{action_id}/reject")
        valid = client.post(
            f"/api/actions/{action_id}/reject",
            headers={"Authorization": f"Bearer {SECRET_TOKEN}"},
        )
        assert missing.status_code == 401
        assert valid.status_code == 200, valid.text
        assert valid.json()["actor"] == "analyst"
        assert valid.json()["approval_status"] == "rejected"
        assert SECRET_TOKEN not in valid.text
        assert SECRET_TOKEN not in missing.text


def test_approve_persists_simulated_decision(client: TestClient) -> None:
    incident_id, action_id = _insert_proposed(client)
    before = datetime.now(UTC)
    response = client.post(f"/api/actions/{action_id}/approve")
    after = datetime.now(UTC)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == str(action_id)
    assert body["incident_id"] == str(incident_id)
    assert body["action_type"] == "force_password_reset"
    assert body["target"] == "demo_user"
    assert body["reason"] == "fixture reason"
    assert body["risk_level"] == "high"
    assert body["approval_status"] == "approved"
    assert body["execution_status"] == "not_executed"
    assert body["simulated"] is True
    assert body["actor"] == "unverified"
    decided_at = datetime.fromisoformat(body["decided_at"])
    assert before <= decided_at <= after
    assert body["incident_status"] == "awaiting_approval"

    stored = _reload_action(client, action_id)
    assert stored.approval_status == "approved"
    assert stored.execution_status == "not_executed"
    assert stored.simulated is True
    assert stored.actor == "unverified"
    assert stored.decided_at is not None


def test_reject_persists_simulated_decision(client: TestClient) -> None:
    _, action_id = _insert_proposed(client)
    response = client.post(f"/api/actions/{action_id}/reject")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["approval_status"] == "rejected"
    assert body["execution_status"] == "not_executed"
    assert body["simulated"] is True
    assert body["actor"] == "unverified"
    assert body["decided_at"] is not None
    stored = _reload_action(client, action_id)
    assert stored.approval_status == "rejected"
    assert stored.execution_status == "not_executed"
    assert stored.simulated is True


def test_duplicate_approve_is_idempotent(client: TestClient) -> None:
    _, action_id = _insert_proposed(client)
    first = client.post(f"/api/actions/{action_id}/approve")
    assert first.status_code == 200
    original = first.json()
    second = client.post(f"/api/actions/{action_id}/approve")
    assert second.status_code == 200
    body = second.json()
    assert body["actor"] == original["actor"]
    assert body["decided_at"] == original["decided_at"]
    assert body["approval_status"] == "approved"
    stored = _reload_action(client, action_id)
    assert stored.actor == original["actor"]
    assert stored.decided_at == datetime.fromisoformat(original["decided_at"])


def test_duplicate_reject_is_idempotent(client: TestClient) -> None:
    _, action_id = _insert_proposed(client)
    first = client.post(f"/api/actions/{action_id}/reject")
    second = client.post(f"/api/actions/{action_id}/reject")
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["actor"] == first.json()["actor"]
    assert second.json()["decided_at"] == first.json()["decided_at"]
    assert second.json()["approval_status"] == "rejected"


def test_reject_after_approve_returns_409(client: TestClient) -> None:
    _, action_id = _insert_proposed(client)
    assert client.post(f"/api/actions/{action_id}/approve").status_code == 200
    response = client.post(f"/api/actions/{action_id}/reject")
    assert response.status_code == 409
    body = response.json()
    assert body["error"] == "http_error"
    assert body["detail"] == "Action already approved"
    stored = _reload_action(client, action_id)
    assert stored.approval_status == "approved"


def test_approve_after_reject_returns_409(client: TestClient) -> None:
    _, action_id = _insert_proposed(client)
    assert client.post(f"/api/actions/{action_id}/reject").status_code == 200
    response = client.post(f"/api/actions/{action_id}/approve")
    assert response.status_code == 409
    assert response.json()["detail"] == "Action already rejected"
    stored = _reload_action(client, action_id)
    assert stored.approval_status == "rejected"


def test_unknown_action_returns_404(client: TestClient) -> None:
    missing = uuid.UUID("00000000-0000-4000-8000-000000000099")
    response = client.post(f"/api/actions/{missing}/approve")
    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "not_found"
    assert body["detail"] == "Action not found"


def test_invalid_action_uuid_returns_validation_error(client: TestClient) -> None:
    response = client.post("/api/actions/not-a-uuid/approve")
    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


def test_decisions_remain_simulated_without_containment(client: TestClient, monkeypatch) -> None:
    called = {"execute": 0}

    def _forbidden(*_args: object, **_kwargs: object) -> None:
        called["execute"] += 1
        raise AssertionError("containment must not run")

    monkeypatch.setattr("app.services.actions.decide_action", decide_action)
    _, action_id = _insert_proposed(client)
    response = client.post(f"/api/actions/{action_id}/approve")
    assert response.status_code == 200
    assert response.json()["simulated"] is True
    assert response.json()["execution_status"] == "not_executed"
    assert called["execute"] == 0
    assert "containment" not in response.text.lower()


def test_decision_survives_new_session(client: TestClient) -> None:
    _, action_id = _insert_proposed(client)
    assert client.post(f"/api/actions/{action_id}/approve").status_code == 200
    stored = _reload_action(client, action_id)
    assert stored.approval_status == "approved"
    assert stored.actor == "unverified"
    assert stored.decided_at is not None
    assert stored.simulated is True


def test_incident_status_unchanged_when_one_of_many_actions_decided(client: TestClient) -> None:
    incident_id, first_id = _insert_proposed(
        client,
        extra_actions=[("flag_ip_for_review", "192.0.2.10")],
    )
    approve = client.post(f"/api/actions/{first_id}/approve")
    assert approve.status_code == 200
    assert approve.json()["incident_status"] == "awaiting_approval"
    detail = client.get(f"/api/incidents/{incident_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "awaiting_approval"
    statuses = {item["id"]: item["approval_status"] for item in body["actions"]}
    assert statuses[str(first_id)] == "approved"
    other = next(item for item in body["actions"] if item["id"] != str(first_id))
    assert other["approval_status"] == "proposed"
    assert other["id"] != "action-1"
    assert uuid.UUID(other["id"])


def test_reinvestigation_preserves_decided_actions(client: TestClient) -> None:
    incident_id, action_id = _insert_proposed(client)
    assert client.post(f"/api/actions/{action_id}/approve").status_code == 200
    original = _reload_action(client, action_id)
    session = client.app.state.session_factory()
    try:
        _store_actions(
            session,
            incident_id,
            [
                RecommendedAction(
                    action_type="force_password_reset",
                    target="demo_user",
                    reason="retried recommendation",
                    risk_level="high",
                ),
                RecommendedAction(
                    action_type="monitor",
                    target=None,
                    reason="watch the host",
                    risk_level="low",
                ),
            ],
        )
        rows = list(
            session.scalars(
                select(ResponseAction).where(ResponseAction.incident_id == incident_id)
            ).all()
        )
        types = {(row.action_type, row.target, row.approval_status) for row in rows}
        assert ("force_password_reset", "demo_user", "approved") in types
        assert ("monitor", None, "proposed") in types
        assert ("force_password_reset", "demo_user", "proposed") not in types
        decided = next(row for row in rows if row.id == action_id)
        assert decided.actor == original.actor
        assert decided.decided_at == original.decided_at
        assert decided.reason == "fixture reason"
    finally:
        session.close()


def test_incident_detail_returns_persisted_action_ids(client: TestClient) -> None:
    incident_id, action_id = _insert_proposed(client)
    assert client.post(f"/api/actions/{action_id}/reject").status_code == 200
    detail = client.get(f"/api/incidents/{incident_id}")
    assert detail.status_code == 200
    actions = detail.json()["actions"]
    assert len(actions) == 1
    assert actions[0]["id"] == str(action_id)
    assert actions[0]["approval_status"] == "rejected"
    assert actions[0]["simulated"] is True
    assert uuid.UUID(actions[0]["id"]).version == 4


def test_blank_analyst_token_is_none() -> None:
    settings = build_settings(analyst_api_token="  ")
    assert settings.analyst_api_token is None


def test_x_analyst_id_is_not_identity(client: TestClient) -> None:
    _, action_id = _insert_proposed(client)
    response = client.post(
        f"/api/actions/{action_id}/approve",
        headers={"X-Analyst-Id": "alice@example.com"},
    )
    assert response.status_code == 200
    assert response.json()["actor"] == "unverified"
    assert "alice" not in response.text


def test_workflow_retry_preserves_approved_action(client: TestClient) -> None:
    incident_id = uuid.UUID(_open_incident(client))
    first = client.post(f"/api/incidents/{incident_id}/investigate")
    assert first.status_code == 200, first.text
    detail = client.get(f"/api/incidents/{incident_id}").json()
    proposed = detail["actions"]
    assert proposed
    approved_id = proposed[0]["id"]
    action_type = proposed[0]["action_type"]
    target = proposed[0]["target"]
    approve = client.post(f"/api/actions/{approved_id}/approve")
    assert approve.status_code == 200
    original = approve.json()

    session = client.app.state.session_factory()
    try:
        rows = list(
            session.scalars(select(AgentRun).where(AgentRun.incident_id == incident_id)).all()
        )
        for row in rows:
            row.status = "failed"
            row.error = "RuntimeError"
        session.commit()
    finally:
        session.close()

    retry = client.post(f"/api/incidents/{incident_id}/investigate")
    assert retry.status_code == 200, retry.text
    assert retry.json()["created"] is True
    after = client.get(f"/api/incidents/{incident_id}").json()
    matching = [
        item
        for item in after["actions"]
        if item["action_type"] == action_type and item["target"] == target
    ]
    assert len(matching) == 1
    assert matching[0]["id"] == approved_id
    assert matching[0]["approval_status"] == "approved"
    assert matching[0]["actor"] == original["actor"]
    assert matching[0]["decided_at"] == original["decided_at"]
    assert matching[0]["reason"] == original["reason"]
