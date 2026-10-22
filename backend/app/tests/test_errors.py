from fastapi.testclient import TestClient

from app.main import create_app
from app.tests.helpers import build_settings


def test_validation_error_returns_json_envelope() -> None:
    application = create_app(build_settings())

    @application.get("/__test/echo")
    def echo(limit: int) -> dict[str, int]:
        return {"limit": limit}

    with TestClient(application) as test_client:
        response = test_client.get("/__test/echo", params={"limit": "not-an-int"})

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "validation_error"
    assert body["code"] == "validation_error"
    assert body["detail"] == "Request validation failed"
    assert isinstance(body["errors"], list)
    assert body["errors"]


def test_unhandled_exception_returns_json_envelope() -> None:
    application = create_app(build_settings())

    @application.get("/__test/boom")
    def boom() -> None:
        raise RuntimeError("boom")

    with TestClient(application, raise_server_exceptions=False) as test_client:
        response = test_client.get("/__test/boom")

    assert response.status_code == 500
    body = response.json()
    assert body["error"] == "internal_error"
    assert body["code"] == "internal_error"
    assert body["detail"] == "An unexpected error occurred"
    assert "boom" not in body["detail"]
