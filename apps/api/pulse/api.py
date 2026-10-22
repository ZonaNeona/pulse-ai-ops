"""HTTP routes for the screens. Every handler is a thin call into a module.

Who is asking is decided by the server (`core.visitor`): the session cookie separates visitors' documents,
drafts and chat, the IP hash carries the AI limits. Nothing is taken from client-sent ids.
"""

import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from pulse import bot, data
from pulse.agents import hermes, runner, tools
from pulse.agents import trace as traces
from pulse.core import budget, llm, visitor
from pulse.core.config import get_settings
from pulse.core.visitor import Visitor
from pulse.modules import docs, integrations, knowledge, overview
from pulse.modules.docs import read
from pulse.modules.sales import calls, deals, pulse, signals, team

router = APIRouter(prefix="/api")
Who = Annotated[Visitor, Depends(visitor.identify)]


class Question(BaseModel):
    message: str = Field(min_length=1, max_length=800)


class KbQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=500)


# --- Overview and sales -------------------------------------------------------


@router.get("/overview")
async def get_overview(who: Who) -> dict[str, Any]:
    await docs.queue(who.session)
    cards = overview.ai_cards(
        docs.pending(who.session), knowledge.evaluation.stats(), budget.summary(who.quota), traces.count_today()
    )
    return overview.overview(data.load(), cards)


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


# --- Integrations -------------------------------------------------------------


@router.get("/integrations")
def get_integrations() -> list[dict[str, Any]]:
    return integrations.cards(data.load())


@router.get("/integrations/log")
def get_log() -> list[dict[str, Any]]:
    return integrations.log()


@router.get("/integrations/reconciliation")
def get_reconciliation() -> dict[str, Any]:
    return integrations.reconciliation(data.load())


# --- Documents (LangGraph) ----------------------------------------------------


@router.get("/docs")
async def get_docs(who: Who) -> list[dict[str, Any]]:
    return await docs.queue(who.session)


@router.get("/docs/graph")
def get_docs_graph() -> dict[str, str]:
    """The graph as LangGraph itself draws it (mermaid), not a hand-made picture."""
    return {"mermaid": docs.graph.mermaid()}


@router.get("/docs/{doc_id}")
async def get_doc(doc_id: int, who: Who) -> dict[str, Any]:
    doc = await docs.get(who.session, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return doc.to_dict()


async def _decide(doc_id: int, who: Visitor, approve: bool) -> dict[str, Any]:
    try:
        return (await docs.decide(who.session, doc_id, approve)).to_dict()
    except docs.NotAllowed as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@router.post("/docs/{doc_id}/approve")
async def approve_doc(doc_id: int, who: Who) -> dict[str, Any]:
    return await _decide(doc_id, who, True)


@router.post("/docs/{doc_id}/reject")
async def reject_doc(doc_id: int, who: Who) -> dict[str, Any]:
    return await _decide(doc_id, who, False)


@router.post("/docs/upload")
async def upload_doc(file: UploadFile, who: Who) -> dict[str, Any]:
    content = await file.read(read.MAX_BYTES + 1)
    try:
        doc = await docs.upload(who.session, who.quota, file.filename or "document", content)
    except read.Unreadable as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return doc.to_dict()


# --- Knowledge ----------------------------------------------------------------


@router.get("/kb/stats")
def get_kb_stats() -> dict[str, Any]:
    return knowledge.evaluation.stats()


@router.get("/kb/documents")
def get_kb_documents() -> list[dict[str, Any]]:
    return knowledge.documents()


@router.get("/kb/eval")
def get_kb_eval() -> dict[str, Any]:
    """The golden set run without a model: retrieval must find the right section or refuse."""
    return knowledge.evaluation.latest()


@router.post("/kb/ask")
async def ask_kb(body: KbQuestion, who: Who) -> dict[str, Any]:
    return (await knowledge.answer(body.question, who.quota)).to_dict()


# --- Copilot, drafts, traces, budget ------------------------------------------


@router.post("/copilot/chat")
async def copilot_chat(body: Question, who: Who) -> dict[str, Any]:
    return await runner.ask(body.message, who)


@router.get("/copilot/drafts")
def get_drafts(who: Who) -> list[dict[str, Any]]:
    return [runner.draft_view(d) for d in tools.drafts(who.session)]


def _set_draft(draft_id: str, who: Visitor, status: str) -> dict[str, Any]:
    result = tools.set_draft(draft_id, who.session, status)
    if result is None:
        raise HTTPException(status_code=409, detail="Черновик не найден или уже решён")
    return result


@router.post("/drafts/{draft_id}/confirm")
def confirm_draft(draft_id: str, who: Who) -> dict[str, Any]:
    """A person confirms the agent's draft. In the demo it is kept for this visitor only, nothing leaves the stand."""
    return _set_draft(draft_id, who, "confirmed")


@router.post("/drafts/{draft_id}/discard")
def discard_draft(draft_id: str, who: Who) -> dict[str, Any]:
    return _set_draft(draft_id, who, "discarded")


@router.get("/agents")
def get_agents() -> dict[str, Any]:
    """What the agent layer consists of right now — the «Под капотом» screen shows it as is."""
    s = get_settings()
    return {
        "tools": [{"name": t.name, "description": t.description, "writes": t.writes} for t in tools.TOOLS.values()],
        "model": s.llm_model if llm.available() else "",
        "visionModel": s.llm_vision_model if llm.available() else "",
        "hermes": hermes.configured(),
    }


@router.get("/trace/latest")
def get_latest_trace() -> dict[str, Any] | None:
    return runner.latest()


@router.get("/budget")
def get_budget(who: Who) -> dict[str, Any]:
    return budget.summary(who.quota)


# --- Telegram -------------------------------------------------------------------


@router.get("/bot/status")
def get_bot_status() -> dict[str, Any]:
    return bot.status()


@router.post("/bot/webhook")
async def bot_webhook(
    request: Request, secret: Annotated[str, Header(alias="X-Telegram-Bot-Api-Secret-Token")] = ""
) -> dict[str, bool]:
    if not bot.check_secret(secret):
        raise HTTPException(status_code=403, detail="forbidden")
    await bot.feed(await request.json())
    return {"ok": True}


# --- How we work ----------------------------------------------------------------


@router.get("/work/quality")
def get_quality() -> dict[str, Any] | None:
    """Measured by `tools/quality_report.py` when the release was built; None on a dev checkout."""
    path = Path(__file__).parent / "quality.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
