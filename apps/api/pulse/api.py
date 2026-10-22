"""HTTP routes for the screens. Every handler is a thin call into a module working on the data snapshot."""

from typing import Any

from fastapi import APIRouter, HTTPException

from pulse import data
from pulse.core.config import get_settings
from pulse.modules import integrations, overview
from pulse.modules.sales import calls, deals, pulse, signals, team

router = APIRouter(prefix="/api")


@router.get("/overview")
def get_overview() -> dict[str, Any]:
    return overview.overview(data.load())


@router.get("/sales/pulse")
def get_pulse() -> dict[str, Any]:
    d = data.load()
    return {"kpis": pulse.kpis(d), "series": pulse.series(d), "signals": signals.build(d)}


@router.get("/sales/team")
def get_team() -> list[dict[str, Any]]:
    return team.team(data.load())


@router.get("/sales/funnels")
def get_funnels() -> list[dict[str, Any]]:
    return deals.funnels(data.load())


@router.get("/sales/deals")
def get_deals() -> list[dict[str, Any]]:
    return deals.board(data.load())


@router.get("/sales/calls")
def get_calls(manager: int | None = None) -> list[dict[str, Any]]:
    return calls.feed(data.load(), manager)


@router.get("/sales/calls/{call_id}")
def get_call(call_id: int) -> dict[str, Any]:
    review = calls.review(data.load(), call_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Для этого звонка нет записи с разбором")
    return review


@router.get("/budget")
def get_budget() -> dict[str, Any]:
    """AI spend today and the per-visitor limits. Nothing is spent until the AI layer is switched on."""
    s = get_settings()
    return {
        "spentUsd": 0.0,
        "capUsd": s.ai_daily_usd,
        "questionsLeft": s.ai_visitor_questions,
        "questionsCap": s.ai_visitor_questions,
        "documentsLeft": s.ai_visitor_documents,
        "documentsCap": s.ai_visitor_documents,
        "byHour": [0] * 24,
    }


@router.get("/integrations")
def get_integrations() -> list[dict[str, Any]]:
    return integrations.cards(data.load())


@router.get("/integrations/log")
def get_log() -> list[dict[str, Any]]:
    return integrations.log()


@router.get("/integrations/reconciliation")
def get_reconciliation() -> dict[str, Any]:
    return integrations.reconciliation(data.load())
