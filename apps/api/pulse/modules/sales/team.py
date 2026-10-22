"""Team view: each manager's day against the norm for this hour, quality, overdue work and pipeline."""

from datetime import datetime, timedelta
from statistics import mean
from typing import Any

from pulse.core import fmt
from pulse.data import Data
from pulse.modules.sales import calls as calls_mod

NORM_CALLS = 45
NORM_TALK_MIN = 120
ROLE_LABEL = {"hunter": "Новые клиенты", "farmer": "Действующие клиенты", "newbie": "Стажёр"}


def role(data: Data, uid: int, position: str) -> str:
    first = next((c.started for c in data.calls if c.user_id == uid), None)
    if first and (data.now - first).days < 30:
        return "newbie"
    return "farmer" if "клиент" in position.lower() else "hunter"


def manager(data: Data, uid: int) -> dict[str, Any]:
    user = data.users[uid]
    now, day, progress = data.now, data.day, max(0.05, data.day_progress)
    today = [c for c in calls_mod.on_day(data, day) if c.user_id == uid and not c.missed]
    norm = round(NORM_CALLS * progress)
    week = now - timedelta(days=7)
    scores = [
        a.score for c in data.calls if c.user_id == uid and c.started >= week and (a := data.assessments.get(c.id))
    ]
    quality = round(mean(scores)) if scores else 0
    overdue = sum(1 for t in data.tasks if t.responsible_id == uid and not t.done and t.deadline and t.deadline < now)
    open_deals = [d for d in data.deals if d.assigned_id == uid and d.semantics == "process"]
    trend = [
        sum(1 for c in calls_mod.on_day(data, d) if c.user_id == uid and not c.missed)
        for d in [*reversed(data.workdays_before(day, 9)), day]
    ]
    pace = len(today) / norm if norm else 1.0
    kind = role(data, uid, user.position)
    forgotten = len({d.company_id for d in open_deals if d.last_activity and (now - d.last_activity).days > 14})

    if pace < 0.6 or (quality and quality < 55):
        status = "danger"
    elif pace < 0.85 or overdue >= 4 or (quality and quality < 70):
        status = "warning"
    else:
        status = "success"

    team_quality = [x for x in (_quality(data, u.id, week) for u in data.team) if x]
    if pace < 0.6:
        note = f"Звонков {round(pace * 100)}% от нормы к этому часу"
    elif quality and quality < 55:
        note = f"Оценка звонков {quality} из 100 — ниже порога"
    elif kind == "newbie":
        first = next(c.started for c in data.calls if c.user_id == uid)
        note = f"Новичок, {(now - first).days // 7 + 1}-я неделя"
    elif forgotten:
        note = f"{fmt.count(forgotten, ('клиент', 'клиента', 'клиентов'))} без касания больше 14 дней"
    elif team_quality and quality == max(team_quality):
        note = "Лучшая оценка звонков в команде"
    elif overdue >= 4:
        note = f"{fmt.count(overdue, ('просроченная задача', 'просроченные задачи', 'просроченных задач'))}"
    else:
        note = "Идёт по плану дня"

    return {
        "id": uid,
        "name": user.name,
        "role": kind,
        "roleLabel": ROLE_LABEL[kind],
        "callsToday": len(today),
        "callsNorm": norm,
        "talkMin": round(sum(c.duration_s for c in today) / 60),
        "talkNorm": round(NORM_TALK_MIN * progress),
        "quality": quality,
        "overdue": overdue,
        "deals": len(open_deals),
        "pipeline": round(sum(d.amount for d in open_deals)),
        "trend": trend,
        "status": status,
        "note": note,
    }


def _quality(data: Data, uid: int, since: datetime) -> int:
    scores = [
        a.score for c in data.calls if c.user_id == uid and c.started >= since and (a := data.assessments.get(c.id))
    ]
    return round(mean(scores)) if scores else 0


def team(data: Data) -> list[dict[str, Any]]:
    return sorted((manager(data, u.id) for u in data.team), key=lambda m: -m["callsToday"])
