import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.common import ErrorResponse
from app.schemas.investigations import InvestigationRead
from app.services.investigations import get_investigation

router = APIRouter(prefix="/investigations", tags=["investigations"])


@router.get("/{investigation_id}", response_model=InvestigationRead, summary="Get investigation")
def read_investigation(
    investigation_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> InvestigationRead:
    loaded = get_investigation(session, investigation_id)
    if loaded is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return loaded


@router.get(
    "/{investigation_id}/stream",
    summary="Stream investigation progress",
    responses={501: {"model": ErrorResponse}},
)
def stream_investigation(investigation_id: uuid.UUID) -> None:
    raise HTTPException(
        status_code=501,
        detail="Live SSE progress is implemented in Phase 7",
    )
