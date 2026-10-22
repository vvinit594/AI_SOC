import os

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
os.environ.setdefault("LOG_LEVEL", "WARNING")

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


@pytest.fixture
def client() -> Generator[TestClient]:
    get_settings.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
