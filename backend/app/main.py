import logging
import sys
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.router import api_router
from app.api.routes.health import router as health_router
from app.core.config import Settings, get_settings, redact_database_url
from app.core.logging import configure_logging
from app.db import models as _db_models  # noqa: F401
from app.db.session import create_engine_from_settings, create_session_factory
from app.schemas.common import ErrorResponse

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings if settings is not None else get_settings()
    configure_logging(resolved)
    engine = create_engine_from_settings(resolved)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
        logger.info("Python executable: %s (%s)", sys.executable, sys.version.split()[0])
        logger.info("Database target: %s", redact_database_url(resolved.database_url))
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            logger.info("Database connection ok")
        except Exception:
            logger.exception("Database connection failed")
        yield
        engine.dispose()

    application = FastAPI(
        title=resolved.app_name,
        version=__version__,
        description="AI-SOC backend: log processing, detection, and agent orchestration.",
        docs_url="/docs" if resolved.docs_enabled else None,
        redoc_url="/redoc" if resolved.docs_enabled else None,
        openapi_url="/openapi.json" if resolved.docs_enabled else None,
        lifespan=lifespan,
    )
    application.state.engine = engine
    application.state.session_factory = session_factory

    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "Last-Event-ID"],
    )

    def provide_settings() -> Settings:
        return resolved

    application.dependency_overrides[get_settings] = provide_settings
    application.include_router(health_router)
    application.include_router(api_router, prefix="/api")

    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        error_name = "not_found" if exc.status_code == 404 else "http_error"
        payload = ErrorResponse(
            error=error_name,
            detail=str(exc.detail),
            code=error_name,
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        payload = ErrorResponse(
            error="validation_error",
            detail="Request validation failed",
            code="validation_error",
        )
        content: Mapping[str, Any] = {
            **payload.model_dump(),
            "errors": jsonable_encoder(exc.errors()),
        }
        return JSONResponse(status_code=422, content=content)

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled application error method=%s path=%s",
            request.method,
            request.url.path,
            exc_info=exc,
        )
        payload = ErrorResponse(
            error="internal_error",
            detail="An unexpected error occurred",
            code="internal_error",
        )
        return JSONResponse(status_code=500, content=payload.model_dump())

    return application


app = create_app()
