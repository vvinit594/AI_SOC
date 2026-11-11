from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.core.config import Settings, get_settings
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    responses={
        200: {"description": "The API process is running and the database is reachable"},
        503: {"description": "The API process is running but the database is unavailable"},
    },
)
def get_health(request: Request, settings: Settings = Depends(get_settings)) -> HealthResponse:
    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        raise StarletteHTTPException(status_code=503, detail="Database unavailable")
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        raise StarletteHTTPException(status_code=503, detail="Database unavailable") from None
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.app_env,
        version=__version__,
    )
