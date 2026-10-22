"""Demo dataset: one generation writes the Bitrix24 and 1С emulator data plus the planted story."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from pulse.core import clock
from pulse.core.config import get_settings
from pulse.seed import b24, erp, quality


def seed_dir() -> Path:
    return get_settings().pulse_data_dir / "seed"


def build(now: datetime | None = None, out: Path | None = None) -> dict[str, Any]:
    now = now or clock.now()
    out = out or seed_dir()
    out.mkdir(parents=True, exist_ok=True)
    b24_data, story = b24.generate(now)
    erp_data = erp.generate(b24_data, story, now.date())
    assessments = quality.generate(b24_data, story, now)
    story["plan_month"] = month_plan(b24_data, now)
    story["generated_at"] = now.isoformat()
    files = (("b24.json", b24_data), ("erp.json", erp_data), ("quality.json", assessments), ("story.json", story))
    for name, payload in files:
        tmp = out / f"{name}.tmp"
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(out / name)  # readers never see a half-written file
    return story


def month_plan(b24_data: dict[str, Any], now: datetime) -> int:
    """A sales plan the team is slightly behind on: the current pace minus a few percent, rounded."""
    start = now.date().replace(day=1)
    fact = sum(
        float(d["OPPORTUNITY"])
        for d in b24_data["deals"]
        if d["STAGE_SEMANTIC_ID"] == "S" and datetime.fromisoformat(d["MOVED_TIME"]).date() >= start
    )
    days = [start + timedelta(days=i) for i in range(31) if (start + timedelta(days=i)).month == start.month]
    workdays = [d for d in days if d.weekday() < 5]
    elapsed = sum(1 for d in workdays if d <= now.date()) / len(workdays)
    return int(round(fact / max(0.25, elapsed) * 1.08 / 100_000) * 100_000)


def assessments() -> list[dict[str, Any]]:
    path = seed_dir() / "quality.json"
    data: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    return data


def story() -> dict[str, Any]:
    path = seed_dir() / "story.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def is_fresh() -> bool:
    """The dataset belongs to today. Otherwise "today" on the screens would be some other day."""
    generated = story().get("generated_at")
    return isinstance(generated, str) and datetime.fromisoformat(generated).date() == clock.today()
