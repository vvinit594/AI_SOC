from collections.abc import Generator

from fastapi import Request
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_engine_from_settings(settings: Settings) -> Engine:
    url = settings.database_url
    if url.startswith("sqlite"):
        kwargs: dict[str, object] = {
            "connect_args": {"check_same_thread": False},
        }
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool
        engine = create_engine(url, **kwargs)
        _enable_sqlite_foreign_keys(engine)
        return engine

    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db(request: Request) -> Generator[Session]:
    session: Session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()
