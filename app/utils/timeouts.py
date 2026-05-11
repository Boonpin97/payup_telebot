"""Time helpers for session expiry."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def utcnow() -> datetime:
    """Timezone-aware UTC ``datetime`` (Firestore-friendly)."""
    return datetime.now(tz=timezone.utc)


def expires_at(seconds: int, *, base: datetime | None = None) -> datetime:
    return (base or utcnow()) + timedelta(seconds=seconds)


def is_expired(expires_at_dt: datetime, *, now: datetime | None = None) -> bool:
    if expires_at_dt is None:
        return True
    if expires_at_dt.tzinfo is None:
        expires_at_dt = expires_at_dt.replace(tzinfo=timezone.utc)
    return (now or utcnow()) >= expires_at_dt
