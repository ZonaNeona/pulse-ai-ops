"""Daily AI budget (USD) and per-visitor limits.

Two-phase: `reserve` books the estimated cost before a model call and fails if the day's cap or the
visitor's quota is used up; `settle` replaces the estimate with the real cost the provider reported.
A failed call settles at zero, a call without a reported cost keeps its estimate — the cap is never
undercounted.
"""

import json
import uuid
from typing import Any

from pulse.core import clock, db
from pulse.core.config import get_settings

QUOTA_ACTIONS = ("question", "document")


def _day() -> str:
    return clock.today().isoformat()


def _spent(conn: Any, day: str) -> float:
    row = conn.execute(
        "SELECT coalesce(sum(coalesce(actual_usd, estimated_usd)), 0) FROM ai_usage WHERE day = ? AND status != "
        "'failed'",
        (day,),
    ).fetchone()
    return float(row[0])


def _used(conn: Any, day: str, visitor: str, action: str) -> int:
    row = conn.execute(
        "SELECT count(*) FROM ai_usage WHERE day = ? AND visitor_id = ? AND action = ? AND status != 'failed'",
        (day, visitor, action),
    ).fetchone()
    return int(row[0])


def _quota(action: str) -> int:
    s = get_settings()
    return s.ai_visitor_documents if action == "document" else s.ai_visitor_questions


def reserve(visitor: str, action: str, estimated_usd: float) -> str:
    """Book a model call. Raises RuntimeError with a visitor-facing reason when it is not allowed."""
    s = get_settings()
    day, now = _day(), clock.now()
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")  # cap check and insert are one step for concurrent requests
        if _spent(conn, day) + estimated_usd > s.ai_daily_usd:
            raise RuntimeError(
                f"Дневной бюджет ИИ стенда (${s.ai_daily_usd:.2f}) исчерпан — до завтра работают готовые ответы"
            )
        if action in QUOTA_ACTIONS and _used(conn, day, visitor, action) >= _quota(action):
            what = "вопросов" if action == "question" else "документов"
            raise RuntimeError(f"Лимит {_quota(action)} {what} в день на посетителя исчерпан — готовые ответы доступны")
        rid = f"res_{uuid.uuid4().hex[:12]}"
        conn.execute(
            "INSERT INTO ai_usage(id, day, hour, visitor_id, action, estimated_usd, actual_usd, status, details, "
            "created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, NULL, 'reserved', '{}', ?)",
            (rid, day, now.hour, visitor, action, estimated_usd, now.isoformat()),
        )
    return rid


def settle(reserve_id: str, actual_usd: float, details: dict[str, Any] | None = None) -> None:
    """Record the real cost. `actual_usd == 0` with an error in details marks the call failed (not counted)."""
    failed = bool(details and details.get("error"))
    with db.connect() as conn:
        conn.execute(
            "UPDATE ai_usage SET actual_usd = CASE WHEN ? > 0 THEN ? ELSE actual_usd END, status = ?, details = ? "
            "WHERE id = ?",
            (
                actual_usd,
                actual_usd,
                "failed" if failed else "settled",
                json.dumps(details or {}, ensure_ascii=False),
                reserve_id,
            ),
        )


def add_cost(visitor: str, action: str, usd: float) -> None:
    """Extra model turns inside one already-booked request (tool loops): cost only, no quota use."""
    now = clock.now()
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO ai_usage(id, day, hour, visitor_id, action, estimated_usd, actual_usd, status, details, "
            "created_at) "
            "VALUES (?, ?, ?, ?, ?, 0, ?, 'settled', '{}', ?)",
            (f"add_{uuid.uuid4().hex[:12]}", _day(), now.hour, visitor, f"{action}:turn", usd, now.isoformat()),
        )


def summary(visitor: str = "") -> dict[str, Any]:
    s = get_settings()
    day = _day()
    with db.connect() as conn:
        spent = _spent(conn, day)
        hours = conn.execute(
            "SELECT hour, count(*) FROM ai_usage WHERE day = ? AND action IN ('question', 'document') AND status != "
            "'failed' "
            "GROUP BY hour",
            (day,),
        ).fetchall()
        q = _used(conn, day, visitor, "question") if visitor else 0
        d = _used(conn, day, visitor, "document") if visitor else 0
    by_hour = [0] * 24
    for h, n in hours:
        by_hour[int(h)] = int(n)
    return {
        "spentUsd": round(spent, 4),
        "capUsd": s.ai_daily_usd,
        "questionsLeft": max(0, s.ai_visitor_questions - q),
        "questionsCap": s.ai_visitor_questions,
        "documentsLeft": max(0, s.ai_visitor_documents - d),
        "documentsCap": s.ai_visitor_documents,
        "byHour": by_hour,
        "modelConnected": bool(s.llm_api_key),
    }
