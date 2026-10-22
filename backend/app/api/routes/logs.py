from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.common import ErrorResponse
from app.schemas.ingestion import LogUploadResponse
from app.services.ingestion import (
    IngestFileError,
    detect_format,
    ingest_records,
    parse_upload_bytes,
)

router = APIRouter(prefix="/logs", tags=["logs"])


@router.post("/upload", response_model=LogUploadResponse, summary="Upload JSON or CSV events")
async def upload_logs(
    file: UploadFile,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LogUploadResponse | JSONResponse:
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    payload = await file.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise HTTPException(status_code=413, detail="Upload exceeds MAX_UPLOAD_SIZE_MB")

    try:
        fmt = detect_format(file.filename, file.content_type)
        records = parse_upload_bytes(payload, fmt)
        return ingest_records(session, records, settings)
    except IngestFileError as exc:
        if exc.errors:
            return JSONResponse(
                status_code=400,
                content=jsonable_encoder(
                    {
                        **ErrorResponse(
                            error="ingest_error",
                            detail=exc.detail,
                            code="ingest_error",
                        ).model_dump(),
                        "errors": [error.model_dump() for error in exc.errors],
                    }
                ),
            )
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
