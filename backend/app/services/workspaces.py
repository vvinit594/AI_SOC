from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security_constants import LEGACY_WORKSPACE_ID, LEGACY_WORKSPACE_NAME
from app.core.time import utc_now
from app.db.models import Workspace, WorkspaceMembership


def ensure_legacy_workspace(session: Session) -> Workspace:
    workspace = session.get(Workspace, LEGACY_WORKSPACE_ID)
    if workspace is not None:
        return workspace
    workspace = Workspace(
        id=LEGACY_WORKSPACE_ID,
        name=LEGACY_WORKSPACE_NAME,
        kind="legacy",
        created_at=utc_now(),
    )
    session.add(workspace)
    session.flush()
    return workspace


def create_personal_workspace(session: Session, *, name: str) -> Workspace:
    workspace = Workspace(name=name[:120], kind="personal", created_at=utc_now())
    session.add(workspace)
    session.flush()
    return workspace


def add_owner_membership(
    session: Session, *, user_id: uuid.UUID, workspace_id: uuid.UUID
) -> WorkspaceMembership:
    membership = WorkspaceMembership(
        user_id=user_id,
        workspace_id=workspace_id,
        role="owner",
        created_at=utc_now(),
    )
    session.add(membership)
    session.flush()
    return membership


def get_membership(
    session: Session, *, user_id: uuid.UUID, workspace_id: uuid.UUID
) -> WorkspaceMembership | None:
    return session.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.user_id == user_id,
            WorkspaceMembership.workspace_id == workspace_id,
        )
    )
