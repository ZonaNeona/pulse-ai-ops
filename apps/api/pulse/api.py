"""HTTP routes for the screens. Every handler is a thin call into a module working on the data snapshot."""

from typing import Any, cast

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from pulse import data
from pulse.agents import cache, runner, tools
from pulse.core import budget
from pulse.modules import integrations, overview
from pulse.modules.sales import calls, deals, pulse, signals, team

router = APIRouter(prefix="/api")


class ChatRequest(BaseModel):
    message: str
    session_id: str = ""
    visitor_id: str = ""


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
def get_budget(request: Request) -> dict[str, Any]:
    """AI spend today and the per-visitor limits calculated from SQLite."""
    visitor_id = request.headers.get("x-visitor-id", "") or (request.client.host if request.client else "")
    return budget.summary(visitor_id)


@router.post("/copilot/chat")
async def copilot_chat(body: ChatRequest, request: Request) -> dict[str, Any]:
    """Answers a question via instant cache, Hermes Agent (if running), or the fallback runner."""
    hdr_v = request.headers.get("x-visitor-id", "")
    ip_v = request.client.host if request.client else ""
    visitor = body.visitor_id or hdr_v or ip_v
    return await runner.answer(body.message, body.session_id, visitor)



@router.get("/trace/latest")
def get_latest_trace() -> dict[str, Any]:
    """Latest agent trace for the 'Under the Hood' screen."""
    tr = runner.get_latest_trace()
    if tr is not None:
        return tr
    d = data.load()
    sample = cache.find_answer("Сравни продажи октября с оплатами в 1С", d)
    return cache.build_trace("Сравни продажи октября с оплатами в 1С", sample or {})


@router.post("/drafts/{draft_id}/confirm")
def confirm_draft(draft_id: str) -> dict[str, Any]:
    """Confirm a draft action (Human-in-the-loop)."""
    return cast(dict[str, Any], tools.run_tool("confirm_draft", {"draft_id": draft_id}))


@router.post("/drafts/{draft_id}/undo")
def undo_draft(draft_id: str) -> dict[str, Any]:
    """Undo or cancel a draft action."""
    return cast(dict[str, Any], tools.run_tool("undo_draft", {"draft_id": draft_id}))




@router.get("/integrations")
def get_integrations() -> list[dict[str, Any]]:
    return integrations.cards(data.load())


@router.get("/integrations/log")
def get_log() -> list[dict[str, Any]]:
    return integrations.log()


@router.get("/integrations/reconciliation")
def get_reconciliation() -> dict[str, Any]:
    return integrations.reconciliation(data.load())
