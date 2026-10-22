"""Call facts the other sales views build on: callbacks, per-day slices, the call feed and its review."""

from bisect import bisect_right
from collections import defaultdict
from datetime import date, datetime
from statistics import median
from typing import Any

from pulse.core import fmt
from pulse.crm.model import Call
from pulse.data import Data
from pulse.modules.sales import quality


def on_day(data: Data, d: date, *, until: datetime | None = None) -> list[Call]:
    return [c for c in data.calls if c.started.date() == d and (until is None or c.started.time() <= until.time())]


def callbacks(data: Data) -> dict[int, float | None]:
    """For every missed call: minutes until the client was called back (or answered later), None if never."""
    if "callbacks" in data.cache:
        cached: dict[int, float | None] = data.cache["callbacks"]
        return cached
    by_phone: dict[str, list[Call]] = defaultdict(list)
    for c in data.calls:
        by_phone[c.phone].append(c)
    result: dict[int, float | None] = {}
    for phone_calls in by_phone.values():
        starts = [c.started for c in phone_calls]
        for c in phone_calls:
            if not c.missed:
                continue
            later = phone_calls[bisect_right(starts, c.started) :]
            back = next((x for x in later if x.direction == "out" or not x.missed), None)
            result[c.id] = (back.started - c.started).total_seconds() / 60 if back else None
    data.cache["callbacks"] = result
    return result


def median_callback(data: Data, since: datetime, until: datetime) -> float | None:
    cb = callbacks(data)
    values = [v for c in data.calls if c.missed and since <= c.started < until and (v := cb[c.id]) is not None]
    return median(values) if values else None


def outcome(data: Data, c: Call) -> str:
    if c.missed:
        return "Пропущен"
    if c.direction == "out" and c.duration_s < 25:
        return "Не дозвонился"
    a = data.assessments.get(c.id)
    if a:
        return quality.outcome(a)
    return "Входящий разговор" if c.direction == "in" else "Исходящий разговор"


def as_item(data: Data, c: Call) -> dict[str, Any]:
    a = data.assessments.get(c.id)
    when = (
        c.started.strftime("%H:%M")
        if c.started.date() == data.day
        else f"{fmt.WEEKDAYS[c.started.weekday()]} {c.started:%H:%M}"
    )
    return {
        "id": c.id,
        "manager": data.name(c.user_id),
        "managerId": c.user_id,
        "client": data.client(c.company_id),
        "direction": c.direction,
        "durationSec": c.duration_s,
        "at": when,
        "score": a.score if a else None,
        "outcome": outcome(data, c),
        "missed": c.missed,
    }


def feed(data: Data, manager: int | None = None, limit: int = 80) -> list[dict[str, Any]]:
    """Calls of the working day and the one before, newest first. Unanswered dial attempts are left out."""
    days = {data.day, *data.workdays_before(data.day, 1)}
    calls = [
        c
        for c in reversed(data.calls)
        if c.started.date() in days
        and (manager is None or c.user_id == manager)
        and not (c.direction == "out" and c.duration_s < 25)
    ]
    return [as_item(data, c) for c in calls[:limit]]


def review(data: Data, call_id: int) -> dict[str, Any] | None:
    call = next((c for c in data.calls if c.id == call_id), None)
    a = data.assessments.get(call_id)
    if not call or not a:
        return None
    return {
        "call": as_item(data, call),
        **quality.review(a, manager=data.name(call.user_id), duration_s=call.duration_s),
    }
