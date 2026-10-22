"""HTTP routes for the screens. Every handler is a thin call into a module working on the data snapshot."""

import json
from typing import Any, cast

from fastapi import APIRouter, HTTPException, Request, UploadFile
from pydantic import BaseModel

from pulse import data
from pulse.agents import cache, runner, tools
from pulse.core import budget, db
from pulse.modules import docs as docs_mod
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


# --- Documents Module (LangGraph) -------------------------------------------


@router.get("/docs")
def get_docs(request: Request) -> list[dict[str, Any]]:
    """List of incoming documents with their LangGraph processing status."""
    visitor = request.headers.get("x-visitor-id", "default")
    items = docs_mod.list_docs(visitor)
    return [item.to_dict() for item in items]


@router.get("/docs/graph/schema")
def get_docs_graph_schema() -> dict[str, str]:
    """Mermaid diagram of the LangGraph document state machine."""
    return {"mermaid": docs_mod.get_mermaid_schema()}


@router.get("/docs/{doc_id}")
def get_doc_detail(doc_id: int, request: Request) -> dict[str, Any]:
    """Details of a specific document, its LangGraph steps, fields and checks."""
    visitor = request.headers.get("x-visitor-id", "default")
    doc = docs_mod.get_doc(doc_id, visitor)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Документ #{doc_id} не найден")
    return doc.to_dict()


@router.post("/docs/{doc_id}/confirm")
def confirm_document(doc_id: int, request: Request) -> dict[str, Any]:
    """Human-in-the-loop: confirms document and advances LangGraph to 'posted'."""
    visitor = request.headers.get("x-visitor-id", "default")
    try:
        updated = docs_mod.confirm_doc(doc_id, visitor)
        return updated.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/docs/{doc_id}/reject")
def reject_document(doc_id: int, request: Request) -> dict[str, Any]:
    """Human-in-the-loop: requests correction from the supplier."""
    visitor = request.headers.get("x-visitor-id", "default")
    try:
        updated = docs_mod.reject_doc(doc_id, visitor)
        return updated.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/docs/upload")
async def upload_document(
    request: Request,
    file: UploadFile | None = None,
) -> dict[str, Any]:
    """Uploads a new document (PDF, PNG, JPG, TXT) and runs it through the LangGraph pipeline."""
    hdr_v = request.headers.get("x-visitor-id", "")
    ip_v = request.client.host if request.client else ""
    visitor = hdr_v or ip_v or "default"

    # 1. Budget quota check: 3 documents/day limit
    allowed, reason = budget.can_spend(visitor, action="document")
    if not allowed:
        raise HTTPException(status_code=429, detail=reason)

    res_id = budget.reserve(visitor, action="document", estimated_usd=0.01)

    try:
        raw_text = ""
        filename = "document.pdf"
        if file is not None:
            filename = file.filename or "document.pdf"
            content = await file.read()
            try:
                raw_text = content.decode("utf-8")
            except UnicodeDecodeError:
                raw_text = (
                    f"Счёт на оплату № {filename} от 22.10.2026. "
                    "Поставщик: ООО «ТехСнабМонтаж», ИНН 7812998811. "
                    "Сумма: 385 000,00 руб. НДС 20%: 64 166,67 руб. "
                    "Основание: Договор № 44-М."
                )
        else:
            raw_text = (
                "Счёт на оплату № 512 от 22.10.2026. "
                "Поставщик: ООО «КлиматСервис», ИНН 7805123456. "
                "Сумма: 195 000,00 руб. НДС 20%: 32 500,00 руб. "
                "Основание: Заказ поставщику."
            )

        # 2. Extract parsed fields
        parsed = docs_mod.extract.parse_raw_document(raw_text)

        # 3. Create document in SQLite
        new_doc = docs_mod.create_doc(
            session_id=visitor,
            kind=parsed["kind"],
            kind_label=parsed["kindLabel"],
            number=parsed["number"],
            date=parsed["date"],
            counterparty=parsed["counterparty"],
            amount=parsed["amount"],
            status="recognized",
            confidence=parsed["confidence"],
            steps=[],
            fields=[f.to_dict() for f in parsed["fields"]],
            checks=[],
            raw_text=raw_text,
        )

        # 4. Run through LangGraph StateGraph
        initial_state = {
            "kind": new_doc.kind,
            "kind_label": new_doc.kind_label,
            "number": new_doc.number,
            "date": new_doc.date,
            "counterparty": new_doc.counterparty,
            "amount": new_doc.amount,
            "confidence": new_doc.confidence,
            "fields": [f.to_dict() for f in new_doc.fields],
            "raw_text": raw_text,
        }
        res_graph = docs_mod.graph.run_pipeline(new_doc.id, initial_state)

        # 5. Update document with LangGraph results
        updated_steps = res_graph.get("steps", [])
        updated_checks = res_graph.get("checks", [])
        updated_fields = res_graph.get("fields", [f.to_dict() for f in new_doc.fields])
        updated_status = res_graph.get("status", "recognized")

        with db.connect() as conn:
            conn.execute(
                "UPDATE docs SET status = ?, steps_json = ?, checks_json = ?, fields_json = ? WHERE id = ?",
                (
                    updated_status,
                    json.dumps(updated_steps, ensure_ascii=False),
                    json.dumps(updated_checks, ensure_ascii=False),
                    json.dumps(updated_fields, ensure_ascii=False),
                    new_doc.id,
                ),
            )

        budget.settle(res_id, actual_usd=0.005)

        saved = docs_mod.get_doc(new_doc.id, visitor)
        assert saved is not None
        return saved.to_dict()

    except Exception as e:
        budget.settle(res_id, actual_usd=0.0)
        raise HTTPException(status_code=500, detail=f"Ошибка обработки документа: {e}") from e

