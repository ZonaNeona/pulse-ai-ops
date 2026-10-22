"""Instant answers to the questions people ask most, built from the same tools the agent uses.

No model and no cache of written texts: the intent is matched by keywords, the tools are called for real
(their timing goes into the trace) and the answer is assembled from what they returned, so the numbers
always match the screens. Anything that does not match a clear intent goes to the agent.
"""

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from pulse import data
from pulse.agents import tools
from pulse.agents.trace import Trace
from pulse.core import fmt
from pulse.modules.sales import pulse


@dataclass
class Reply:
    text: str
    sources: list[dict[str, str]] = field(default_factory=list)


Handler = Callable[[Trace, str], Awaitable[Reply]]


async def call(trace: Trace, name: str, args: dict[str, Any] | None = None, lane: str = "Инструменты") -> Any:
    args = args or {}
    label = name + ("(" + ", ".join(f"{k}={v}" for k, v in args.items()) + ")" if args else "")
    with trace.step("tool", name, label, lane) as info:
        result = await tools.run(name, args)
        info["detail"] = tools.brief(result)
    return result


def _short(v: float) -> str:
    return fmt.rub_short(v)


async def team(trace: Trace, q: str) -> Reply:
    rows = await call(trace, "team_status")
    weak = sorted((m for m in rows if m["status"] in ("danger", "warning")), key=lambda m: m["quality"])
    lines = ["**Кто проседает (звонки к норме этого часа, оценка звонков за 7 дней):**"]
    for m in weak[:4]:
        mark = "🔴" if m["status"] == "danger" else "🟡"
        lines.append(
            f"{mark} **{m['name']}** — {m['callsToday']} из {m['callsNorm']} звонков, оценка {m['quality']}/100, "
            f"просрочек {m['overdue']}. {m['note']}."
        )
    if not weak:
        lines.append("Все менеджеры идут в норме.")
    best = max(rows, key=lambda m: m["quality"])
    lines.append(f"\nЛучшая оценка звонков — **{best['name']}** ({best['quality']}/100).")
    return Reply("\n".join(lines), [{"label": "Команда", "href": "/sales/team"}])


async def stale(trace: Trace, q: str) -> Reply:
    rows = await call(trace, "get_deals", {"stale_only": True, "limit": 50})
    total = sum(r["amount"] for r in rows)
    lines = [
        f"**{fmt.count(len(rows), ('сделка', 'сделки', 'сделок'))} без движения {pulse.STALE_DAYS}+ дней** на "
        f"{_short(total)}:"
    ]
    for r in rows[:5]:
        lines.append(
            f"• **{r['title']}** ({r['client']}) — {_short(r['amount'])}, {r['daysIdle']} дн. на стадии "
            f"«{r['stageName']}», {r['manager']}"
        )
    if len(rows) > 5:
        lines.append(f"…и ещё {len(rows) - 5}.")
    if rows:
        lines.append("\nТакие сделки разбираются на планёрке — «Регламент согласования сделок и договоров», § 2.2.")
    return Reply("\n".join(lines), [{"label": "Сделки без движения", "href": "/sales/deals"}])


async def reconcile(trace: Trace, q: str) -> Reply:
    r = await call(trace, "reconciliation")
    gap = r["crmAmount"] - r["erpAmount"]
    lines = [
        f"**{r['period']}:** в CRM оплачено {fmt.count(r['crmDeals'], ('сделка', 'сделки', 'сделок'))} на "
        f"{_short(r['crmAmount'])}, "
        f"в 1С проведено {r['erpPosted']} реализаций на {_short(r['erpAmount'])}. Разница **{_short(gap)}**.",
    ]
    for g in r["gaps"][:5]:
        lines.append(f"• {g['deal']} ({g['client']}) — {_short(g['amount'])}: {g['issue']}, {g['manager']}")
    return Reply("\n".join(lines), [{"label": "Сверка CRM ↔ 1С", "href": "/integrations"}])


async def worst_call(trace: Trace, q: str) -> Reply:
    feed = await call(trace, "call_feed", {"limit": 200})
    scored = [c for c in feed if c.get("score") is not None]
    if not scored:
        return Reply("За сегодня и прошлый рабочий день разобранных звонков нет.")
    worst = min(scored, key=lambda c: c["score"])
    review = await call(trace, "call_review", {"call_id": worst["id"]})
    if "error" in review:
        return Reply(
            f"Худший звонок — #{worst['id']} ({worst['manager']}, {worst['score']}/100), но разбора по нему нет."
        )
    lines = [
        f"**Худший звонок — {worst['manager']} → {worst['client']}, {worst['score']}/100** "
        f"({fmt.num(worst['durationSec'] // 60)} мин)."
    ]
    weak = sorted(review.get("criteria", []), key=lambda c: c["score"] / max(c.get("max", 10), 1))[:3]
    for c in weak:
        quote = f" — «{c['quote']}»" if c.get("quote") else ""
        lines.append(f"• {c['label']}: {c['score']}/{c.get('max', 10)}{quote}")
    if review.get("advice"):
        lines.append("\nЧто поправить: " + "; ".join(a[0].lower() + a[1:] for a in review["advice"]) + ".")
    return Reply("\n".join(lines), [{"label": "Разбор звонка", "href": f"/sales/calls?call={worst['id']}"}])


async def documents(trace: Trace, q: str) -> Reply:
    rows = await call(trace, "docs_queue")
    if not rows:
        return Reply(
            "Сейчас ни один документ не ждёт решения — всё, что пришло, прошло проверки и проведено.",
            [{"label": "Документы", "href": "/docs"}],
        )
    lines = [f"**Ждут решения человека: {len(rows)}**"]
    for d in rows:
        problem = "; ".join(d["problems"]) or "нужна проверка"
        lines.append(f"• № {d['number']}, {d['counterparty']}, {_short(d['amount'])} — {problem}")
    lines.append("\nПодтвердить или отклонить можно на экране «Документы»: граф продолжит работу с места остановки.")
    return Reply("\n".join(lines), [{"label": "Документы", "href": "/docs"}])


def _signals(rule: str, title: str) -> Handler:
    async def handler(trace: Trace, q: str) -> Reply:
        rows = await call(trace, "get_signals", {"rule": rule, "limit": 10})
        if not rows:
            return Reply(f"{title}: сейчас нет.", [{"label": "Сигналы", "href": "/"}])
        lines = [f"**{title}: {len(rows)}**"]
        lines += [f"• {s['title']} — {s['reason']}. {s['action']}" for s in rows[:6]]
        return Reply("\n".join(lines), [{"label": "Сделать сейчас", "href": "/"}])

    return handler


async def stock(trace: Trace, q: str) -> Reply:
    rows = await call(trace, "erp_stock")
    low = [s for s in rows if s["free"] <= 0] or sorted(rows, key=lambda s: s["free"])[:3]
    lines = ["**Остатки 1С — что заканчивается:**"]
    lines += [
        f"• {s['name']}: свободно {fmt.num(s['free'])} {s['unit']} (резерв {fmt.num(s['reserved'])}), "
        f"поставка {s['supplier']} — {s['leadDays']} дн."
        for s in low[:5]
    ]
    return Reply("\n".join(lines), [{"label": "1С", "href": "/integrations"}])


async def revenue(trace: Trace, q: str) -> Reply:
    p = await call(trace, "sales_pulse")
    r = p["revenue"]
    pct = round(r["fact"] / r["plan"] * 100) if r["plan"] else 0
    text = (
        f"**Выручка месяца: {_short(r['fact'])} из {_short(r['plan'])} ({pct} %).** Прогноз к концу месяца — "
        f"{_short(r['forecast'])}, "
        f"рабочих дней осталось {r['daysLeft']}."
    )
    return Reply(text, [{"label": "Обзор", "href": "/"}])


# (pattern, handler); the first match wins. Patterns are deliberately narrow — a vague question is the
# agent's job, not a guess here.
INTENTS: list[tuple[re.Pattern[str], Handler]] = [
    (re.compile(r"просел|проседа|отста[её]т|хуже всех|кто .*норм"), team),
    (re.compile(r"завис|без движения|застрял|застря"), stale),
    (re.compile(r"сверк|сравни .*(1с|оплат)|оплат.* 1с|расхожден"), reconcile),
    (re.compile(r"худш\w* звон|плох\w* звон|разбери .*звон"), worst_call),
    (re.compile(r"документ.*(ждут|подтвержд|провер)|ждут подтвержд"), documents),
    (re.compile(r"пропущенн|не перезвон"), _signals("no-callback", "Пропущенные без перезвона")),
    (re.compile(r"просроч\w* задач|просрочк"), _signals("overdue-task", "Просроченные задачи")),
    (re.compile(r"остат|склад|заканчива"), stock),
    (re.compile(r"выручк|план продаж|выполнение плана"), revenue),
]


# A question that asks "why", wants advice or narrows to a person is not the generic one: the agent answers it.
SPECIFIC = re.compile(r"почему|зачем|посовет|что делать|как (исправ|улучш|поднять)|если |прогноз на")


def _names() -> list[str]:
    """Stems of managers' surnames and first names: «у Кузнецовой» must not get the whole team's answer."""
    out = []
    for u in data.load().team:
        out += [part.lower().replace("ё", "е")[:5] for part in u.name.split()]
    return out


def match(question: str) -> Handler | None:
    q = question.lower().replace("ё", "е")
    if SPECIFIC.search(q) or any(stem in q for stem in _names()):
        return None
    found = {h for p, h in INTENTS if p.search(q)}
    # Two topics in one question («сравни оплаты и покажи документы») — a single canned answer would drop half.
    return found.pop() if len(found) == 1 else None
