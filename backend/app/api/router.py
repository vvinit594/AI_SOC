from fastapi import APIRouter

from app.api.routes import (
    actions,
    events,
    incidents,
    investigations,
    logs,
    reports,
    scenarios,
)

api_router = APIRouter()
api_router.include_router(logs.router)
api_router.include_router(scenarios.router)
api_router.include_router(events.router)
api_router.include_router(incidents.router)
api_router.include_router(investigations.router)
api_router.include_router(actions.router)
api_router.include_router(reports.router)
