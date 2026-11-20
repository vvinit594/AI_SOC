from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security_constants import CSRF_COOKIE_NAME
from app.services.workspaces import ensure_legacy_workspace

DEFAULT_TEST_PASSWORD = "CorrectHorseBattery1"

AUTH_TABLES = {
    "users",
    "workspaces",
    "workspace_memberships",
    "user_sessions",
    "login_attempts",
    "password_recovery_tokens",
}

TENANT_TABLES = {
    "security_events",
    "incidents",
    "incident_events",
    "agent_runs",
    "response_actions",
    "audit_logs",
}


def build_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "app_name": "AI-SOC API",
        "log_level": "WARNING",
        "cors_allowed_origins": "http://localhost:3000",
        "database_url": "sqlite:///:memory:",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


class CookieClient(TestClient):
    """Test client that sends the CSRF header from the readable CSRF cookie."""

    def request(self, method: str, url: str, **kwargs: object):  # type: ignore[override]
        headers = dict(kwargs.get("headers") or {})  # type: ignore[arg-type]
        if str(method).upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            if not any(str(key).lower() == "x-csrf-token" for key in headers):
                csrf = self.cookies.get(CSRF_COOKIE_NAME)
                if csrf:
                    headers["X-CSRF-Token"] = csrf
                    kwargs["headers"] = headers
        return super().request(method, url, **kwargs)


def register_user(
    client: TestClient,
    *,
    email: str = "analyst@example.com",
    password: str = DEFAULT_TEST_PASSWORD,
    full_name: str = "Test Analyst",
) -> dict[str, object]:
    response = client.post(
        "/api/auth/register",
        json={"full_name": full_name, "email": email, "password": password},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert "password" not in body
    assert "password_hash" not in body
    return body


def resolve_workspace_id(client: TestClient, session: Session) -> uuid.UUID:
    me = client.get("/api/auth/me")
    if me.status_code == 200:
        return uuid.UUID(me.json()["workspace"]["id"])
    return ensure_legacy_workspace(session).id
