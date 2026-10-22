from fastapi import APIRouter

from app.api.routes import actions, incidents, investigations, logs, reports

api_router = APIRouter()
api_router.include_router(logs.router)
api_router.include_router(incidents.router)
api_router.include_router(investigations.router)
api_router.include_router(actions.router)
api_router.include_router(reports.router)
