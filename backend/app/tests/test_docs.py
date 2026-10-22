from fastapi.testclient import TestClient

from app.main import create_app
from app.tests.helpers import build_settings


def test_docs_available_outside_production(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_docs_are_disabled_in_production() -> None:
    settings = build_settings(app_env="production")
    with TestClient(create_app(settings)) as test_client:
        docs = test_client.get("/docs")
        openapi = test_client.get("/openapi.json")
        redoc = test_client.get("/redoc")

    assert docs.status_code == 404
    assert docs.json()["error"] == "not_found"
    assert openapi.status_code == 404
    assert openapi.json()["error"] == "not_found"
    assert redoc.status_code == 404
    assert redoc.json()["error"] == "not_found"


def test_health_still_works_in_production() -> None:
    settings = build_settings(app_env="production")
    with TestClient(create_app(settings)) as test_client:
        response = test_client.get("/health")

    assert response.status_code == 200
    assert response.json()["environment"] == "production"
    assert response.json()["status"] == "ok"
