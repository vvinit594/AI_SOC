from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import BACKEND_ENV_FILE, Settings, redact_database_url
from app.tests.helpers import build_settings


def test_cors_origins_are_trimmed() -> None:
    settings = build_settings(cors_allowed_origins="http://localhost:3000, https://aisoc.example")
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


def test_backend_env_file_is_absolute_and_local() -> None:
    assert BACKEND_ENV_FILE.is_absolute()
    assert BACKEND_ENV_FILE.name == ".env"
    assert BACKEND_ENV_FILE.parent.name == "backend"
    assert Path(Settings.model_config["env_file"]) == BACKEND_ENV_FILE


def test_redact_database_url_hides_password() -> None:
    redacted = redact_database_url("postgresql+psycopg://aisoc:super-secret@localhost:55432/aisoc")
    assert "super-secret" not in redacted
    assert "55432" in redacted
    assert redacted.startswith("postgresql+psycopg://aisoc:***@localhost:55432/aisoc")
