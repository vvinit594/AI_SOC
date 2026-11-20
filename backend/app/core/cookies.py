from __future__ import annotations

from fastapi import Request, Response

from app.core.config import Settings
from app.core.security_constants import CSRF_COOKIE_NAME, SESSION_COOKIE_NAME


def cookies_should_be_secure(settings: Settings, request: Request) -> bool:
    return settings.is_production or request.url.scheme == "https"


def set_auth_cookies(
    response: Response,
    *,
    session_token: str,
    csrf_token: str,
    settings: Settings,
    request: Request,
) -> None:
    secure = cookies_should_be_secure(settings, request)
    max_age = settings.session_ttl_seconds
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_token,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_auth_cookies(response: Response, *, settings: Settings, request: Request) -> None:
    secure = cookies_should_be_secure(settings, request)
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=secure,
        samesite="lax",
    )
    response.delete_cookie(
        CSRF_COOKIE_NAME,
        path="/",
        httponly=False,
        secure=secure,
        samesite="lax",
    )
