"""Sales pulse: today's KPIs against the same hour of previous working days, and the 14-day call chart."""

from datetime import date, datetime, timedelta
from statistics import mean
from typing import Any

from pulse.core import fmt
from pulse.data import Data
from pulse.modules.sales import calls as calls_mod

STALE_DAYS = 7


def _same_hour(data: Data, d: date) -> datetime:
    """The moment on day `d` that corresponds to "now" on the current working day."""
    ref = data.now if data.day == data.now.date() else datetime.combine(data.day, datetime.max.time(), data.now.tzinfo)
    return datetime.combine(d, ref.time(), ref.tzinfo)


def _baseline(data: Data, counter: Any, days: int = 5) -> float:
    return float(mean(counter(d, _same_hour(data, d)) for d in data.workdays_before(data.day, days)))


def kpi(
    key: str,
    label: str,
    value: float | None,
    unit: str,
    *,
    delta: int | None,
    spark: list[float],
    hint: str,
    tone: str = "neutral",
    invert: bool = False,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "value": value,
        "unit": unit,
        "delta": delta,
        "invert": invert,
        "spark": spark,
        "hint": hint,
        "tone": tone,
    }


def open_stale(data: Data) -> list[Any]:
    return [
        d
        for d in data.deals
        if d.semantics == "process" and d.last_activity and (data.now - d.last_activity).days >= STALE_DAYS
    ]


def no_callback(data: Data, since: datetime) -> tuple[list[Any], int]:
    cb = calls_mod.callbacks(data)
    missed = [c for c in data.calls if c.missed and c.started >= since]
    return [c for c in missed if cb.get(c.id) is None], len(missed)


def quality_avg(data: Data, since: datetime, until: datetime) -> float | None:
    scores = [a.score for c in data.calls if since <= c.started < until and (a := data.assessments.get(c.id))]
    return round(mean(scores)) if scores else None


def kpis(data: Data) -> list[dict[str, Any]]:
    day, now = data.day, data.now
    recent = [*reversed(data.workdays_before(day, 9)), day]

    def calls_until(d: date, until: datetime) -> int:
        return sum(1 for c in calls_mod.on_day(data, d) if c.started <= until and not c.missed)

    def deals_until(d: date, until: datetime) -> int:
        return sum(1 for x in data.deals if x.created.date() == d and x.created <= until)

    today_calls = calls_until(day, _same_hour(data, day))
    calls_k = kpi(
        "calls",
        "Звонки сегодня",
        today_calls,
        "count",
        delta=fmt.pct_delta(today_calls, _baseline(data, calls_until)),
        spark=[calls_until(d, _same_hour(data, d)) for d in recent],
        hint="к этому часу",
    )

    start_prev = datetime.combine(data.workdays_before(day, 1)[0], datetime.min.time(), now.tzinfo)
    pending, missed_total = no_callback(data, start_prev)
    missed_k = kpi(
        "noCallback",
        "Без перезвона",
        len(pending),
        "count",
        delta=None,
        invert=True,
        spark=[sum(1 for c in calls_mod.on_day(data, d) if c.missed) for d in recent],
        hint=f"из {missed_total} пропущенных",
        tone="danger" if pending else "success",
    )

    week = now - timedelta(days=7)
    cb_now = calls_mod.median_callback(data, week, now)
    cb_prev = calls_mod.median_callback(data, week - timedelta(days=7), week)
    cb_k = kpi(
        "callback",
        "Медиана перезвона",
        round(cb_now) if cb_now is not None else None,
        "min",
        delta=fmt.pct_delta(cb_now or 0, cb_prev or 0),
        invert=True,
        spark=[],
        hint="цель — 15 минут",
        tone="success" if cb_now is not None and cb_now <= 15 else "warning",
    )

    new_deals = deals_until(day, _same_hour(data, day))
    deals_k = kpi(
        "newDeals",
        "Новые сделки",
        new_deals,
        "count",
        delta=fmt.pct_delta(new_deals, _baseline(data, deals_until)),
        spark=[deals_until(d, _same_hour(data, d)) for d in recent],
        hint="созданы сегодня",
    )

    stale = open_stale(data)
    stale_k = kpi(
        "stale",
        "Сделки без движения",
        len(stale),
        "count",
        delta=None,
        invert=True,
        spark=[],
        hint=f"{fmt.rub_short(sum(d.amount for d in stale))} без контакта",
        tone="warning" if stale else "success",
    )

    q_now = quality_avg(data, week, now)
    q_prev = quality_avg(data, week - timedelta(days=7), week)
    q_spark = [
        quality_avg(
            data,
            datetime.combine(d, datetime.min.time(), now.tzinfo),
            datetime.combine(d, datetime.max.time(), now.tzinfo),
        )
        for d in recent
    ]
    quality_k = kpi(
        "quality",
        "Оценка звонков",
        q_now,
        "score",
        delta=fmt.pct_delta(q_now or 0, q_prev or 0),
        spark=[q for q in q_spark if q is not None],
        hint="за 7 дней, из 100",
    )
    return [calls_k, missed_k, cb_k, deals_k, stale_k, quality_k]


def series(data: Data, days: int = 14) -> list[dict[str, Any]]:
    out = []
    for i in range(days - 1, -1, -1):
        d = data.now.date() - timedelta(days=i)
        day_calls = calls_mod.on_day(data, d)
        out.append(
            {
                "key": d.isoformat(),
                "label": f"{d.day} {fmt.WEEKDAYS[d.weekday()]}",
                "weekend": d.weekday() >= 5,
                "out": sum(1 for c in day_calls if c.direction == "out"),
                "in": sum(1 for c in day_calls if c.direction == "in" and not c.missed),
                "missed": sum(1 for c in day_calls if c.missed),
            }
        )
    return out
