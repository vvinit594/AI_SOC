from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def require_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must include a timezone; store UTC")
    return value.astimezone(UTC)
