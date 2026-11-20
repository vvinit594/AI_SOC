from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.passwords import (
    PasswordPolicyError,
    burn_verify_time,
    hash_password,
    validate_password,
    verify_password,
)
from app.core.security_constants import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    LOGIN_MAX_FAILURES_PER_EMAIL_IP,
    LOGIN_MAX_FAILURES_PER_IP,
    LOGIN_WINDOW_SECONDS,
    RECOVERY_TTL_SECONDS,
    SESSION_COOKIE_NAME,
)
from app.core.time import utc_now
from app.core.tokens import hash_token, new_urlsafe_token, tokens_match
from app.db.models import (
    LoginAttempt,
    PasswordRecoveryToken,
    User,
    UserSession,
    Workspace,
    WorkspaceMembership,
)
from app.schemas.auth import CurrentUserRead, WorkspaceRead
from app.services.workspaces import add_owner_membership, create_personal_workspace


class AuthError(ValueError):
    def __init__(self, detail: str, *, status_code: int, code: str = "http_error") -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code
        self.code = code


@dataclass
class Principal:
    user: User
    workspace: Workspace
    membership: WorkspaceMembership
    session: UserSession

    @property
    def workspace_id(self) -> uuid.UUID:
        return self.workspace.id

    @property
    def actor(self) -> str:
        return f"user:{self.user.id}"


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_full_name(full_name: str) -> str:
    cleaned = " ".join(full_name.split())
    if not cleaned:
        raise AuthError("Full name is required", status_code=422, code="validation_error")
    return cleaned[:120]


def user_payload(user: User, workspace: Workspace, role: str) -> CurrentUserRead:
    return CurrentUserRead(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        created_at=user.created_at,
        workspace=WorkspaceRead(
            id=workspace.id, name=workspace.name, kind=workspace.kind, role=role
        ),
    )


def register_account(
    session: Session,
    *,
    full_name: str,
    email: str,
    password: str,
) -> tuple[User, Workspace, WorkspaceMembership]:
    name = normalize_full_name(full_name)
    normalized = normalize_email(email)
    try:
        validate_password(password, email=normalized)
    except PasswordPolicyError as exc:
        raise AuthError(exc.detail, status_code=422, code="validation_error") from exc

    existing = session.scalar(select(User).where(User.email == normalized))
    if existing is not None:
        raise AuthError(
            "An account with this email already exists", status_code=409, code="conflict"
        )

    user = User(
        full_name=name,
        email=normalized,
        password_hash=hash_password(password),
        created_at=utc_now(),
    )
    session.add(user)
    session.flush()
    workspace = create_personal_workspace(session, name=f"{name}'s workspace")
    membership = add_owner_membership(session, user_id=user.id, workspace_id=workspace.id)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise AuthError(
            "An account with this email already exists", status_code=409, code="conflict"
        ) from exc
    session.refresh(user)
    session.refresh(workspace)
    session.refresh(membership)
    return user, workspace, membership


def _count_failures(
    session: Session,
    *,
    email: str | None,
    ip_address: str | None,
    since,
) -> int:
    filters = [
        LoginAttempt.succeeded.is_(False),
        LoginAttempt.attempted_at >= since,
    ]
    if email is not None:
        filters.append(LoginAttempt.email == email)
    if ip_address is not None:
        filters.append(LoginAttempt.ip_address == ip_address)
    return session.scalar(select(func.count()).select_from(LoginAttempt).where(*filters)) or 0


def _record_attempt(
    session: Session, *, email: str, ip_address: str | None, succeeded: bool
) -> None:
    session.add(
        LoginAttempt(
            email=email,
            ip_address=ip_address,
            succeeded=succeeded,
            attempted_at=utc_now(),
        )
    )
    session.commit()


def _login_limited(session: Session, *, email: str, ip_address: str | None) -> bool:
    since = utc_now() - timedelta(seconds=LOGIN_WINDOW_SECONDS)
    if (
        _count_failures(session, email=email, ip_address=ip_address, since=since)
        >= LOGIN_MAX_FAILURES_PER_EMAIL_IP
    ):
        return True
    if ip_address and _count_failures(session, email=None, ip_address=ip_address, since=since) >= (
        LOGIN_MAX_FAILURES_PER_IP
    ):
        return True
    return False


def authenticate_user(
    session: Session,
    *,
    email: str,
    password: str,
    ip_address: str | None,
) -> User:
    normalized = normalize_email(email)
    if _login_limited(session, email=normalized, ip_address=ip_address):
        raise AuthError(
            "Too many login attempts. Try again later.",
            status_code=429,
            code="rate_limited",
        )

    user = session.scalar(select(User).where(User.email == normalized))
    if user is None:
        burn_verify_time()
        _record_attempt(session, email=normalized, ip_address=ip_address, succeeded=False)
        raise AuthError("Invalid email or password", status_code=401, code="unauthenticated")
    if not verify_password(password, user.password_hash):
        _record_attempt(session, email=normalized, ip_address=ip_address, succeeded=False)
        raise AuthError("Invalid email or password", status_code=401, code="unauthenticated")
    _record_attempt(session, email=normalized, ip_address=ip_address, succeeded=True)
    return user


def issue_session(
    session: Session,
    *,
    user: User,
    workspace: Workspace,
    settings: Settings,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[UserSession, str, str]:
    raw_token = new_urlsafe_token()
    raw_csrf = new_urlsafe_token()
    now = utc_now()
    row = UserSession(
        user_id=user.id,
        workspace_id=workspace.id,
        token_hash=hash_token(raw_token),
        csrf_hash=hash_token(raw_csrf),
        expires_at=now + timedelta(seconds=settings.session_ttl_seconds),
        created_at=now,
        last_seen_at=now,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:255] or None,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row, raw_token, raw_csrf


def rotate_login_session(
    session: Session,
    *,
    user: User,
    settings: Settings,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[Workspace, WorkspaceMembership, UserSession, str, str]:
    membership = session.scalar(
        select(WorkspaceMembership)
        .where(WorkspaceMembership.user_id == user.id, WorkspaceMembership.role == "owner")
        .order_by(WorkspaceMembership.created_at.asc())
    )
    if membership is None:
        raise AuthError("Account is missing a workspace", status_code=500, code="internal_error")
    workspace = session.get(Workspace, membership.workspace_id)
    if workspace is None:
        raise AuthError("Account is missing a workspace", status_code=500, code="internal_error")
    _revoke_user_sessions(session, user.id)
    row, raw_token, raw_csrf = issue_session(
        session,
        user=user,
        workspace=workspace,
        settings=settings,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return workspace, membership, row, raw_token, raw_csrf


def _revoke_user_sessions(session: Session, user_id: uuid.UUID) -> None:
    now = utc_now()
    rows = list(session.scalars(select(UserSession).where(UserSession.user_id == user_id)))
    for row in rows:
        if row.revoked_at is None:
            row.revoked_at = now
    session.commit()


def revoke_session(session: Session, row: UserSession) -> None:
    if row.revoked_at is None:
        row.revoked_at = utc_now()
        session.commit()


def load_principal_from_token(session: Session, raw_token: str | None) -> Principal | None:
    if not raw_token:
        return None
    token_hash = hash_token(raw_token)
    row = session.scalar(select(UserSession).where(UserSession.token_hash == token_hash))
    if row is None or row.revoked_at is not None:
        return None
    if row.expires_at <= utc_now():
        return None
    user = session.get(User, row.user_id)
    workspace = session.get(Workspace, row.workspace_id)
    membership = session.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.user_id == row.user_id,
            WorkspaceMembership.workspace_id == row.workspace_id,
        )
    )
    if user is None or workspace is None or membership is None:
        return None
    row.last_seen_at = utc_now()
    session.commit()
    return Principal(user=user, workspace=workspace, membership=membership, session=row)


def require_csrf(principal: Principal, header_token: str | None, cookie_token: str | None) -> None:
    if not header_token or not cookie_token:
        raise AuthError("CSRF token missing", status_code=403, code="csrf_failed")
    if not tokens_match(header_token, principal.session.csrf_hash):
        raise AuthError("CSRF token invalid", status_code=403, code="csrf_failed")
    if not tokens_match(cookie_token, principal.session.csrf_hash):
        raise AuthError("CSRF token invalid", status_code=403, code="csrf_failed")


def request_password_recovery(
    session: Session,
    *,
    email: str,
    settings: Settings,
) -> tuple[str, str | None]:
    """Return (delivery, dev_token). Never discloses whether the email exists in production."""
    if settings.smtp_url:
        raise AuthError(
            "Password recovery email delivery is not implemented yet",
            status_code=503,
            code="recovery_unconfigured",
        )
    if settings.is_production:
        raise AuthError(
            "Password recovery is not configured",
            status_code=503,
            code="recovery_unconfigured",
        )

    normalized = normalize_email(email)
    user = session.scalar(select(User).where(User.email == normalized))
    if user is None:
        return "development", None
    raw = new_urlsafe_token()
    now = utc_now()
    session.add(
        PasswordRecoveryToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=now + timedelta(seconds=RECOVERY_TTL_SECONDS),
            created_at=now,
        )
    )
    session.commit()
    return "development", raw


def reset_password(session: Session, *, token: str, password: str) -> None:
    token_hash = hash_token(token)
    row = session.scalar(
        select(PasswordRecoveryToken).where(PasswordRecoveryToken.token_hash == token_hash)
    )
    if row is None or row.used_at is not None or row.expires_at <= utc_now():
        raise AuthError("Invalid or expired recovery token", status_code=400, code="http_error")
    user = session.get(User, row.user_id)
    if user is None:
        raise AuthError("Invalid or expired recovery token", status_code=400, code="http_error")
    try:
        validate_password(password, email=user.email)
    except PasswordPolicyError as exc:
        raise AuthError(exc.detail, status_code=422, code="validation_error") from exc
    user.password_hash = hash_password(password)
    row.used_at = utc_now()
    _revoke_user_sessions(session, user.id)
    session.commit()


def cookie_names() -> tuple[str, str, str]:
    return SESSION_COOKIE_NAME, CSRF_COOKIE_NAME, CSRF_HEADER_NAME
