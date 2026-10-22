"""Unified tool registry for Pulse AI agents.

Both Hermes Agent (via MCP) and the built-in fallback runner execute tools through this registry.
Read tools access the local snapshot (data.load()); write actions produce drafts requiring
human confirmation (human-in-the-loop pattern).
"""

import json
import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from pulse import data
from pulse.core import clock, db
from pulse.modules import docs as docs_mod
from pulse.modules import integrations, overview
from pulse.modules.sales import calls, deals, pulse, signals, team

# --- Tool Implementations ----------------------------------------------------


def tool_sales_pulse() -> dict[str, Any]:
    """Returns today's sales KPIs, trends, and summary metrics."""
    d = data.load()
    return {
        "kpis": pulse.kpis(d),
        "revenue": overview.overview(d)["revenue"],
        "signals_count": len(signals.build(d)),
    }


def tool_get_signals(limit: int = 10, severity: str = "") -> list[dict[str, Any]]:
    """Returns active operational sales signals (missed calls without callback, stale deals, overdue tasks)."""
    d = data.load()
    sigs = signals.build(d)
    if severity:
        sigs = [s for s in sigs if s.get("severity") == severity]
    return sigs[:limit]


def tool_team_status() -> list[dict[str, Any]]:
    """Returns sales team performance: calls vs norms, talk time, quality scores, slumping managers."""
    d = data.load()
    return team.team(d)


def tool_get_deals(
    stage: str = "", manager: str = "", stale_only: bool = False, limit: int = 20
) -> list[dict[str, Any]]:
    """Returns CRM deals, optionally filtered by stage, manager, or stagnation status."""
    d = data.load()
    board = deals.board(d)
    if stage:
        board = [item for item in board if item.get("stage") == stage]
    if manager:
        board = [item for item in board if item.get("manager") == manager]
    if stale_only:
        board = [item for item in board if item.get("isStale")]
    return board[:limit]


def tool_deal_details(deal_id: int) -> dict[str, Any]:
    """Returns complete details of a specific deal by its ID."""
    d = data.load()
    for deal in d.deals:
        if deal.id == deal_id:
            company_title = ""
            if deal.company_id and deal.company_id in d.companies:
                company_title = d.companies[deal.company_id].title
            return {
                "id": deal.id,
                "title": deal.title,
                "amount": deal.amount,
                "stage": deal.stage_id,
                "company": company_title,
                "created": deal.created.isoformat(),
                "modified": deal.modified.isoformat(),
            }
    return {"error": f"Сделка #{deal_id} не найдена"}



def tool_call_review(call_id: int) -> dict[str, Any]:
    """Returns speech analytics review for a call: criteria scores, quotes from transcript, recommendations."""
    d = data.load()
    res = calls.review(d, call_id)
    if not res:
        return {"error": f"Разбор для звонка #{call_id} не найден"}
    return res


def tool_reconciliation() -> dict[str, Any]:
    """Returns cross-system reconciliation between CRM (Bitrix24) and ERP (1C): total amounts and gap list."""
    d = data.load()
    return integrations.reconciliation(d)


def tool_erp_stock(query: str = "") -> list[dict[str, Any]]:
    """Returns warehouse stock balances from 1C accounting."""
    d = data.load()
    items = []
    for item in d.stock:
        if not query or query.lower() in item.name.lower() or query.lower() in item.sku.lower():
            items.append({
                "sku": item.sku,
                "title": item.name,
                "balance": item.qty,
                "reserved": item.reserved,
                "available": item.free,
                "unit": item.unit,
            })
    return items[:25]



def tool_draft_task(
    title: str, responsible: str, deal_id: int | None = None, deadline_days: int = 1, session_id: str = ""
) -> dict[str, Any]:
    """Creates a draft CRM task. Does NOT apply until explicitly confirmed by the user."""
    draft_id = f"draft_{uuid.uuid4().hex[:8]}"
    now = clock.now()
    deadline = now + timedelta(days=deadline_days)
    payload = {
        "title": title,
        "responsible": responsible,
        "deal_id": deal_id,
        "deadline": deadline.isoformat(),
    }
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO ai_drafts(id, session_id, kind, title, payload, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                draft_id,
                session_id or "default",
                "task",
                f"Создать задачу: {title}",
                json.dumps(payload, ensure_ascii=False),
                "pending",
                now.isoformat(),
                now.isoformat(),
            ),
        )
    return {
        "draft_id": draft_id,
        "status": "pending_confirmation",
        "action": "task_create",
        "title": title,
        "responsible": responsible,
        "deadline": deadline.strftime("%d.%m.%Y"),
        "note": "Черновик сохранён. Требуется подтверждение пользователя.",
    }


def tool_confirm_draft(draft_id: str) -> dict[str, Any]:
    """Applies a previously created draft after user confirmation."""
    now = clock.now()
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM ai_drafts WHERE id = ?", (draft_id,)).fetchone()
        if not row:
            return {"error": f"Черновик {draft_id} не найден"}
        if row["status"] == "confirmed":
            return {"status": "already_confirmed", "draft_id": draft_id}
        conn.execute(
            "UPDATE ai_drafts SET status = 'confirmed', updated_at = ? WHERE id = ?",
            (now.isoformat(), draft_id),
        )
    return {"status": "confirmed", "draft_id": draft_id, "applied_at": now.isoformat()}


def tool_undo_draft(draft_id: str) -> dict[str, Any]:
    """Cancels or rolls back a draft."""
    now = clock.now()
    with db.connect() as conn:
        conn.execute(
            "UPDATE ai_drafts SET status = 'undone', updated_at = ? WHERE id = ?",
            (now.isoformat(), draft_id),
        )
    return {"status": "undone", "draft_id": draft_id}


def get_drafts(session_id: str) -> list[dict[str, Any]]:
    """Returns all drafts for a session ordered by creation time."""
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT id, session_id, kind, title, payload, status, created_at, updated_at "
            "FROM ai_drafts WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def tool_docs_queue() -> list[dict[str, Any]]:
    """Returns incoming documents that require human review or confirmation."""
    items = docs_mod.list_docs()
    waiting = [d for d in items if d.status in ("mismatch", "review")]
    return [d.to_dict() for d in waiting]


def tool_review_doc(doc_id: int) -> dict[str, Any]:
    """Returns full details of an incoming document, its LangGraph steps, and 1C/CRM checks."""
    doc = docs_mod.get_doc(doc_id)
    if not doc:
        return {"error": f"Документ #{doc_id} не найден"}
    return doc.to_dict()


def tool_confirm_doc(doc_id: int) -> dict[str, Any]:
    """Human-in-the-loop confirmation of a document: posts it to 1C."""
    doc = docs_mod.confirm_doc(doc_id)
    return {"status": doc.status, "message": f"Документ {doc.number} успешно проведён в 1С"}


def tool_knowledge_search(query: str, limit: int = 3) -> dict[str, Any]:
    """Search company regulations knowledge base (pricing, discounts, warranty, installation standards, claims)."""
    from pulse.modules import knowledge as kb_mod

    ans = kb_mod.answer_question(query)
    chunks = kb_mod.search_chunks(query, limit=limit)
    return {
        "grounded": ans.grounded,
        "answer": ans.answer,
        "sources": [s.to_dict() for s in ans.sources],
        "chunks": chunks,
    }


# --- Tool Definitions & Schemas ----------------------------------------------

REGISTRY: dict[str, tuple[dict[str, Any], Callable[..., Any]]] = {
    "sales_pulse": (
        {
            "name": "sales_pulse",
            "description": "Сводный пульс продаж за сегодня: ключевые KPI, выручка к плану, аномалии.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
        tool_sales_pulse,
    ),
    "get_signals": (
        {
            "name": "get_signals",
            "description": "Активные сигналы РОПа: пропущенные звонки, зависшие сделки, просрочки.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Максимальное число сигналов", "default": 10},
                    "severity": {
                        "type": "string",
                        "enum": ["high", "medium", "low", ""],
                        "description": "Фильтр по срочности",
                    },
                },
            },
        },
        tool_get_signals,
    ),
    "team_status": (
        {
            "name": "team_status",
            "description": "Статус менеджеров: звонки, нормы, время разговора, оценка качества и отставания.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
        tool_team_status,
    ),

    "get_deals": (
        {
            "name": "get_deals",
            "description": "Получить список сделок CRM с фильтрацией по стадии, менеджеру или признаку застревания.",
            "parameters": {
                "type": "object",
                "properties": {
                    "stage": {"type": "string", "description": "Стадия сделки"},
                    "manager": {"type": "string", "description": "Имя менеджера"},
                    "stale_only": {"type": "boolean", "description": "Только сделки без движения > 7 дней"},
                    "limit": {"type": "integer", "default": 20},
                },
            },
        },
        tool_get_deals,
    ),
    "deal_details": (
        {
            "name": "deal_details",
            "description": "Получить подробную информацию по конкретной сделке CRM по её ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "deal_id": {"type": "integer", "description": "ID сделки"},
                },
                "required": ["deal_id"],
            },
        },
        tool_deal_details,
    ),
    "call_review": (
        {
            "name": "call_review",
            "description": "Аналитический разбор звонка: оценка 0-100, критерии чек-листа, цитаты и совет.",
            "parameters": {
                "type": "object",
                "properties": {
                    "call_id": {"type": "integer", "description": "ID звонка"},
                },
                "required": ["call_id"],
            },
        },
        tool_call_review,
    ),

    "reconciliation": (
        {
            "name": "reconciliation",
            "description": "Сверить продажи CRM (Битрикс24) с реализациями в 1С: суммы и список расхождений.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
        tool_reconciliation,
    ),
    "erp_stock": (
        {
            "name": "erp_stock",
            "description": "Проверить остатки и резервы оборудования на складе в 1С.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Поисковый запрос (артикул или название)"},
                },
            },
        },
        tool_erp_stock,
    ),
    "draft_task": (
        {
            "name": "draft_task",
            "description": "Создать черновик задачи в CRM. Применяется ТОЛЬКО после подтверждения пользователем.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Заголовок задачи"},
                    "responsible": {"type": "string", "description": "Ответственный сотрудник"},
                    "deal_id": {"type": "integer", "description": "ID связанной сделки (опционально)"},
                    "deadline_days": {"type": "integer", "description": "Срок в днях от сегодня", "default": 1},
                },
                "required": ["title", "responsible"],
            },
        },
        tool_draft_task,
    ),

    "confirm_draft": (
        {
            "name": "confirm_draft",
            "description": "Подтвердить применение ранее созданного черновика (Human-in-the-loop).",
            "parameters": {
                "type": "object",
                "properties": {
                    "draft_id": {"type": "string", "description": "ID черновика"},
                },
                "required": ["draft_id"],
            },
        },
        tool_confirm_draft,
    ),
    "undo_draft": (
        {
            "name": "undo_draft",
            "description": "Отменить черновик задачи или изменения.",
            "parameters": {
                "type": "object",
                "properties": {
                    "draft_id": {"type": "string", "description": "ID черновика"},
                },
                "required": ["draft_id"],
            },
        },
        tool_undo_draft,
    ),
    "docs_queue": (
        {
            "name": "docs_queue",
            "description": "Очередь входящих документов (счета, акты, УПД), ожидающих подтверждения человека.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
        tool_docs_queue,
    ),
    "review_doc": (
        {
            "name": "review_doc",
            "description": "Проверить статус документа, шаги графа LangGraph и расхождения со сверкой 1С/CRM.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "integer", "description": "ID документа"},
                },
                "required": ["doc_id"],
            },
        },
        tool_review_doc,
    ),
    "confirm_doc": (
        {
            "name": "confirm_doc",
            "description": "Подтвердить проводку документа в 1С (Human-in-the-loop).",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "integer", "description": "ID документа"},
                },
                "required": ["doc_id"],
            },
        },
        tool_confirm_doc,
    ),
    "knowledge_search": (
        {
            "name": "knowledge_search",
            "description": (
                "Поиск по базе регламентов компании 'Норд Инжиниринг' "
                "(цены, скидки, гарантии, стандарты монтажа, рекламации)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Поисковый запрос или вопрос по регламентам"},
                    "limit": {"type": "integer", "description": "Количество фрагментов", "default": 3},
                },
                "required": ["query"],
            },
        },
        tool_knowledge_search,
    ),
}


def get_specs() -> list[dict[str, Any]]:
    """Returns OpenAI/JSON schema specs for all registered tools."""
    return [
        {"type": "function", "function": spec}
        for spec, _ in REGISTRY.values()
    ]


def run_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Executes a tool by name with arguments."""
    entry = REGISTRY.get(name)
    if not entry:
        raise ValueError(f"Инструмент '{name}' не зарегистрирован")
    _, func = entry
    return func(**arguments)
