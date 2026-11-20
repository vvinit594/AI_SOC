from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.auth import AnalystAuthError, resolve_actor
from app.core.config import Settings, get_settings
from app.core.security_constants import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, SESSION_COOKIE_NAME
from app.db.models import Incident, ResponseAction
from app.db.session import get_db
from app.services.auth import AuthError, Principal, load_principal_from_token, require_csrf
from app.services.incidents import get_incident


@dataclass(frozen=True)
class AccessContext:
    actor: str
    principal: Principal | None
    workspace_id: UUID | None


def _client_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    return request.client.host


def get_optional_principal(
    request: Request,
    session: Session = Depends(get_db),
) -> Principal | None:
    return load_principal_from_token(session, request.cookies.get(SESSION_COOKIE_NAME))


def get_current_principal(
    request: Request,
    session: Session = Depends(get_db),
    x_csrf_token: Annotated[str | None, Header(alias=CSRF_HEADER_NAME)] = None,
) -> Principal:
    principal = load_principal_from_token(session, request.cookies.get(SESSION_COOKIE_NAME))
    if principal is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
        try:
            require_csrf(principal, x_csrf_token, request.cookies.get(CSRF_COOKIE_NAME))
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return principal


def require_human_session(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> Principal:
    return principal


def resolve_access(
    request: Request,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    authorization: Annotated[str | None, Header()] = None,
    x_csrf_token: Annotated[str | None, Header(alias=CSRF_HEADER_NAME)] = None,
) -> AccessContext:
    """Human session wins. Otherwise fall back to the shared analyst token."""
    principal = load_principal_from_token(session, request.cookies.get(SESSION_COOKIE_NAME))
    if principal is not None:
        if request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            try:
                require_csrf(principal, x_csrf_token, request.cookies.get(CSRF_COOKIE_NAME))
            except AuthError as exc:
                raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
        return AccessContext(
            actor=principal.actor,
            principal=principal,
            workspace_id=principal.workspace_id,
        )
    try:
        actor = resolve_actor(settings, authorization)
    except AnalystAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return AccessContext(actor=actor, principal=None, workspace_id=None)


def workspace_incident_or_404(
    session: Session,
    incident_id: UUID,
    access: AccessContext,
) -> Incident:
    incident = get_incident(session, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    if access.principal is not None and incident.workspace_id != access.workspace_id:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


def workspace_action_or_404(
    session: Session,
    action: ResponseAction | None,
    access: AccessContext,
) -> ResponseAction:
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")
    incident = session.get(Incident, action.incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Action not found")
    if access.principal is not None and incident.workspace_id != access.workspace_id:
        raise HTTPException(status_code=404, detail="Action not found")
    return action


CurrentUser = Annotated[Principal, Depends(get_current_principal)]
Access = Annotated[AccessContext, Depends(resolve_access)]
ClientIp = Annotated[str | None, Depends(_client_ip)]
