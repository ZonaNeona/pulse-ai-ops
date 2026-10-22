"""Overview: health of every module, the headline KPIs and one "do now" feed across modules."""

from datetime import date, datetime, timedelta
from typing import Any

from pulse.core import fmt
from pulse.data import Data
from pulse.modules import integrations
from pulse.modules.sales import pulse, signals
from pulse.seed import names

LATE_STAGE_SHARE = 0.35  # chance a late-stage deal closes within the month, for the forecast


def _workdays(start: date, end: date) -> int:
    return sum(1 for i in range((end - start).days + 1) if (start + timedelta(days=i)).weekday() < 5)


def revenue(data: Data) -> dict[str, Any]:
    start = integrations.month_start(data)
    end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    won = [d for d in data.deals if d.semantics == "success" and (d.moved or d.modified) >= start]
    fact = sum(d.amount for d in won)
    late = [
        d
        for d in data.deals
        if d.semantics == "process"
        and d.close_date
        and d.close_date <= end.date()
        and [s.id for s in next(f for f in data.funnels if f.id == d.funnel_id).stages].index(d.stage_id) >= 3
    ]
    plan = int(data.story.get("plan_month") or fact * 1.2)
    return {
        "fact": round(fact),
        "plan": plan,
        "forecast": round(fact + LATE_STAGE_SHARE * sum(d.amount for d in late)),
        "daysLeft": _workdays(data.now.date() + timedelta(days=1), end.date()),
    }


def _revenue_kpi(data: Data, rev: dict[str, Any]) -> dict[str, Any]:
    """Revenue against the plan's pace: where the month should be by today if the plan is to be met."""
    start = integrations.month_start(data)
    end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    elapsed = _workdays(start.date(), data.now.date()) / max(1, _workdays(start.date(), end.date()))
    expected = rev["plan"] * elapsed
    weeks = [start + timedelta(days=7 * i) for i in range(6) if start + timedelta(days=7 * i) <= data.now]
    spark = [
        sum(
            d.amount
            for d in data.deals
            if d.semantics == "success" and start <= (d.moved or d.modified) <= w + timedelta(days=7)
        )
        for w in weeks
    ]
    pace = fmt.pct_delta(rev["fact"], expected)
    month = fmt.MONTHS_NOMINATIVE[start.month - 1].lower()
    hint = f"по плану к сегодня {fmt.rub_short(expected)}"
    return pulse.kpi("revenue", f"Выручка, {month}", rev["fact"], "rub", delta=pace, spark=spark, hint=hint) | {
        "target": rev["plan"]
    }


def overview(data: Data, cards: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """`cards` — the AI modules' health, computed by the caller for the visitor's session (see `ai_cards`)."""
    sigs = signals.build(data)
    kpis = {k["key"]: k for k in pulse.kpis(data)}
    rec = integrations.reconciliation(data)
    rev = revenue(data)
    high = [s for s in sigs if s["severity"] == "high"]
    gap_sum = sum(g["amount"] for g in rec["gaps"])

    modules = [
        {
            "id": "sales",
            "title": "Продажи",
            "status": "danger" if len(high) > 2 else "warning" if sigs else "success",
            "headline": fmt.count(len(sigs), ("сигнал", "сигнала", "сигналов")),
            "detail": f"{fmt.count(len(high), ('срочный', 'срочных', 'срочных'))}: "
            + ", ".join(sorted({s["ruleLabel"].lower() for s in high})[:2])
            if high
            else "Срочного нет",
            "href": "/sales",
        },
        {
            "id": "integrations",
            "title": "Интеграции",
            "status": "warning" if rec["gaps"] else "success",
            "headline": fmt.count(len(rec["gaps"]), ("расхождение", "расхождения", "расхождений"))
            if rec["gaps"]
            else "Всё сходится",
            "detail": f"CRM ↔ 1С за месяц: {fmt.rub_short(gap_sum)}" if rec["gaps"] else "CRM и 1С совпадают",
            "href": "/integrations",
        },
    ]

    actions = []
    for s in sigs[:5]:
        actions.append(
            {
                "id": s["id"],
                "module": "sales",
                "severity": s["severity"],
                "title": s["title"],
                "reason": s["reason"],
                "action": s["action"],
                "owner": s["manager"],
                "age": fmt.age_short(s["ageHours"] * 60),
                "href": s.get("href", "/sales"),
            }
        )
    for g in rec["gaps"][:2]:
        actions.append(
            {
                "id": f"gap:{g['dealId']}",
                "module": "integrations",
                "severity": "medium",
                "title": f"{g['client']}: {fmt.rub_short(g['amount'])}",
                "reason": g["issue"],
                "action": "Поставить задачу",
                "owner": g["manager"],
                "age": "месяц",
                "href": "/integrations",
            }
        )
    modules += cards or []
    rank = {"high": 0, "medium": 1, "low": 2}
    actions.sort(key=lambda a: rank[a["severity"]])

    return {
        "company": {
            "name": names.COMPANY["name"],
            "industry": names.COMPANY["industry"],
            "today": fmt.day_title(datetime.combine(data.day, data.now.time())),
            "timezone": "Europe/Moscow",
        },
        "modules": modules,
        "kpis": [_revenue_kpi(data, rev), kpis["calls"], kpis["noCallback"], kpis["stale"]],
        "actions": actions[:7],
        "revenue": rev,
    }


def ai_cards(pending: list[Any], kb: dict[str, Any], spend: dict[str, Any], runs_today: int) -> list[dict[str, Any]]:
    """Documents, knowledge and agents cards from live state: the visitor's queue, the last eval, today's spend."""
    first = pending[0] if pending else None
    problem = next((c.detail for c in first.checks if not c.ok), "нужна проверка") if first else ""
    docs = {
        "id": "docs",
        "title": "Документы",
        "status": "danger" if any(d.status == "mismatch" for d in pending) else "warning" if pending else "success",
        "headline": f"{len(pending)} ждут человека" if pending else "Очередь пуста",
        "detail": f"№ {first.value('number')}: {problem}" if first else "Всё проверено и проведено",
        "href": "/docs",
    }
    passed, total = kb["evalPassed"], kb["evalTotal"]
    knowledge = {
        "id": "knowledge",
        "title": "Знания",
        "status": "success" if total and passed == total else "warning",
        "headline": f"Эталон {passed} из {total}",
        "detail": f"{fmt.count(kb['documents'], ('регламент', 'регламента', 'регламентов'))}, "
        f"отказы вне базы {kb['refusalsCorrect']} из {kb['refusalsTotal']}",
        "href": "/knowledge",
    }
    share = spend["spentUsd"] / spend["capUsd"] if spend["capUsd"] else 0
    agents = {
        "id": "agents",
        "title": "Агенты",
        "status": "danger" if share >= 1 else "warning" if share > 0.8 or not spend["modelConnected"] else "success",
        "headline": f"${spend['spentUsd']:.2f} из ${spend['capUsd']:.2f}".replace(".", ","),
        "detail": (fmt.count(runs_today, ("ход", "хода", "ходов")) + " агента сегодня")
        if spend["modelConnected"]
        else "Модель не подключена: работают готовые ответы",
        "href": "/under-the-hood",
    }
    return [docs, knowledge, agents]
