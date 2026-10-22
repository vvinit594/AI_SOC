from app import __version__


def test_health_returns_ok(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "AI-SOC API"
    assert body["environment"] in {"development", "test", "production"}
    assert body["version"] == __version__


def test_unknown_route_returns_json_error(client) -> None:
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "not_found"
    assert body["code"] == "not_found"
    assert "detail" in body


def test_openapi_available_outside_production(client) -> None:
    response = client.get("/docs")
    assert response.status_code == 200
