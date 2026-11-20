from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)
    password: str = Field(min_length=1, max_length=128)


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    kind: str
    role: str


class CurrentUserRead(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    workspace: WorkspaceRead
    created_at: datetime


class RegisterResponse(CurrentUserRead):
    pass


class LoginResponse(CurrentUserRead):
    pass


class LogoutResponse(BaseModel):
    ok: bool = True


class ForgotPasswordResponse(BaseModel):
    detail: str
    delivery: str
    dev_recovery_token: str | None = None


class ResetPasswordResponse(BaseModel):
    ok: bool = True
