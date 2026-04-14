from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.core.config import settings


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def to_local(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo(settings.TIMEZONE))


def local_now_iso() -> str:
    return to_local(utc_now()).isoformat(timespec="seconds")
