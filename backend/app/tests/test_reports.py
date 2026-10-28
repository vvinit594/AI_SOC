from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from app.db.models import AgentRun, AuditLog, Incident, IncidentEvent, ResponseAction, SecurityEvent
from app.tests.test_actions import SECRET_TOKEN, _app_client, _insert_proposed, _reload_action
from app.tests.test_investigations import _open_incident

XSS_TITLE = '<script>alert("xss-title")</script>'
XSS_SUMMARY = "Matched R1 <img src=x onerror=alert(1)>"
XSS_MESSAGE = '</td><script>alert("xss-event")</script>'
XSS_REASON = "<svg onload=alert(1)>"
XSS_FINDING = '<iframe src="javascript:alert(1)">'
OTHER_TITLE = "UNRELATED-INCIDENT-SHOULD-NOT-LEAK"


class _TagProbe(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag.lower())


def _headers(token: str | None = None) -> dict[str, str]:
    if token is None:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _insert_report_fixture(
    client: TestClient,
    *,
    title: str = "Report fixture",
    summary: str = "Matched R1 and R2 on demo_user",
    include_event: bool = True,
    include_investigation: bool = True,
    include_other_incident: bool = False,
    extra_action: tuple[str, str | None] | None = ("flag_ip_for_review", "192.0.2.10"),
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID | None]:
    session = client.app.state.session_factory()
    try:
        incident = Incident(
            title=title,
            severity="high",
            status="awaiting_approval",
            summary=summary,
            scenario="A",
        )
        session.add(incident)
        session.flush()
        if include_event:
            event = SecurityEvent(
                timestamp=datetime(2026, 10, 21, 12, 0, tzinfo=UTC),
                event_type="login_failure",
                source_ip="192.0.2.10",
                username="demo_user",
                hostname="demo-server-01",
                action="authentication_failed",
                source="linux_auth",
                raw_message=XSS_MESSAGE if "<" in title else "Failed password",
                scenario="A",
            )
            session.add(event)
            session.flush()
            session.add(
                IncidentEvent(
                    incident_id=incident.id,
                    event_id=event.id,
                    link_type="evidence",
                )
            )
        action = ResponseAction(
            incident_id=incident.id,
            action_type="force_password_reset",
            target="demo_user",
            reason=XSS_REASON if "<" in title else "fixture reason",
            risk_level="high",
            approval_status="proposed",
            execution_status="not_executed",
            simulated=True,
        )
        session.add(action)
        extra_id: uuid.UUID | None = None
        if extra_action is not None:
            extra = ResponseAction(
                incident_id=incident.id,
                action_type=extra_action[0],
                target=extra_action[1],
                reason="sibling fixture",
                risk_level="medium",
                approval_status="proposed",
                execution_status="not_executed",
                simulated=True,
            )
            session.add(extra)
            session.flush()
            extra_id = extra.id
        if include_investigation:
            investigation_id = uuid.uuid4()
            session.add(
                AgentRun(
                    investigation_id=investigation_id,
                    incident_id=incident.id,
                    agent_name="analysis",
                    status="completed",
                    structured_output={
                        "finding": XSS_FINDING
                        if "<" in title
                        else "Repeated failures then success.",
                        "reasoning_summary": "Evidence supports T1110.",
                        "confidence": "high",
                        "techniques": ["T1110"],
                        "facts": [
                            {"kind": "verified", "statement": "Failures clustered on one IP."}
                        ],
                        "evidence_event_ids": [],
                    },
                )
            )
            session.add(
                AgentRun(
                    investigation_id=investigation_id,
                    incident_id=incident.id,
                    agent_name="threat_intelligence",
                    status="completed",
                    structured_output={
                        "finding": "Lookup completed.",
                        "records": [
                            {
                                "indicator": "192.0.2.10",
                                "status": "unavailable",
                                "source": "none",
                                "provider": "none",
                                "summary": "Provider disabled.",
                            }
                        ],
                    },
                )
            )
        if include_other_incident:
            session.add(
                Incident(
                    title=OTHER_TITLE,
                    severity="low",
                    status="open",
                    summary="other",
                )
            )
        session.commit()
        return incident.id, action.id, extra_id
    finally:
        session.close()


def _assert_html_download(response, incident_id: uuid.UUID) -> str:
    assert response.status_code == 200, response.text
    content_type = response.headers["content-type"]
    assert content_type.startswith("text/html")
    assert "charset=utf-8" in content_type.lower()
    assert (
        response.headers["content-disposition"]
        == f'attachment; filename="incident-{incident_id}-report.html"'
    )
    assert response.headers["x-content-type-options"] == "nosniff"
    document = response.text
    assert document.lstrip().lower().startswith("<!doctype html>")
    assert "Generated at" in document
    return document


def test_report_success_headers_and_filename(client: TestClient) -> None:
    incident_id, _action_id, _extra = _insert_report_fixture(client)
    response = client.get(f"/api/incidents/{incident_id}/report")
    document = _assert_html_download(response, incident_id)
    assert str(incident_id) in document
    assert "Report fixture" in document
    assert "R1" in document
    assert "R2" in document


def test_report_unknown_incident_404(client: TestClient) -> None:
    missing = uuid.UUID("00000000-0000-4000-8000-000000000099")
    response = client.get(f"/api/incidents/{missing}/report")
    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "not_found"
    assert body["detail"] == "Incident not found"


def test_report_invalid_uuid_422(client: TestClient) -> None:
    response = client.get("/api/incidents/not-a-uuid/report")
    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


def test_report_missing_optional_fields(client: TestClient) -> None:
    session = client.app.state.session_factory()
    try:
        incident = Incident(title="Sparse incident", severity="low", status="open", summary="")
        session.add(incident)
        session.flush()
        event = SecurityEvent(
            timestamp=datetime(2026, 10, 21, 12, 0, tzinfo=UTC),
            event_type="login_success",
            source="linux_auth",
            raw_message="Accepted password",
        )
        session.add(event)
        session.flush()
        session.add(IncidentEvent(incident_id=incident.id, event_id=event.id, link_type="evidence"))
        session.add(
            AgentRun(
                investigation_id=uuid.uuid4(),
                incident_id=incident.id,
                agent_name="investigation",
                status="completed",
                structured_output={
                    "finding": None,
                    "techniques": None,
                    "facts": "not-a-list",
                    "records": None,
                    "actions": None,
                },
            )
        )
        session.add(
            ResponseAction(
                incident_id=incident.id,
                action_type="review_session",
                target=None,
                reason="optional target missing",
                risk_level="low",
                approval_status="proposed",
                execution_status="not_executed",
                simulated=True,
            )
        )
        session.commit()
        incident_id = incident.id
    finally:
        session.close()
    response = client.get(f"/api/incidents/{incident_id}/report")
    document = _assert_html_download(response, incident_id)
    assert "Sparse incident" in document
    assert "No detection rule identifiers" in document
    assert "No audit events recorded" in document
    assert "review_session" in document


def test_report_escapes_injected_markup(client: TestClient) -> None:
    incident_id, action_id, _extra = _insert_report_fixture(
        client, title=XSS_TITLE, summary=XSS_SUMMARY
    )
    session = client.app.state.session_factory()
    try:
        session.add(
            AuditLog(
                event_type="response_action.approved",
                actor="unverified",
                resource_type="response_action",
                resource_id=action_id,
                incident_id=incident_id,
                details={
                    "decision": XSS_TITLE,
                    "previous_approval_status": "proposed",
                    "resulting_approval_status": "approved",
                    "action_type": XSS_REASON,
                },
            )
        )
        session.commit()
    finally:
        session.close()
    response = client.get(f"/api/incidents/{incident_id}/report")
    document = _assert_html_download(response, incident_id)
    assert XSS_TITLE not in document
    assert XSS_SUMMARY not in document
    assert XSS_MESSAGE not in document
    assert XSS_REASON not in document
    assert XSS_FINDING not in document
    assert "&lt;script&gt;" in document
    assert "&lt;img" in document
    assert "&lt;svg" in document
    assert "&lt;iframe" in document
    probe = _TagProbe()
    probe.feed(document)
    assert "script" not in probe.tags
    assert "img" not in probe.tags
    assert "svg" not in probe.tags
    assert "iframe" not in probe.tags


def test_report_audit_history_and_action_states(client: TestClient) -> None:
    incident_id, action_id, extra_id = _insert_report_fixture(client)
    assert extra_id is not None
    approved = client.post(f"/api/actions/{action_id}/approve")
    rejected = client.post(f"/api/actions/{extra_id}/reject")
    assert approved.status_code == 200
    assert rejected.status_code == 200
    response = client.get(f"/api/incidents/{incident_id}/report")
    document = _assert_html_download(response, incident_id)
    assert "approved" in document
    assert "rejected" in document
    assert "response_action.approved" in document
    assert "response_action.rejected" in document
    assert "unverified" in document
    assert str(action_id) in document
    assert str(extra_id) in document
    assert "force_password_reset" in document
    assert "flag_ip_for_review" in document
    assert "T1110" in document
    assert "Brute Force" in document
    assert "192.0.2.10" in document
    assert "unavailable" in document


def test_report_never_describes_unexecuted_as_executed(client: TestClient) -> None:
    incident_id, action_id, extra_id = _insert_report_fixture(client)
    assert extra_id is not None
    assert client.post(f"/api/actions/{action_id}/approve").status_code == 200
    response = client.get(f"/api/incidents/{incident_id}/report")
    document = _assert_html_download(response, incident_id)
    assert "not_executed" in document
    assert "yes" in document
    assert "Not performed" in document
    assert "no live containment occurred" in document
    assert "simulated" in document.lower()
    scrubbed = document.replace("not_executed", "")
    assert "executed" not in scrubbed.lower()
    stored = _reload_action(client, action_id)
    assert stored.approval_status == "approved"
    assert stored.execution_status == "not_executed"
    assert stored.simulated is True


def test_report_does_not_leak_other_incidents_or_secrets(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    incident_id, _action_id, _extra = _insert_report_fixture(client, include_other_incident=True)
    with caplog.at_level(logging.DEBUG):
        response = client.get(f"/api/incidents/{incident_id}/report")
    document = _assert_html_download(response, incident_id)
    assert OTHER_TITLE not in document
    assert SECRET_TOKEN not in document
    assert "DATABASE_URL" not in document
    assert "postgresql+psycopg" not in document
    assert "LLM_API_KEY" not in document
    assert SECRET_TOKEN not in caplog.text


def test_development_without_token_can_download_report() -> None:
    with _app_client(app_env="development", analyst_api_token=None) as client:
        incident_id, _action_id, _extra = _insert_report_fixture(client, extra_action=None)
        response = client.get(f"/api/incidents/{incident_id}/report")
        _assert_html_download(response, incident_id)


def test_development_configured_token_rejects_missing_and_invalid_report() -> None:
    with _app_client(app_env="development", analyst_api_token=SECRET_TOKEN) as client:
        incident_id, _action_id, _extra = _insert_report_fixture(client, extra_action=None)
        missing = client.get(f"/api/incidents/{incident_id}/report")
        invalid = client.get(
            f"/api/incidents/{incident_id}/report",
            headers=_headers(f"{SECRET_TOKEN}-wrong"),
        )
        valid = client.get(
            f"/api/incidents/{incident_id}/report",
            headers=_headers(SECRET_TOKEN),
        )
        assert missing.status_code == 401
        assert invalid.status_code == 401
        for body in (missing.json(), invalid.json()):
            assert body["detail"] == "Invalid or missing analyst token"
            assert SECRET_TOKEN not in str(body)
        _assert_html_download(valid, incident_id)
        assert SECRET_TOKEN not in valid.text


def test_production_without_token_forbids_report() -> None:
    with _app_client(app_env="production", analyst_api_token=None) as client:
        incident_id, _action_id, _extra = _insert_report_fixture(client, extra_action=None)
        response = client.get(f"/api/incidents/{incident_id}/report")
        assert response.status_code == 403
        assert response.json()["detail"] == "ANALYST_API_TOKEN is required in production"


def test_production_configured_token_allows_report() -> None:
    with _app_client(app_env="production", analyst_api_token=SECRET_TOKEN) as client:
        incident_id, _action_id, _extra = _insert_report_fixture(client, extra_action=None)
        missing = client.get(f"/api/incidents/{incident_id}/report")
        valid = client.get(
            f"/api/incidents/{incident_id}/report",
            headers=_headers(SECRET_TOKEN),
        )
        assert missing.status_code == 401
        _assert_html_download(valid, incident_id)
        assert SECRET_TOKEN not in valid.text


def test_report_download_does_not_mutate_phase8_state(client: TestClient) -> None:
    incident_id, action_id = _insert_proposed(client)
    approve = client.post(f"/api/actions/{action_id}/approve")
    assert approve.status_code == 200
    before = client.get(f"/api/incidents/{incident_id}/audit-logs").json()
    report = client.get(f"/api/incidents/{incident_id}/report")
    _assert_html_download(report, incident_id)
    after = client.get(f"/api/incidents/{incident_id}/audit-logs").json()
    assert after == before
    stored = _reload_action(client, action_id)
    assert stored.approval_status == "approved"
    assert stored.execution_status == "not_executed"
    assert stored.simulated is True
    conflict = client.post(f"/api/actions/{action_id}/reject")
    assert conflict.status_code == 409
    repeat = client.post(f"/api/actions/{action_id}/approve")
    assert repeat.status_code == 200
    assert repeat.json()["decided_at"] == approve.json()["decided_at"]
    listed = client.get(f"/api/incidents/{incident_id}")
    assert listed.status_code == 200
    assert listed.json()["actions"][0]["approval_status"] == "approved"


def test_report_includes_live_investigation_without_claiming_execution(
    client: TestClient,
) -> None:
    incident_id = _open_incident(client)
    investigated = client.post(f"/api/incidents/{uuid.UUID(incident_id)}/investigate")
    assert investigated.status_code == 200, investigated.text
    response = client.get(f"/api/incidents/{incident_id}/report")
    document = _assert_html_download(response, uuid.UUID(incident_id))
    assert "Investigation findings" in document
    assert "investigation" in document
    assert (
        re.search(
            r"\b(was|were|has been|have been|successfully)\s+executed\b",
            document,
            flags=re.IGNORECASE,
        )
        is None
    )
    actions_start = document.index("Recommended response actions")
    history_start = document.index("Approval and rejection history")
    actions_section = document[actions_start:history_start].replace("not_executed", "")
    assert "executed" not in actions_section.lower()
    if re.search(r"force_password_reset|flag_ip_for_review|review_session|monitor", document):
        assert "Not performed" in document
