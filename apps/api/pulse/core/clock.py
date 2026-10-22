"""Single source of "now". Tests freeze it; the demo seed anchors its dates to it."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from pulse.core.config import get_settings

_frozen: datetime | None = None


def tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def now() -> datetime:
    return _frozen if _frozen is not None else datetime.now(tz()).replace(microsecond=0)


def today() -> date:
    return now().date()


def freeze(at: datetime | None) -> None:
    """Pin the clock (tests, deterministic screenshots). `None` releases it."""
    global _frozen
    _frozen = at


def b24(dt: datetime) -> str:
    """Bitrix24 REST datetime format: 2026-10-12T21:48:15+03:00."""
    return dt.astimezone(tz()).isoformat(timespec="seconds")


def parse(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=tz())


def workdays_back(day: date, n: int) -> date:
    """The date `n` working days before `day` (weekends skipped)."""
    d = day
    while n > 0:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d
