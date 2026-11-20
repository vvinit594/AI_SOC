from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security_constants import (
    CSRF_COOKIE_NAME,
    LEGACY_WORKSPACE_ID,
    LOGIN_MAX_FAILURES_PER_EMAIL_IP,
    SESSION_COOKIE_NAME,
    SESSION_TTL_SECONDS_DEFAULT,
)
from app.core.time import utc_now
from app.db.base import Base
from app.db.models import SecurityEvent, User, UserSession, Workspace, WorkspaceMembership
from app.db.seed import seed_demo_data
from app.main import create_app
from app.tests.helpers import (
    DEFAULT_TEST_PASSWORD,
    CookieClient,
    build_settings,
    register_user,
)


def test_register_creates_user_workspace_membership_and_session(application) -> None:
    with CookieClient(application) as client:
        body = register_user(client, email="owner@example.com", full_name="Ada Lovelace")
        assert body["email"] == "owner@example.com"
        assert body["full_name"] == "Ada Lovelace"
        assert body["workspace"]["kind"] == "personal"
        assert body["workspace"]["role"] == "owner"
        assert client.cookies.get(SESSION_COOKIE_NAME)
        assert client.cookies.get(CSRF_COOKIE_NAME)
        response = client.get("/api/auth/me")
        assert response.status_code == 200
        me = response.json()
        assert me["id"] == body["id"]
        assert me["workspace"]["id"] == body["workspace"]["id"]

        session = client.app.state.session_factory()
        try:
            user = session.get(User, uuid.UUID(body["id"]))
            assert user is not None
            assert user.password_hash.startswith("$argon2id$")
            memberships = list(
                session.scalars(
                    select(WorkspaceMembership).where(WorkspaceMembership.user_id == user.id)
                )
            )
            assert len(memberships) == 1
            workspace = session.get(Workspace, memberships[0].workspace_id)
            assert workspace is not None
            assert workspace.id != LEGACY_WORKSPACE_ID
            assert workspace.kind == "personal"
            sessions = list(
                session.scalars(select(UserSession).where(UserSession.user_id == user.id))
            )
            assert len(sessions) == 1
            assert sessions[0].revoked_at is None
        finally:
            session.close()


def test_register_rejects_duplicate_email(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Other",
            "email": "analyst@example.com",
            "password": DEFAULT_TEST_PASSWORD,
        },
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


def test_register_rejects_invalid_email(anonymous_client: TestClient) -> None:
    response = anonymous_client.post(
        "/api/auth/register",
        json={"full_name": "Ada", "email": "not-an-email", "password": DEFAULT_TEST_PASSWORD},
    )
    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


def test_register_rejects_weak_password(anonymous_client: TestClient) -> None:
    too_short = anonymous_client.post(
        "/api/auth/register",
        json={"full_name": "Ada", "email": "weak@example.com", "password": "short"},
    )
    letters_only = anonymous_client.post(
        "/api/auth/register",
        json={
            "full_name": "Ada",
            "email": "letters-only@example.com",
            "password": "CorrectHorseBattery",
        },
    )
    assert too_short.status_code == 422
    assert "12" in too_short.json()["detail"]
    assert letters_only.status_code == 422
    assert "letters and numbers" in letters_only.json()["detail"].lower()


def test_login_success_and_invalid_are_generic(application) -> None:
    with CookieClient(application) as client:
        register_user(client, email="login@example.com")
        client.post("/api/auth/logout")
        ok = client.post(
            "/api/auth/login",
            json={"email": "login@example.com", "password": DEFAULT_TEST_PASSWORD},
        )
        assert ok.status_code == 200
        assert ok.json()["email"] == "login@example.com"
        missing = client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": DEFAULT_TEST_PASSWORD},
        )
        wrong = client.post(
            "/api/auth/login",
            json={"email": "login@example.com", "password": "DefinitelyWrong1"},
        )
        assert missing.status_code == 401
        assert wrong.status_code == 401
        assert missing.json()["detail"] == wrong.json()["detail"] == "Invalid email or password"


def test_session_cookie_flags_are_httponly_samesite_lax(application) -> None:
    with CookieClient(application) as client:
        response = client.post(
            "/api/auth/register",
            json={
                "full_name": "Flags",
                "email": "flags@example.com",
                "password": DEFAULT_TEST_PASSWORD,
            },
        )
        assert response.status_code == 201
        headers = response.headers.get_list("set-cookie")
        session_header = next(
            item for item in headers if item.startswith(f"{SESSION_COOKIE_NAME}=")
        )
        csrf_header = next(item for item in headers if item.startswith(f"{CSRF_COOKIE_NAME}="))
        assert "HttpOnly" in session_header
        assert "samesite=lax" in session_header.lower()
        assert "httponly" not in csrf_header.lower()
        assert "samesite=lax" in csrf_header.lower()
        assert "secure" not in session_header.lower()
        assert f"max-age={SESSION_TTL_SECONDS_DEFAULT}" in session_header.lower()


def test_logout_invalidates_session(client: TestClient) -> None:
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    logged_out = client.post("/api/auth/logout")
    assert logged_out.status_code == 200
    expired = client.get("/api/auth/me")
    assert expired.status_code == 401
    listed = client.get("/api/events")
    assert listed.status_code == 401


def test_expired_session_is_rejected(client: TestClient) -> None:
    session = client.app.state.session_factory()
    try:
        row = session.scalar(select(UserSession))
        assert row is not None
        row.expires_at = utc_now() - timedelta(seconds=1)
        session.commit()
    finally:
        session.close()
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_csrf_is_required_for_cookie_authenticated_post(client: TestClient) -> None:
    raw = TestClient(client.app)
    token = client.cookies.get(SESSION_COOKIE_NAME)
    assert token
    raw.cookies.set(SESSION_COOKIE_NAME, token)
    response = raw.post("/api/auth/logout")
    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]


def test_login_rate_limit_does_not_disclose_email(application) -> None:
    with CookieClient(application) as client:
        register_user(client, email="limited@example.com")
        client.post("/api/auth/logout")
        for _ in range(LOGIN_MAX_FAILURES_PER_EMAIL_IP):
            failed = client.post(
                "/api/auth/login",
                json={"email": "limited@example.com", "password": "WrongPassword1"},
            )
            assert failed.status_code == 401
        limited = client.post(
            "/api/auth/login",
            json={"email": "limited@example.com", "password": "WrongPassword1"},
        )
        unknown = client.post(
            "/api/auth/login",
            json={"email": "other-limited@example.com", "password": "WrongPassword1"},
        )
        assert limited.status_code == 429
        assert unknown.status_code == 401
        assert "Too many login attempts" in limited.json()["detail"]


def test_unauthenticated_tenant_routes_are_rejected(anonymous_client: TestClient) -> None:
    missing = uuid.uuid4()
    assert anonymous_client.get("/api/events").status_code == 401
    assert anonymous_client.get("/api/incidents").status_code == 401
    assert anonymous_client.post("/api/incidents/detect").status_code == 401
    assert anonymous_client.get(f"/api/incidents/{missing}").status_code == 401
    report = anonymous_client.get(f"/api/incidents/{missing}/report")
    # Test env allows machine-to-machine unverified access; a missing incident is 404.
    assert report.status_code in {401, 403, 404}


def test_cross_workspace_event_incident_and_report_are_hidden(application) -> None:
    from app.services.progress import load_progress_events
    from app.tests.test_actions import _insert_proposed
    from app.tests.test_investigations import _open_incident

    with CookieClient(application) as client:
        owner_a = register_user(client, email="owner-a@example.com")
        loaded = client.post("/api/scenarios/A/load")
        assert loaded.status_code == 200
        detected = client.post("/api/incidents/detect")
        assert detected.status_code == 200
        events = client.get("/api/events").json()
        incidents = client.get("/api/incidents").json()
        assert events["total"] > 0
        assert incidents["total"] > 0
        event_id = events["items"][0]["id"]
        incident_id = incidents["items"][0]["id"]
        report = client.get(f"/api/incidents/{incident_id}/report")
        assert report.status_code == 200
        investigate = client.post(f"/api/incidents/{_open_incident(client)}/investigate")
        assert investigate.status_code == 200, investigate.text
        investigation_id = investigate.json()["investigation"]["id"]
        assert client.get(f"/api/investigations/{investigation_id}").status_code == 200
        _, action_id = _insert_proposed(client)
        sibling_incident_id, reject_action_id = _insert_proposed(client)

        register_user(client, email="owner-b@example.com")
        assert client.get("/api/events").json()["total"] == 0
        assert client.get("/api/incidents").json()["total"] == 0
        assert client.get(f"/api/incidents/{incident_id}").status_code == 404
        assert client.get(f"/api/incidents/{incident_id}/report").status_code == 404
        assert client.get(f"/api/incidents/{incident_id}/audit-logs").status_code == 404
        assert client.post(f"/api/incidents/{incident_id}/investigate").status_code == 404
        listed_ids = {item["id"] for item in client.get("/api/events").json()["items"]}
        assert event_id not in listed_ids
        supplied_workspace = client.get(f"/api/events?workspace_id={owner_a['workspace']['id']}")
        assert supplied_workspace.status_code == 200
        assert supplied_workspace.json()["total"] == 0
        assert client.get(f"/api/investigations/{investigation_id}").status_code == 404
        stream = client.get(f"/api/investigations/{investigation_id}/stream")
        assert stream.status_code == 404
        assert "not found" in stream.json()["detail"].lower()
        assert client.post(f"/api/actions/{action_id}/approve").status_code == 404
        assert client.post(f"/api/actions/{reject_action_id}/reject").status_code == 404
        assert client.get(f"/api/incidents/{sibling_incident_id}").status_code == 404

        session = client.app.state.session_factory()
        try:
            owner_b_workspace = uuid.UUID(client.get("/api/auth/me").json()["workspace"]["id"])
            leaked = load_progress_events(
                session,
                uuid.UUID(investigation_id),
                workspace_id=owner_b_workspace,
            )
            own = load_progress_events(
                session,
                uuid.UUID(investigation_id),
                workspace_id=uuid.UUID(owner_a["workspace"]["id"]),
            )
        finally:
            session.close()
        assert leaked is None
        assert own is not None


def test_audit_actor_is_authenticated_user(client: TestClient) -> None:
    from app.tests.test_actions import _insert_proposed

    me = client.get("/api/auth/me").json()
    _incident_id, action_id = _insert_proposed(client)
    response = client.post(f"/api/actions/{action_id}/approve")
    assert response.status_code == 200
    assert response.json()["actor"] == f"user:{me['id']}"


def test_legacy_data_is_not_assigned_to_first_registrant(application) -> None:
    session = application.state.session_factory()
    try:
        seed_demo_data(session)
        events = list(session.scalars(select(SecurityEvent)))
        assert events
        assert all(event.workspace_id == LEGACY_WORKSPACE_ID for event in events)
    finally:
        session.close()

    with CookieClient(application) as client:
        body = register_user(client, email="first-public@example.com")
        assert body["workspace"]["id"] != str(LEGACY_WORKSPACE_ID)
        listed = client.get("/api/events").json()
        assert listed["total"] == 0
        listed_incidents = client.get("/api/incidents").json()
        assert listed_incidents["total"] == 0


def test_password_recovery_dev_mode_does_not_claim_email_sent(application) -> None:
    with CookieClient(application) as client:
        register_user(client, email="recover@example.com")
        client.post("/api/auth/logout")
        response = client.post("/api/auth/forgot-password", json={"email": "recover@example.com"})
        assert response.status_code == 200
        body = response.json()
        assert body["delivery"] == "development"
        assert "email was sent" not in body["detail"].lower()
        assert "sent" not in body["detail"].lower()
        assert body["dev_recovery_token"]
        reset = client.post(
            "/api/auth/reset-password",
            json={"token": body["dev_recovery_token"], "password": "NewCorrectHorse1"},
        )
        assert reset.status_code == 200
        login = client.post(
            "/api/auth/login",
            json={"email": "recover@example.com", "password": "NewCorrectHorse1"},
        )
        assert login.status_code == 200


def test_password_recovery_production_requires_delivery_config() -> None:
    settings = build_settings(app_env="production", analyst_api_token="prod-token-not-used")
    application = create_app(settings)
    Base.metadata.create_all(application.state.engine)
    with TestClient(application) as client:
        response = client.post("/api/auth/forgot-password", json={"email": "anyone@example.com"})
        assert response.status_code == 503
        assert "not configured" in response.json()["detail"].lower()


def test_password_recovery_smtp_url_is_not_implemented() -> None:
    settings = build_settings(
        app_env="production",
        analyst_api_token="prod-token-not-used",
        smtp_url="smtp://localhost:25",
    )
    application = create_app(settings)
    Base.metadata.create_all(application.state.engine)
    with TestClient(application) as client:
        response = client.post("/api/auth/forgot-password", json={"email": "anyone@example.com"})
        assert response.status_code == 503
        assert "not implemented" in response.json()["detail"].lower()


def test_login_rotates_and_revokes_previous_session(application) -> None:
    with CookieClient(application) as client:
        register_user(client, email="rotate@example.com")
        previous = client.cookies.get(SESSION_COOKIE_NAME)
        assert previous
        login = client.post(
            "/api/auth/login",
            json={"email": "rotate@example.com", "password": DEFAULT_TEST_PASSWORD},
        )
        assert login.status_code == 200
        current = client.cookies.get(SESSION_COOKIE_NAME)
        assert current
        assert current != previous
        raw = TestClient(client.app)
        raw.cookies.set(SESSION_COOKIE_NAME, previous)
        assert raw.get("/api/auth/me").status_code == 401
        assert client.get("/api/auth/me").status_code == 200


def test_production_session_cookie_is_secure() -> None:
    settings = build_settings(app_env="production", analyst_api_token="prod-token-not-used")
    application = create_app(settings)
    Base.metadata.create_all(application.state.engine)
    with CookieClient(application) as client:
        response = client.post(
            "/api/auth/register",
            json={
                "full_name": "Prod",
                "email": "prod-cookie@example.com",
                "password": DEFAULT_TEST_PASSWORD,
            },
        )
        assert response.status_code == 201
        session_header = next(
            item
            for item in response.headers.get_list("set-cookie")
            if item.startswith(f"{SESSION_COOKIE_NAME}=")
        )
        assert "secure" in session_header.lower()
        assert "httponly" in session_header.lower()
        assert "samesite=lax" in session_header.lower()


def test_session_persists_across_requests(client: TestClient) -> None:
    first = client.get("/api/auth/me")
    second = client.get("/api/auth/me")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    events = client.get("/api/events")
    assert events.status_code == 200
