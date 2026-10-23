from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

try:
    import sqlalchemy  # noqa: F401
except ModuleNotFoundError as exc:
    raise RuntimeError(
        "SQLAlchemy is not installed in this interpreter. "
        "From backend/, use .venv\\Scripts\\python.exe -m pytest"
    ) from exc

from app.core.config import Settings
from app.db import models as _db_models  # noqa: F401
from app.db.base import Base
from app.db.seed import seed_demo_data
from app.main import create_app
from app.tests.helpers import build_settings


@pytest.fixture
def settings() -> Settings:
    return build_settings()


@pytest.fixture
def application(settings: Settings) -> FastAPI:
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    return app


@pytest.fixture
def client(application: FastAPI) -> Generator[TestClient]:
    with TestClient(application) as test_client:
        yield test_client


@pytest.fixture
def seed_db(application: FastAPI) -> dict[str, int]:
    session = application.state.session_factory()
    try:
        return seed_demo_data(session)
    finally:
        session.close()
