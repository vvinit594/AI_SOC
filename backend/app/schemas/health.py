from typing import Literal

from pydantic import BaseModel, Field

from app.core.config import AppEnv


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str
    environment: AppEnv
    version: str = Field(description="Application package version")
