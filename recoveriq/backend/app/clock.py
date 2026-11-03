"""Business clock. In demo mode an offset can be applied so judges can see quiet hours and
broken promises without waiting. All business rules read time from here, never datetime.now()."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .config import settings

try:
    LOCAL_TZ = ZoneInfo(settings.timezone)
except Exception:  # Windows without tzdata: IST has no DST, a fixed offset is exact
    LOCAL_TZ = timezone(timedelta(hours=5, minutes=30), "IST")

_offset_seconds: float = 0.0


def set_offset(seconds: float) -> None:
    global _offset_seconds
    _offset_seconds = seconds


def get_offset() -> float:
    return _offset_seconds


def utcnow() -> datetime:
    """Naive UTC datetime (what we store), shifted by the demo offset."""
    return datetime.utcnow() + timedelta(seconds=_offset_seconds)


def local_now() -> datetime:
    return utcnow().replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ)


def local_today() -> date:
    return local_now().date()


def to_local(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ)
