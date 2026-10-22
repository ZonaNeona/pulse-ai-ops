"""The agent's tools, described once and served to every brain: the built-in model loop, Hermes via MCP,
the quick answers and the Telegram bot all call `run`.

Read tools see the same snapshot as the screens. The only write is `draft_task`: it creates a draft that a
person confirms or discards in the web app — an agent never changes CRM data on its own.
"""

import contextvars
import inspect
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from pulse import data
from pulse.core import clock, db, fmt
from pulse.core.config import get_settings
from pulse.modules import integrations, overview
from pulse.modules.sales import calls, deals, pulse, signals, team

# The visitor session the current run acts for (drafts and documents are per session).
session: contextvars.ContextVar[str] = contextvars.ContextVar("session", default="agent")


def current_session() -> str:
    """In-process runs set the context variable; the MCP process (spawned by Hermes) reads the turn file."""
    value = session.get()
    if value != "agent":
        return value
    try:
        turn = json.loads((get_settings().pulse_data_dir / "agent_turn.json").read_text(encoding="utf-8"))
        return str(turn.get("session") or "agent")
    except (OSError, ValueError):
        return "agent"


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., Any]
    writes: bool = False

    def spec(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": self.parameters},
        }


def _obj(props: dict[str, Any] | None = None, required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": props or {}, "required": required or []}


def sales_pulse() -> dict[str, Any]:
    d = data.load()
    return {"kpis": pulse.kpis(d), "revenue": overview.revenue(d)}


def get_signals(rule: str = "", limit: int = 10) -> list[dict[str, Any]]:
    sigs = signals.build(data.load())
    return [s for s in sigs if not rule or s["rule"] == rule][:limit]


def team_status() -> list[dict[str, Any]]:
    return team.team(data.load())


def get_deals(manager: str = "", stale_only: bool = False, funnel: str = "", limit: int = 15) -> list[dict[str, Any]]:
    d = data.load()
    rows = deals.board(d)
    names = {f["id"]: f["name"] for f in deals.funnels(d)}
    out = []
    for r in rows:
        if manager and manager.lower() not in r["manager"].lower():
            continue
        if stale_only and r["daysIdle"] < pulse.STALE_DAYS:
            continue
        if funnel and funnel.lower() not in names.get(r["funnel"], "").lower():
            continue
        out.append(r | {"funnelName": names.get(r["funnel"], r["funnel"]), "stageName": d.stage_name(r["stage"])})
    out.sort(key=lambda r: (-r["daysIdle"], -r["amount"]) if stale_only else (-r["amount"],))
    return out[:limit]


def call_feed(manager: str = "", limit: int = 20) -> list[dict[str, Any]]:
    d = data.load()
    uid = next((u.id for u in d.team if manager and manager.lower() in u.name.lower()), None)
    return calls.feed(d, uid)[:limit]


def call_review(call_id: int) -> dict[str, Any]:
    review = calls.review(data.load(), call_id)
    return review or {"error": f"У звонка #{call_id} нет записи с разбором"}


def reconciliation() -> dict[str, Any]:
    return integrations.reconciliation(data.load())


def erp_stock(query: str = "") -> list[dict[str, Any]]:
    q = query.lower()
    return [
        {
            "sku": s.sku,
            "name": s.name,
            "qty": s.qty,
            "reserved": s.reserved,
            "free": s.free,
            "unit": s.unit,
            "price": s.price,
            "supplier": s.supplier,
            "leadDays": s.lead_days,
        }
        for s in data.load().stock
        if not q or q in s.name.lower() or q in s.sku.lower()
    ][:20]


async def docs_queue() -> list[dict[str, Any]]:
    from pulse.modules import docs

    await docs.queue(current_session())  # the first look of a session builds its demo queue
    return [
        {
            "id": x.id,
            "kind": x.kind,
            "number": x.value("number"),
            "counterparty": x.value("counterparty"),
            "amount": x.amount,
            "status": x.status,
            "problems": [c.detail for c in x.checks if not c.ok],
        }
        for x in docs.pending(current_session())
    ]


def knowledge_search(query: str) -> list[dict[str, Any]]:
    from pulse.modules.knowledge.answer import relevant

    return [{"document": h.chunk.doc_title, "section": h.chunk.section, "text": h.chunk.text} for h in relevant(query)]


def draft_task(title: str, responsible: str, deadline_days: int = 1, deal_id: int | None = None) -> dict[str, Any]:
    """A task draft for a person to confirm. Nothing reaches the CRM until then."""
    draft_id = f"draft_{uuid.uuid4().hex[:8]}"
    now = clock.now()
    deadline = now + timedelta(days=max(0, min(30, deadline_days)))
    payload = {"title": title, "responsible": responsible, "deadline": deadline.isoformat(), "deal_id": deal_id}
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO ai_drafts(id, session_id, kind, title, payload, status, created_at, updated_at) "
            "VALUES (?, ?, 'task', ?, ?, 'pending', ?, ?)",
            (
                draft_id,
                current_session(),
                title,
                json.dumps(payload, ensure_ascii=False),
                now.isoformat(),
                now.isoformat(),
            ),
        )
    return {
        "draft_id": draft_id,
        "status": "pending",
        "title": title,
        "responsible": responsible,
        "deadline": f"{deadline:%d.%m.%Y}",
        "note": "Черновик: задача появится в CRM только после подтверждения",
    }


TOOLS: dict[str, Tool] = {
    t.name: t
    for t in [
        Tool(
            "sales_pulse",
            "KPI отдела продаж к текущему часу (звонки, пропущенные, медиана перезвона, сделки, оценка) и выручка "
            "месяца к плану.",
            _obj(),
            sales_pulse,
        ),
        Tool(
            "get_signals",
            "Сигналы «сделать сейчас»: пропущенные без перезвона (no-callback), сделки без движения (stale-deal), "
            "просроченные задачи (overdue-task), лиды без действия (lead-no-action), слабые звонки (low-score), "
            "отставание от нормы (below-norm).",
            _obj(
                {
                    "rule": {"type": "string", "description": "код правила или пусто для всех"},
                    "limit": {"type": "integer"},
                }
            ),
            get_signals,
        ),
        Tool(
            "team_status",
            "Менеджеры: звонки к норме этого часа, минуты разговоров, оценка звонков за 7 дней, просрочки, воронка, "
            "тренд.",
            _obj(),
            team_status,
        ),
        Tool(
            "get_deals",
            "Сделки CRM в работе и выигранные за 2 недели. Фильтры: менеджер, воронка (Поставка, Монтаж, Сервис), "
            "только без движения 7+ дней.",
            _obj(
                {
                    "manager": {"type": "string"},
                    "stale_only": {"type": "boolean"},
                    "funnel": {"type": "string"},
                    "limit": {"type": "integer"},
                }
            ),
            get_deals,
        ),
        Tool(
            "call_feed",
            "Звонки за сегодня и прошлый рабочий день: клиент, менеджер, длительность, оценка, итог.",
            _obj({"manager": {"type": "string"}, "limit": {"type": "integer"}}),
            call_feed,
        ),
        Tool(
            "call_review",
            "Разбор записанного звонка: 8 критериев с баллами, цитаты из расшифровки, советы.",
            _obj({"call_id": {"type": "integer"}}, ["call_id"]),
            call_review,
        ),
        Tool(
            "reconciliation",
            "Сверка за месяц: оплаченные сделки CRM против реализаций 1С, список расхождений.",
            _obj(),
            reconciliation,
        ),
        Tool(
            "erp_stock",
            "Остатки 1С: количество, резерв, свободно, цена, поставщик, срок поставки.",
            _obj({"query": {"type": "string"}}),
            erp_stock,
        ),
        Tool(
            "docs_queue",
            "Входящие документы, которые ждут решения человека, и найденные в них проблемы.",
            _obj(),
            docs_queue,
        ),
        Tool(
            "knowledge_search",
            "Поиск по регламентам компании (цены и скидки, договоры, гарантия, рекламации, монтаж, склад, продажи, "
            "документы). Возвращает разделы с текстом.",
            _obj({"query": {"type": "string"}}, ["query"]),
            knowledge_search,
        ),
        Tool(
            "draft_task",
            "Создать ЧЕРНОВИК задачи в CRM. Человек подтвердит или отклонит его сам.",
            _obj(
                {
                    "title": {"type": "string"},
                    "responsible": {"type": "string"},
                    "deadline_days": {"type": "integer"},
                    "deal_id": {"type": "integer"},
                },
                ["title", "responsible"],
            ),
            draft_task,
            writes=True,
        ),
    ]
}


def specs() -> list[dict[str, Any]]:
    return [t.spec() for t in TOOLS.values()]


async def run(name: str, arguments: dict[str, Any]) -> Any:
    tool = TOOLS.get(name)
    if tool is None:
        return {"error": f"Нет инструмента {name}"}
    allowed = set(tool.parameters["properties"])
    try:
        result = tool.func(**{k: v for k, v in arguments.items() if k in allowed})
        return await result if inspect.isawaitable(result) else result
    except (TypeError, ValueError) as exc:
        return {"error": f"Неверные аргументы: {exc}"}


def brief(result: Any) -> str:
    """One line for the trace: what the tool returned, not the whole payload."""
    if isinstance(result, list):
        return fmt.count(len(result), ("запись", "записи", "записей"))
    if isinstance(result, dict):
        if "error" in result:
            return str(result["error"])
        return ", ".join(list(result)[:4])
    return str(result)[:80]


def drafts(session_id: str) -> list[dict[str, Any]]:
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM ai_drafts WHERE session_id = ? ORDER BY created_at", (session_id,)
        ).fetchall()
    return [dict(r) | {"payload": json.loads(r["payload"])} for r in rows]


def set_draft(draft_id: str, session_id: str, status: str) -> dict[str, Any] | None:
    """Confirm or discard — done by a person through the API, never by an agent tool."""
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM ai_drafts WHERE id = ? AND session_id = ?", (draft_id, session_id)).fetchone()
        if row is None or row["status"] != "pending":
            return None
        conn.execute(
            "UPDATE ai_drafts SET status = ?, updated_at = ? WHERE id = ?", (status, clock.now().isoformat(), draft_id)
        )
    return {"draft_id": draft_id, "status": status}
