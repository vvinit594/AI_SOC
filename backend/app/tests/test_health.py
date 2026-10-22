from fastapi.testclient import TestClient

from app import __version__
from app.main import create_app
from app.tests.helpers import build_settings


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "AI-SOC API"
    assert body["environment"] == "test"
    assert body["version"] == __version__


def test_health_uses_injected_settings() -> None:
    settings = build_settings(app_name="Injected API", app_env="development")
    with TestClient(create_app(settings)) as test_client:
        body = test_client.get("/health").json()
    assert body["service"] == "Injected API"
    assert body["environment"] == "development"


def test_unknown_route_returns_json_error(client: TestClient) -> None:
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "not_found"
    assert body["code"] == "not_found"
    assert "detail" in body
