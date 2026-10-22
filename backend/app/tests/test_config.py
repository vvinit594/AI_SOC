from app.core.config import Settings


def test_cors_origins_are_trimmed() -> None:
    settings = Settings(
        cors_allowed_origins="http://localhost:3000, https://aisoc.example"
    )
    assert settings.cors_origins == [
        "http://localhost:3000",
        "https://aisoc.example",
    ]


def test_empty_cors_list_is_rejected() -> None:
    settings = Settings(cors_allowed_origins="  ,  ")
    try:
        _ = settings.cors_origins
        raise AssertionError("empty CORS list should be rejected")
    except ValueError as exc:
        assert "at least one origin" in str(exc)


def test_docs_disabled_in_production() -> None:
    settings = Settings(app_env="production")
    assert settings.docs_enabled is False
    assert settings.is_production is True
