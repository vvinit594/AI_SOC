import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.tests.helpers import build_settings


def test_cors_origins_are_trimmed() -> None:
    settings = build_settings(
        cors_allowed_origins="http://localhost:3000, https://aisoc.example"
    )
    assert settings.cors_origins == [
        "http://localhost:3000",
        "https://aisoc.example",
    ]


def test_empty_cors_list_is_rejected_at_construction() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, cors_allowed_origins="  ,  ")
    assert "at least one origin" in str(exc_info.value)


def test_docs_disabled_in_production() -> None:
    settings = build_settings(app_env="production")
    assert settings.docs_enabled is False
    assert settings.is_production is True


def test_blank_database_url_is_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, database_url="   ")
    assert "DATABASE_URL" in str(exc_info.value)


def test_test_settings_use_sqlite_memory() -> None:
    settings = build_settings()
    assert settings.database_url == "sqlite:///:memory:"
    assert settings.db_pool_size == 5
    assert settings.db_max_overflow == 5
