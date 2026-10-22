import logging
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.router import api_router
from app.api.routes.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.schemas.common import ErrorResponse

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings if settings is not None else get_settings()
    configure_logging(resolved)

    application = FastAPI(
        title=resolved.app_name,
        version=__version__,
        description="AI-SOC backend: log processing, detection, and agent orchestration.",
        docs_url="/docs" if resolved.docs_enabled else None,
        redoc_url="/redoc" if resolved.docs_enabled else None,
        openapi_url="/openapi.json" if resolved.docs_enabled else None,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
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
    async def unhandled_exception_handler(
        _request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled application error", exc_info=exc)
        payload = ErrorResponse(
            error="internal_error",
            detail="An unexpected error occurred",
            code="internal_error",
        )
        return JSONResponse(status_code=500, content=payload.model_dump())

    return application


app = create_app()
