ALLOWED_ORIGIN = "http://localhost:3000"
DISALLOWED_ORIGIN = "http://evil.example"


def test_health_includes_cors_allow_origin(client) -> None:
    response = client.get("/health", headers={"Origin": ALLOWED_ORIGIN})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN


def test_preflight_allows_configured_origin(client) -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code in {200, 204}
    assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN


def test_disallowed_origin_is_not_reflected(client) -> None:
    response = client.get("/health", headers={"Origin": DISALLOWED_ORIGIN})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") != DISALLOWED_ORIGIN


def test_wildcard_cors_is_rejected() -> None:
    from app.core.config import Settings

    settings = Settings(cors_allowed_origins="*")
    try:
        _ = settings.cors_origins
        raise AssertionError("wildcard CORS should be rejected")
    except ValueError as exc:
        assert "explicit allowlist" in str(exc)
