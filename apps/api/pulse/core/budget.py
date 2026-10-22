"""Daily budget and per-visitor limits on AI calls (USD).

Protects against run-away agent tool loops and visitor scraping.
Uses a two-phase reserve/settle pattern adapted for OpenRouter USD costs.
"""


import json
import uuid
from typing import Any

from pulse.core import clock, db
from pulse.core.config import get_settings


def today_str() -> str:
    return clock.today().isoformat()


def can_spend(
    visitor_id: str, action: str = "question", estimated_usd: float = 0.005
) -> tuple[bool, str]:
    """Check if the global daily cap or per-visitor limits are exhausted."""
    settings = get_settings()
    cap = settings.ai_daily_usd
    day = today_str()

    with db.connect() as conn:
        row = conn.execute(
            "SELECT coalesce(sum(coalesce(actual_usd, estimated_usd)), 0) FROM ai_usage WHERE day = ?",
            (day,),
        ).fetchone()
        spent = float(row[0]) if row else 0.0

        if spent + estimated_usd > cap:
            return (
                False,
                f"Суточный лимит ИИ (${cap:.2f}) исчерпан. Показываем ответы из кэша.",
            )

        if visitor_id:
            v_row = conn.execute(
                "SELECT count(*) FROM ai_usage WHERE day = ? AND visitor_id = ? AND action = ?",
                (day, visitor_id, action),
            ).fetchone()
            used_count = int(v_row[0]) if v_row else 0

            max_allowed = (
                settings.ai_visitor_questions
                if action == "question"
                else settings.ai_visitor_documents
            )
            if used_count >= max_allowed:
                return (
                    False,
                    f"Ваш лимит на сегодня ({max_allowed} {action}) исчерпан. Используйте готовые вопросы.",
                )

    return True, ""


def reserve(
    visitor_id: str, action: str, estimated_usd: float, details: dict[str, Any] | None = None
) -> str:
    """Reserve USD amount before invoking a model. Raises RuntimeError if cap reached."""
    ok, reason = can_spend(visitor_id, action, estimated_usd)
    if not ok:
        raise RuntimeError(reason)

    settings = get_settings()
    now = clock.now()
    day = today_str()
    hour = now.hour
    reserve_id = f"res_{uuid.uuid4().hex[:12]}"

    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        # Re-check inside transaction
        row = conn.execute(
            "SELECT coalesce(sum(coalesce(actual_usd, estimated_usd)), 0) FROM ai_usage WHERE day = ?",
            (day,),
        ).fetchone()
        spent = float(row[0]) if row else 0.0
        if spent + estimated_usd > settings.ai_daily_usd:
            raise RuntimeError(f"Суточный лимит ИИ (${settings.ai_daily_usd:.2f}) исчерпан.")

        conn.execute(
            "INSERT INTO ai_usage(id, day, hour, visitor_id, action, estimated_usd, "
            "actual_usd, status, details, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                reserve_id,
                day,
                hour,
                visitor_id or "anonymous",
                action,
                estimated_usd,
                None,
                "reserved",
                json.dumps(details or {}, ensure_ascii=False),
                now.isoformat(),
            ),
        )


    return reserve_id


def settle(
    reserve_id: str,
    actual_usd: float | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Settle the reservation with actual cost after LLM completion."""
    with db.connect() as conn:
        conn.execute(
            "UPDATE ai_usage SET actual_usd = ?, status = ?, details = ? WHERE id = ?",
            (
                actual_usd,
                "settled" if actual_usd is not None else "failed",
                json.dumps(details or {}, ensure_ascii=False),
                reserve_id,
            ),
        )



def summary(visitor_id: str = "") -> dict[str, Any]:
    """Summary of daily AI spend and visitor's quota."""
    settings = get_settings()
    day = today_str()

    with db.connect() as conn:
        row = conn.execute(
            "SELECT coalesce(sum(coalesce(actual_usd, estimated_usd)), 0) FROM ai_usage WHERE day = ?",
            (day,),
        ).fetchone()
        spent = float(row[0]) if row else 0.0

        by_hour = [0] * 24
        hour_rows = conn.execute(
            "SELECT hour, count(*) FROM ai_usage WHERE day = ? GROUP BY hour",
            (day,),
        ).fetchall()
        for h, cnt in hour_rows:
            if 0 <= h < 24:
                by_hour[h] = cnt

        questions_used = 0
        docs_used = 0
        if visitor_id:
            v_rows = conn.execute(
                "SELECT action, count(*) FROM ai_usage WHERE day = ? AND visitor_id = ? GROUP BY action",
                (day, visitor_id),
            ).fetchall()
            for act, cnt in v_rows:
                if act == "question":
                    questions_used = cnt
                elif act == "document":
                    docs_used = cnt

    return {
        "spentUsd": round(spent, 4),
        "capUsd": settings.ai_daily_usd,
        "questionsLeft": max(0, settings.ai_visitor_questions - questions_used),
        "questionsCap": settings.ai_visitor_questions,
        "documentsLeft": max(0, settings.ai_visitor_documents - docs_used),
        "documentsCap": settings.ai_visitor_documents,
        "byHour": by_hour,
    }
