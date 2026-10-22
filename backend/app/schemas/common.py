from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Consistent JSON error envelope for all HTTP failures."""

    error: str = Field(description="Stable machine-readable error name")
    detail: str = Field(description="Human-readable explanation")
    code: str = Field(description="Application error code")
