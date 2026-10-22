"""Log ingestion routes. Implemented in Phase 5."""

from fastapi import APIRouter

router = APIRouter(prefix="/logs", tags=["logs"])
