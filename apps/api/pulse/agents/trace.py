"""Traces of agent runs: every step is timed when it happens; nothing is drawn after the fact."""

import json
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from pulse.core import clock, db, fmt

ENGINE_LABEL = {
    "rules": "Готовый ответ: правила + инструменты",
    "kb": "База знаний",
    "model": "Модель с инструментами",
    "hermes": "Hermes Agent",
    "none": "Без модели",
}


@dataclass
class Trace:
    question: str
    session: str
    engine: str = "rules"
    model: str = ""
    id: str = field(default_factory=lambda: f"run_{uuid.uuid4().hex[:8]}")
    started: float = field(default_factory=time.perf_counter)
    steps: list[dict[str, Any]] = field(default_factory=list)
    cost_usd: float = 0.0
    tokens: int = 0

    def elapsed(self) -> float:
        return (time.perf_counter() - self.started) * 1000

    def add(
        self,
        kind: str,
        name: str,
        label: str,
        lane: str,
        start_ms: float,
        dur_ms: float,
        detail: str = "",
        cost: float = 0.0,
    ) -> None:
        self.steps.append(
            {
                "id": f"s{len(self.steps) + 1}",
                "kind": kind,
                "name": name,
                "label": label,
                "lane": lane,
                "startMs": round(start_ms, 1),
                "durMs": round(max(dur_ms, 0.1), 1),
                "detail": detail,
                "costUsd": round(cost, 6),
            }
        )
        self.cost_usd += cost

    @contextmanager
    def step(self, kind: str, name: str, label: str, lane: str) -> Iterator[dict[str, Any]]:
        """Times a block; the block may fill `info["detail"]` and `info["cost"]`."""
        info: dict[str, Any] = {"detail": "", "cost": 0.0}
        start = self.elapsed()
        try:
            yield info
        finally:
            self.add(kind, name, label, lane, start, self.elapsed() - start, info["detail"], info["cost"])

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "engine": self.engine,
            "engineLabel": ENGINE_LABEL.get(self.engine, self.engine),
            "model": self.model,
            "startedAgo": "только что",
            "totalMs": round(self.elapsed(), 1),
            "costUsd": round(self.cost_usd, 6),
            "tokens": self.tokens,
            "steps": self.steps,
        }


def save(trace: Trace, answer: str, sources: list[dict[str, Any]]) -> None:
    t = trace.to_dict()
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO ai_traces(id, session_id, question, engine, model, total_ms, cost_usd, tokens, steps_json, "
            "answer_text, sources_json, drafts_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)",
            (
                t["id"],
                trace.session,
                trace.question,
                trace.engine,
                trace.model,
                int(t["totalMs"]),
                t["costUsd"],
                trace.tokens,
                json.dumps(t["steps"], ensure_ascii=False),
                answer,
                json.dumps(sources, ensure_ascii=False),
                clock.now().isoformat(),
            ),
        )


def latest(prefer_model: bool = True) -> dict[str, Any] | None:
    """The last run for «Под капотом»: preferably one where a model or Hermes worked, else any."""
    with db.connect() as conn:
        row = None
        if prefer_model:
            row = conn.execute(
                "SELECT * FROM ai_traces WHERE engine IN ('model', 'hermes') ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        row = row or conn.execute("SELECT * FROM ai_traces ORDER BY created_at DESC LIMIT 1").fetchone()
    if not row:
        return None
    from datetime import datetime

    ago = (clock.now() - datetime.fromisoformat(row["created_at"])).total_seconds() / 60
    return {
        "id": row["id"],
        "question": row["question"],
        "engine": row["engine"],
        "engineLabel": ENGINE_LABEL.get(row["engine"], row["engine"]),
        "model": row["model"],
        "startedAgo": fmt.ago(ago),
        "totalMs": row["total_ms"],
        "costUsd": row["cost_usd"],
        "tokens": row["tokens"],
        "steps": json.loads(row["steps_json"]),
    }


def count_today() -> int:
    """Agent runs today (instant answers included) — the «Агенты» card on the overview."""
    with db.connect() as conn:
        row = conn.execute(
            "SELECT count(*) FROM ai_traces WHERE created_at >= ?", (clock.today().isoformat(),)
        ).fetchone()
    return int(row[0])


def clear() -> None:
    """Nightly reset: yesterday's traces describe yesterday's data."""
    with db.connect() as conn:
        conn.execute("DELETE FROM ai_traces")
