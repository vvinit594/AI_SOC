from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_principal, get_optional_principal
from app.core.config import Settings, get_settings
from app.core.cookies import clear_auth_cookies, set_auth_cookies
from app.db.session import get_db
from app.schemas.auth import (
    CurrentUserRead,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from app.services.auth import (
    AuthError,
    Principal,
    authenticate_user,
    issue_session,
    register_account,
    request_password_recovery,
    require_csrf,
    reset_password,
    revoke_session,
    rotate_login_session,
    user_payload,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_UNCONFIGURED_DETAIL = "Password recovery is not configured"
_DEV_DETAIL = "Development recovery is available for this environment. Mail delivery was not used."


def _raise(exc: AuthError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _attach_session(
    response: Response,
    request: Request,
    settings: Settings,
    session_token: str,
    csrf_token: str,
) -> None:
    set_auth_cookies(
        response,
        session_token=session_token,
        csrf_token=csrf_token,
        settings=settings,
        request=request,
    )


@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RegisterResponse:
    try:
        user, workspace, membership = register_account(
            session,
            full_name=payload.full_name,
            email=str(payload.email),
            password=payload.password,
        )
        _row, raw_token, raw_csrf = issue_session(
            session,
            user=user,
            workspace=workspace,
            settings=settings,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except AuthError as exc:
        _raise(exc)
        raise
    _attach_session(response, request, settings, raw_token, raw_csrf)
    return user_payload(user, workspace, membership.role)


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    try:
        user = authenticate_user(
            session,
            email=str(payload.email),
            password=payload.password,
            ip_address=request.client.host if request.client else None,
        )
        workspace, membership, _row, raw_token, raw_csrf = rotate_login_session(
            session,
            user=user,
            settings=settings,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except AuthError as exc:
        _raise(exc)
        raise
    _attach_session(response, request, settings, raw_token, raw_csrf)
    return user_payload(user, workspace, membership.role)


@router.post("/logout", response_model=LogoutResponse)
def logout(
    request: Request,
    response: Response,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    principal: Principal | None = Depends(get_optional_principal),
    x_csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> LogoutResponse:
    if principal is not None:
        from app.core.security_constants import CSRF_COOKIE_NAME

        try:
            require_csrf(principal, x_csrf_token, request.cookies.get(CSRF_COOKIE_NAME))
        except AuthError as exc:
            _raise(exc)
            raise
        revoke_session(session, principal.session)
    clear_auth_cookies(response, settings=settings, request=request)
    return LogoutResponse()


@router.get("/me", response_model=CurrentUserRead)
def me(principal: Principal = Depends(get_current_principal)) -> CurrentUserRead:
    return user_payload(principal.user, principal.workspace, principal.membership.role)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ForgotPasswordResponse:
    try:
        delivery, token = request_password_recovery(
            session, email=str(payload.email), settings=settings
        )
    except AuthError as exc:
        _raise(exc)
        raise
    return ForgotPasswordResponse(
        detail=_DEV_DETAIL if delivery == "development" else _UNCONFIGURED_DETAIL,
        delivery=delivery,
        dev_recovery_token=token,
    )


@router.post("/reset-password", response_model=ResetPasswordResponse)
def reset_password_route(
    payload: ResetPasswordRequest,
    session: Session = Depends(get_db),
) -> ResetPasswordResponse:
    try:
        reset_password(session, token=payload.token, password=payload.password)
    except AuthError as exc:
        _raise(exc)
        raise
    return ResetPasswordResponse()
