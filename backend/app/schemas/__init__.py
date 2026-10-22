"""Pydantic request and response schemas."""

from app.schemas.common import ErrorResponse
from app.schemas.health import HealthResponse

__all__ = ["ErrorResponse", "HealthResponse"]
