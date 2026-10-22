"""Pre-computed call assessments for the demo: what the quality model would have said about each recorded call.

Scores follow each manager's level (Марина is the best on the phone, Дмитрий slid this week), the scenario
follows the funnel and direction of the call. Three calls are fixed for the story.
"""

import random
from datetime import datetime, timedelta
from typing import Any

from pulse.seed import names

LEVEL = {2: 88, 11: 86, 12: 91, 13: 62, 14: 79, 15: 64, 16: 84, 21: 82}
DAYS = 14


def _scenario(inbound: bool, funnel: int | None) -> str:
    if funnel == 2:
        return "D" if inbound else "B"
    if funnel == 1:
        return "C"
    return "A" if inbound else "B"


def generate(b24: dict[str, Any], story: dict[str, Any], now: datetime) -> list[dict[str, Any]]:
    funnel_of_company: dict[str, int] = {}
    for d in b24["deals"]:
        if d["CLOSED"] == "N":
            funnel_of_company.setdefault(d["COMPANY_ID"], int(d["CATEGORY_ID"]))
    since = now - timedelta(days=DAYS)
    week = now - timedelta(days=7)
    out: dict[int, dict[str, Any]] = {}
    for c in b24["calls"]:
        started = datetime.fromisoformat(c["CALL_START_DATE"])
        if (
            not c.get("RECORD_FILE_ID")
            or int(c["CALL_DURATION"]) < 60
            or not since <= started <= now + timedelta(days=1)
        ):
            continue
        uid = int(c["PORTAL_USER_ID"])
        base = LEVEL.get(uid, 75)
        if uid == names.SLUMPING and started >= week:
            base = 47
        rng = random.Random(int(c["ID"]))
        score = max(25, min(98, round(rng.gauss(base, 7))))
        scenario = _scenario(c["CALL_TYPE"] == "2", funnel_of_company.get(c["CRM_ENTITY_ID"]))
        out[int(c["ID"])] = {
            "call_id": int(c["ID"]),
            "scenario": scenario,
            "level": "strong" if score >= 72 else "weak",
            "score": score,
        }
    planted = story.get("calls", {})
    for key, scenario, level, score in (
        ("low_score", "B", "weak", 41),
        ("review", "C", "weak", 64),
        ("best", "B", "strong", 93),
    ):
        if key in planted:
            out[planted[key]] = {"call_id": planted[key], "scenario": scenario, "level": level, "score": score}
    return list(out.values())
