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
from app.tests.helpers import CookieClient, build_settings, register_user


@pytest.fixture
def settings() -> Settings:
    return build_settings()


@pytest.fixture
def application(settings: Settings) -> FastAPI:
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    return app


@pytest.fixture
def anonymous_client(application: FastAPI) -> Generator[TestClient]:
    with TestClient(application) as test_client:
        yield test_client


@pytest.fixture
def client(application: FastAPI) -> Generator[TestClient]:
    with CookieClient(application) as test_client:
        register_user(test_client)
        yield test_client


@pytest.fixture
def seed_db(application: FastAPI, client: TestClient) -> dict[str, int]:
    workspace_id = client.get("/api/auth/me").json()["workspace"]["id"]
    session = application.state.session_factory()
    try:
        from uuid import UUID

        return seed_demo_data(session, workspace_id=UUID(workspace_id))
    finally:
        session.close()
