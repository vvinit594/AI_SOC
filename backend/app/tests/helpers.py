from app.core.config import Settings


def build_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "app_name": "AI-SOC API",
        "log_level": "WARNING",
        "cors_allowed_origins": "http://localhost:3000",
        "database_url": "sqlite:///:memory:",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)
