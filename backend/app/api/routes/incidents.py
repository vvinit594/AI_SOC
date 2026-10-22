"""Incident listing and detection routes. Implemented in Phases 4–5."""

from fastapi import APIRouter

router = APIRouter(prefix="/incidents", tags=["incidents"])
