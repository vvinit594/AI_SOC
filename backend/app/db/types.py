from datetime import UTC, datetime

from sqlalchemy.engine import Dialect
from sqlalchemy.types import DateTime, TypeDecorator


class UTCDateTime(TypeDecorator):
    """Timezone-aware UTC datetime that round-trips correctly on SQLite and PostgreSQL."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None:
            raise ValueError("datetime must include a timezone; store UTC")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
