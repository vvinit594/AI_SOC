import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings

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
