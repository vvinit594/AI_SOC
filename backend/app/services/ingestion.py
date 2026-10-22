from __future__ import annotations

import csv
import io
import json
from typing import Any, Literal

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.demo_data import demo_events
from app.schemas.enums import DemoScenario
from app.schemas.events import SecurityEventCreate
from app.schemas.ingestion import LogUploadResponse, RecordError, ScenarioLoadResponse
from app.services import events as event_service

_FIELD_ALIASES = {
    "eventType": "event_type",
    "sourceIp": "source_ip",
    "destinationIp": "destination_ip",
    "rawMessage": "raw_message",
}
_IGNORED_FIELDS = {"created_at", "createdAt"}
_EVENT_FIELDS = {
    "id",
    "timestamp",
    "event_type",
    "source_ip",
    "destination_ip",
    "username",
    "hostname",
    "action",
    "source",
    "raw_message",
    "scenario",
}


class IngestFileError(ValueError):
    def __init__(
        self,
        detail: str,
        *,
        status_code: int = 400,
        errors: list[RecordError] | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code
        self.errors = errors or []


def detect_format(filename: str | None, content_type: str | None) -> Literal["json", "csv"]:
    name = (filename or "").lower()
    media = (content_type or "").split(";")[0].strip().lower()
    if name.endswith(".json") or media in {"application/json", "text/json"}:
        return "json"
    if name.endswith(".csv") or media in {"text/csv", "application/csv"}:
        return "csv"
    raise IngestFileError("Unsupported file type; upload JSON or CSV")


def parse_upload_bytes(payload: bytes, fmt: Literal["json", "csv"]) -> list[dict[str, Any]]:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise IngestFileError("Upload must be UTF-8 text") from exc
    if not text.strip():
        raise IngestFileError("Upload is empty")
    if fmt == "json":
        return _parse_json(text)
    return _parse_csv(text)


def ingest_records(
    session: Session,
    records: list[dict[str, Any]],
    settings: Settings,
) -> LogUploadResponse:
    if not records:
        raise IngestFileError("No events found in upload")
    if len(records) > settings.max_events_per_upload:
        raise IngestFileError(
            f"Upload contains more than {settings.max_events_per_upload} events"
        )

    valid: list[dict[str, object]] = []
    errors: list[RecordError] = []
    for index, record in enumerate(records):
        try:
            payload = SecurityEventCreate.model_validate(_normalize_record(record))
        except (ValidationError, TypeError, ValueError) as exc:
            errors.append(RecordError(index=index, detail=_record_error_detail(exc)))
            continue
        valid.append(payload.model_dump())

    if not valid:
        raise IngestFileError("No valid events in upload", errors=errors)

    event_ids = event_service.upsert_events(session, valid)
    return LogUploadResponse(
        accepted=len(event_ids),
        rejected=len(errors),
        event_ids=event_ids,
        errors=errors,
    )


def load_scenario(session: Session, scenario: DemoScenario) -> ScenarioLoadResponse:
    records = [event for event in demo_events() if event["scenario"] == scenario]
    event_ids = event_service.upsert_events(session, records)
    return ScenarioLoadResponse(
        scenario=scenario, accepted=len(event_ids), event_ids=event_ids
    )


def _parse_json(text: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise IngestFileError("Upload is not valid JSON") from exc
    if isinstance(parsed, list):
        return [_require_object(item, index) for index, item in enumerate(parsed)]
    if isinstance(parsed, dict):
        for key in ("items", "events"):
            nested = parsed.get(key)
            if isinstance(nested, list):
                return [_require_object(item, index) for index, item in enumerate(nested)]
        return [parsed]
    raise IngestFileError("JSON upload must be an object or an array of objects")


def _parse_csv(text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise IngestFileError("CSV upload is missing a header row")
    rows: list[dict[str, Any]] = []
    for row in reader:
        rows.append({key: _csv_value(value) for key, value in row.items() if key})
    return rows


def _csv_value(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _require_object(item: object, index: int) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise IngestFileError(f"Event at index {index} must be an object")
    return item


def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in record.items():
        if key in _IGNORED_FIELDS:
            continue
        field = _FIELD_ALIASES.get(key, key)
        if field in _EVENT_FIELDS:
            normalized[field] = value
    return normalized


def _record_error_detail(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first.get("loc", ()))
        message = str(first.get("msg", "invalid record"))
        return f"{location}: {message}" if location else message
    return str(exc)
