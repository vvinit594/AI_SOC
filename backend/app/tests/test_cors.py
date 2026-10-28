import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.tests.test_actions import _insert_proposed
from app.tests.test_reports import _insert_report_fixture

ALLOWED_ORIGIN = "http://localhost:3000"
DISALLOWED_ORIGIN = "http://evil.example"


def test_health_includes_cors_allow_origin(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": ALLOWED_ORIGIN})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN


def test_preflight_allows_configured_origin(client: TestClient) -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code in {200, 204}
    assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN


def test_disallowed_origin_is_not_reflected(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": DISALLOWED_ORIGIN})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") != DISALLOWED_ORIGIN


def test_content_disposition_is_exposed_to_the_browser(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": ALLOWED_ORIGIN})
    assert response.status_code == 200
    exposed = response.headers.get("access-control-expose-headers", "")
    assert "content-disposition" in exposed.lower()


def test_wildcard_cors_is_rejected_at_construction() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, cors_allowed_origins="*")
    assert "explicit allowlist" in str(exc_info.value)


def test_report_get_exposes_content_disposition_for_allowed_origin(client: TestClient) -> None:
    incident_id, _action_id, _extra = _insert_report_fixture(client, extra_action=None)
    response = client.get(
        f"/api/incidents/{incident_id}/report",
        headers={"Origin": ALLOWED_ORIGIN},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    exposed = response.headers.get("access-control-expose-headers", "")
    assert "content-disposition" in exposed.lower()
    assert "content-disposition" in response.headers
    assert response.headers["content-type"].startswith("text/html")


def test_report_preflight_allows_get_from_configured_origin(client: TestClient) -> None:
    incident_id, _action_id, _extra = _insert_report_fixture(client, extra_action=None)
    response = client.options(
        f"/api/incidents/{incident_id}/report",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "accept",
        },
    )
    assert response.status_code in {200, 204}
    assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN


def test_approve_preflight_allows_authorization_from_configured_origin(
    client: TestClient,
) -> None:
    _incident_id, action_id = _insert_proposed(client)
    response = client.options(
        f"/api/actions/{action_id}/approve",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code in {200, 204}
    assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    allowed_headers = response.headers.get("access-control-allow-headers", "").lower()
    assert "authorization" in allowed_headers


def test_protected_routes_do_not_reflect_disallowed_origin(client: TestClient) -> None:
    incident_id, action_id, _extra = _insert_report_fixture(client, extra_action=None)
    report = client.get(
        f"/api/incidents/{incident_id}/report",
        headers={"Origin": DISALLOWED_ORIGIN},
    )
    approve = client.post(
        f"/api/actions/{action_id}/approve",
        headers={"Origin": DISALLOWED_ORIGIN},
    )
    assert report.status_code == 200
    assert approve.status_code == 200
    assert report.headers.get("access-control-allow-origin") != DISALLOWED_ORIGIN
    assert approve.headers.get("access-control-allow-origin") != DISALLOWED_ORIGIN
