import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.common import ErrorResponse
from app.schemas.investigations import InvestigationRead
from app.services.investigations import get_investigation
from app.services.progress import iter_sse_events

router = APIRouter(prefix="/investigations", tags=["investigations"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


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
    responses={404: {"model": ErrorResponse}},
)
def stream_investigation(
    investigation_id: uuid.UUID,
    request: Request,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    factory = request.app.state.session_factory
    session = factory()
    try:
        loaded = get_investigation(session, investigation_id)
    finally:
        session.close()
    if loaded is None:
        raise HTTPException(status_code=404, detail="Investigation not found")

    def chunks():
        yield from iter_sse_events(
            factory,
            investigation_id,
            last_event_id=last_event_id,
        )

    return StreamingResponse(
        chunks(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
