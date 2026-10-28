"""Collection routes for reports. Incident download is GET /api/incidents/{id}/report."""

from fastapi import APIRouter

router = APIRouter(prefix="/reports", tags=["reports"])
