"""Signals: rules that turn CRM facts into "do this now" items. Pure functions of the snapshot."""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from pulse.core import fmt
from pulse.data import Data
from pulse.modules.sales import calls as calls_mod
from pulse.modules.sales import pulse

NORM_CALLS = 45
DAYS = ("день", "дня", "дней")
MAX_TASK_SIGNALS = 5
SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}
RULES = {
    "no-callback": "Пропущенный без перезвона",
    "stale-deal": "Сделка без движения",
    "overdue-task": "Просроченная задача",
    "lead-no-action": "Лид без действия",
    "low-score": "Звонок ниже порога",
    "below-norm": "Звонков меньше нормы",
}


def signal(
    rule: str,
    sid: str,
    severity: str,
    title: str,
    reason: str,
    manager: str,
    client: str,
    at: datetime,
    action: str,
    now: datetime,
    href: str = "/sales",
) -> dict[str, Any]:
    return {
        "id": f"{rule}:{sid}",
        "rule": rule,
        "ruleLabel": RULES[rule],
        "severity": severity,
        "title": title,
        "reason": reason,
        "manager": manager,
        "client": client,
        "ageHours": round((now - at).total_seconds() / 3600, 1),
        "action": action,
        "href": href,
    }


def team_calls(data: Data, uid: int, day: Any) -> int:
    return sum(1 for c in calls_mod.on_day(data, day) if c.user_id == uid and not c.missed)


def build(data: Data) -> list[dict[str, Any]]:
    now = data.now
    out: list[dict[str, Any]] = []

    # 1. Missed incoming calls nobody returned, grouped by client.
    since = datetime.combine(data.workdays_before(data.day, 1)[0], datetime.min.time(), now.tzinfo)
    pending, _ = pulse.no_callback(data, since)
    by_phone: dict[str, list[Any]] = defaultdict(list)
    for c in pending:
        by_phone[c.phone].append(c)
    for group in by_phone.values():
        last = group[-1]
        client = data.client(last.company_id)
        n = len(group)
        what = (
            "пропущенный звонок"
            if n == 1
            else fmt.count(n, ("пропущенный звонок", "пропущенных звонка", "пропущенных звонков"))
        )
        out.append(
            signal(
                "no-callback",
                str(last.id),
                "high" if last.started.date() == data.day else "medium",
                f"{client}: {what}",
                f"Последний пропущенный — {fmt.ago((now - last.started).total_seconds() / 60)}, перезвона нет",
                data.name(last.user_id),
                client,
                last.started,
                "Перезвонить сейчас",
                now,
                "/sales/calls",
            )
        )

    # 2. Open deals without any contact for a week or more.
    for d in pulse.open_stale(data):
        idle = (now - d.last_activity).days if d.last_activity else 0
        large = d.amount >= 1_000_000
        out.append(
            signal(
                "stale-deal",
                str(d.id),
                "high" if large and idle >= 9 else "medium",
                f"{data.stage_name(d.stage_id)}: {fmt.rub_short(d.amount)}, тишина {fmt.count(idle, DAYS)}",
                f"«{d.title}» — нет звонков и задач с {d.last_activity:%d.%m}" if d.last_activity else d.title,
                data.name(d.assigned_id),
                data.client(d.company_id),
                d.last_activity or d.modified,
                "Уточнить решение у ЛПР",
                now,
                "/sales/deals",
            )
        )

    # 3. Overdue tasks: the few on the biggest deals one by one, everything else summed up per manager.
    deals = {d.id: d for d in data.deals}
    overdue = [t for t in data.tasks if not t.done and t.deadline and t.deadline < now]
    rest: dict[int, list[Any]] = defaultdict(list)
    big: list[tuple[Any, Any]] = []
    for t in overdue:
        deal = next((deals[int(b[2:])] for b in t.crm if b.startswith("D_") and int(b[2:]) in deals), None)
        if (
            deal
            and deal.amount >= 1_000_000
            and deal.semantics == "process"
            and t.deadline
            and (now - t.deadline).days <= 21
        ):
            big.append((t, deal))
        else:
            rest[t.responsible_id].append(t)
    big.sort(key=lambda x: -x[1].amount)
    for t, _deal in big[MAX_TASK_SIGNALS:]:
        rest[t.responsible_id].append(t)
    for t, deal in big[:MAX_TASK_SIGNALS]:
        days = (now - t.deadline).days if t.deadline else 0
        out.append(
            signal(
                "overdue-task",
                str(t.id),
                "high" if days >= 3 else "medium",
                t.title.split(":")[0],
                f"Просрочено на {fmt.count(max(1, days), DAYS)} · сделка {fmt.rub_short(deal.amount)}",
                data.name(t.responsible_id),
                data.client(deal.company_id),
                t.deadline or now,
                "Выполнить или перенести",
                now,
            )
        )
    for uid, tasks in rest.items():
        if len(tasks) < 2:
            continue
        oldest = min(tasks, key=lambda t: t.deadline or now)
        out.append(
            signal(
                "overdue-task",
                f"user{uid}",
                "medium",
                fmt.count(len(tasks), ("просроченная задача", "просроченные задачи", "просроченных задач")),
                f"Самая старая: «{oldest.title}»",
                data.name(uid),
                "—",
                oldest.deadline or now,
                "Разобрать с менеджером",
                now,
            )
        )

    # 4. New leads nobody touched for over an hour.
    for lead in data.leads:
        if lead.status_id == "NEW" and now - lead.created > timedelta(hours=1):
            hours = (now - lead.created).total_seconds() / 3600
            out.append(
                signal(
                    "lead-no-action",
                    str(lead.id),
                    "high" if hours >= 4 else "medium",
                    lead.title,
                    f"Лид создан {fmt.ago(hours * 60)}, ответственный не связался",
                    data.name(lead.assigned_id),
                    lead.company_title,
                    lead.created,
                    "Связаться в течение часа",
                    now,
                )
            )

    # 5. Calls the quality model scored below 50 in the last two working days: one item per manager.
    floor = datetime.combine(data.workdays_before(data.day, 2)[-1], datetime.min.time(), now.tzinfo)
    weak: dict[int, list[Any]] = defaultdict(list)
    for c in data.calls:
        a = data.assessments.get(c.id)
        if a and a.score < 50 and c.started >= floor:
            weak[c.user_id].append((a.score, c))
    for uid, items in weak.items():
        score, worst = min(items, key=lambda x: x[0])
        many = (
            f"{fmt.count(len(items), ('звонок', 'звонка', 'звонков'))} ниже 50 за два дня"
            if len(items) > 1
            else "Звонок ниже 50"
        )
        out.append(
            signal(
                "low-score",
                str(worst.id),
                "medium" if len(items) >= 3 else "low",
                f"Оценка {score} из 100: {data.client(worst.company_id)}",
                f"{many} · слабые места: потребность, ЛПР, следующий шаг",
                data.name(uid),
                data.client(worst.company_id),
                worst.started,
                "Разобрать звонок на планёрке",
                now,
                f"/sales/calls?id={worst.id}",
            )
        )

    # 6. Managers far behind the call norm for this hour of the day (from 11:00, when the pace is meaningful).
    if data.day_progress >= 0.2:
        expected = NORM_CALLS * data.day_progress
        for u in data.team:
            made = team_calls(data, u.id, data.day)
            usual = (
                sum(team_calls(data, u.id, d) for d in data.workdays_before(data.day, 10)[5:]) / 5 * data.day_progress
            )
            if made < expected * 0.55:
                reason = (
                    f"Две недели назад к этому часу было около {round(usual)} звонков"
                    if usual > made * 1.5
                    else "Проверить загрузку"
                )
                out.append(
                    signal(
                        "below-norm",
                        f"user{u.id}",
                        "medium",
                        f"{u.name}: {made} звонков при норме {round(expected)} к этому часу",
                        reason,
                        u.name,
                        "—",
                        now,
                        "Поговорить с менеджером",
                        now,
                        "/sales/team",
                    )
                )

    out.sort(key=lambda s: (SEVERITY_RANK[s["severity"]], s["ageHours"]))
    return out
