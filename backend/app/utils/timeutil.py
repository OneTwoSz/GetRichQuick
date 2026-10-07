"""UTC helpers. SQLite returns timezone-naive datetimes even for
DateTime(timezone=True) columns, so anything compared with "now" goes
through as_utc() first."""
from datetime import datetime, timezone
from typing import Optional


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def is_past(value: Optional[datetime]) -> bool:
    """True when `value` is set and already in the past (None = never)."""
    return value is not None and as_utc(value) <= utcnow()
