"""Funnels and the deal board: open deals plus the last two weeks of wins, with idle days and the next step."""

from datetime import timedelta
from typing import Any

from pulse.data import Data

TONES = ["neutral", "info", "accent", "warning", "success"]


def funnels(data: Data) -> list[dict[str, Any]]:
    out = []
    for f in data.funnels:
        stages = [s for s in f.stages if s.semantics != "failure"]
        out.append(
            {
                "id": str(f.id),
                "name": f.name,
                "stages": [
                    {"id": s.id, "name": s.name, "tone": "success" if s.semantics == "success" else TONES[min(i, 3)]}
                    for i, s in enumerate(stages)
                ],
            }
        )
    return out


def board(data: Data) -> list[dict[str, Any]]:
    now = data.now
    next_task: dict[int, tuple[Any, str]] = {}
    for t in data.tasks:
        if t.done:
            continue
        for b in t.crm:
            if b.startswith("D_"):
                deal_id = int(b[2:])
                key = t.deadline or now
                if deal_id not in next_task or key < next_task[deal_id][0]:
                    next_task[deal_id] = (key, t.title.split(":")[0])
    recent_win = now - timedelta(days=14)
    out = []
    for d in data.deals:
        if d.semantics == "failure" or (d.semantics == "success" and (d.moved or d.modified) < recent_win):
            continue
        out.append(
            {
                "id": d.id,
                "title": d.title,
                "client": data.client(d.company_id),
                "amount": d.amount,
                "funnel": str(d.funnel_id),
                "stage": d.stage_id,
                "manager": data.name(d.assigned_id),
                "daysIdle": (now - d.last_activity).days if d.last_activity and d.semantics == "process" else 0,
                "nextStep": next_task.get(d.id, (None, None))[1],
            }
        )
    return sorted(out, key=lambda x: -x["amount"])
