from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["development", "test", "production"]


def parse_cors_origins(value: str) -> list[str]:
    origins = [origin.strip() for origin in value.split(",") if origin.strip()]
    if not origins:
        raise ValueError("CORS_ALLOWED_ORIGINS must list at least one origin")
    if any(origin == "*" for origin in origins):
        raise ValueError("CORS_ALLOWED_ORIGINS must be an explicit allowlist, not '*'")
    return origins


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and optional `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: AppEnv = "development"
    app_name: str = "AI-SOC API"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_allowed_origins: str = Field(
        default="http://localhost:3000",
        description="Comma-separated explicit frontend origins. Never '*'.",
    )
    database_url: str = Field(
        default="postgresql+psycopg://aisoc:aisoc@localhost:5432/aisoc",
        description="SQLAlchemy database URL.",
    )
    db_pool_size: int = Field(default=5, ge=1)
    db_max_overflow: int = Field(default=5, ge=0)
    max_upload_size_mb: int = Field(default=10, ge=1)
    max_events_per_upload: int = Field(default=50000, ge=1)

    @field_validator("database_url")
    @classmethod
    def database_url_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("DATABASE_URL must not be empty")
        return value.strip()

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return value.upper()

    @field_validator("cors_allowed_origins")
    @classmethod
    def validate_cors_allowed_origins(cls, value: str) -> str:
        parse_cors_origins(value)
        return value

    @property
    def cors_origins(self) -> list[str]:
        return parse_cors_origins(self.cors_allowed_origins)

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def docs_enabled(self) -> bool:
        return self.app_env != "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
