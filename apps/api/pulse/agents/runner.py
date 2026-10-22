"""One copilot turn, routed to the cheapest brain that can answer it honestly:

1. a frequent question with a clear intent → `quick` (tools only, instant, free);
2. a question about the company's rules → the knowledge module (answer with verified citations);
3. anything else → Hermes Agent (tools over MCP, subagents) when it is up,
   otherwise the built-in tool loop on the same tools through `core.llm`;
4. no model at all → an honest note and what works without one.

Whatever answered, the trace holds only what really happened, with measured times and the real cost.
"""

import json
import re
import uuid
from typing import Any

from pulse.agents import hermes, quick, tools
from pulse.agents import trace as traces
from pulse.agents.trace import Trace
from pulse.core import budget, clock, llm
from pulse.core.visitor import Visitor
from pulse.modules import knowledge

MAX_TURNS = 5
RULES = re.compile(
    r"скидк|гаранти|регламент|политик|неустойк|рекламац|предоплат|аванс|возврат|можно ли|допуст|разреш|"
    r"по правилам|кто согласует|согласован|срок\w* (выезд|ответ|перезвон|поставк|оплат)"
)

SYSTEM = """Ты — ИИ-помощник руководителя в компании «Норд Инжиниринг» (поставка и монтаж инженерного
оборудования для бизнеса). Сегодня {today}. У тебя есть инструменты над CRM (Битрикс24), 1С, входящими
документами и регламентами компании.

Правила:
- каждое число и имя бери из ответа инструмента; если данных нет — так и скажи, не придумывай;
- для вопросов о правилах компании вызывай knowledge_search и ссылайся на документ и раздел;
- изменить что-то в CRM ты не можешь: предложи действие через draft_task — человек сам подтвердит черновик;
- отвечай по-русски, коротко: 2–6 строк, ключевые цифры и имена выделяй **так**, без таблиц и заголовков."""

SOURCE = {
    "sales_pulse": ("Обзор", "/"),
    "get_signals": ("Сделать сейчас", "/"),
    "team_status": ("Команда", "/sales/team"),
    "get_deals": ("Сделки", "/sales/deals"),
    "call_feed": ("Звонки", "/sales/calls"),
    "call_review": ("Звонки", "/sales/calls"),
    "reconciliation": ("Сверка CRM ↔ 1С", "/integrations"),
    "erp_stock": ("1С", "/integrations"),
    "docs_queue": ("Документы", "/docs"),
    "knowledge_search": ("Знания", "/knowledge"),
}

WITHOUT_MODEL = (
    "Свободные вопросы обрабатывает модель, а сейчас она недоступна: {reason}.\n"
    "Без модели работают готовые вопросы — кто просел, зависшие сделки, сверка с 1С, худший звонок, "
    "документы на проверке, пропущенные, просрочки, склад, выручка — и вопросы по регламентам."
)


def _reason(exc: Exception) -> str:
    """«Дневной бюджет … исчерпан — до завтра …» → «дневной бюджет … исчерпан» (abbreviations keep their case)."""
    text = str(exc).split(" — ")[0].rstrip(".")
    return text[0].lower() + text[1:] if len(text) > 1 and text[1].islower() else text


def _sources(used: list[str]) -> list[dict[str, str]]:
    seen: dict[str, str] = {}
    for name in used:
        if name in SOURCE:
            label, href = SOURCE[name]
            seen.setdefault(label, href)
    return [{"label": k, "href": v} for k, v in seen.items()]


async def ask(question: str, visitor: Visitor) -> dict[str, Any]:
    question = question.strip()[:800]
    trace = Trace(question, visitor.session)
    since = clock.now().isoformat()
    token = tools.session.set(visitor.session)
    try:
        text, sources = await _answer(question, visitor, trace)
    finally:
        tools.session.reset(token)
    traces.save(trace, text, sources)
    created = [d for d in tools.drafts(visitor.session) if d["created_at"] >= since]
    return {
        "id": f"a_{uuid.uuid4().hex[:8]}",
        "role": "assistant",
        "text": text,
        "sources": sources,
        "engine": trace.engine,
        "trace": trace.to_dict(),
        "drafts": [draft_view(d) for d in created],
    }


def draft_view(d: dict[str, Any]) -> dict[str, Any]:
    p = d["payload"]
    return {
        "draft_id": d["id"],
        "status": d["status"],
        "title": d["title"],
        "responsible": p.get("responsible", ""),
        "deadline": p.get("deadline", "")[:10],
        "dealId": p.get("deal_id"),
    }


async def _answer(question: str, visitor: Visitor, trace: Trace) -> tuple[str, list[dict[str, str]]]:
    with trace.step("route", "router", "Маршрутизация вопроса", "Маршрутизатор") as info:
        handler = quick.match(question)
        rules = handler is None and bool(RULES.search(question.lower()))
        info["detail"] = "готовый вопрос" if handler else "регламенты" if rules else "свободный вопрос"
    # Frequent questions never spend the visitor's model quota: once it is used up they must still work.
    if handler:
        trace.engine = "rules"
        reply = await handler(trace, question)
        return reply.text, reply.sources
    if rules:
        return await _knowledge(question, visitor, trace)
    if hermes.configured() and llm.available():
        try:
            return await _hermes(question, visitor, trace)
        except hermes.HermesUnavailable as exc:
            trace.add(
                "llm",
                "hermes",
                "Hermes недоступен — отвечает встроенный цикл",
                "Hermes",
                trace.elapsed(),
                0.1,
                str(exc),
            )
    return await _loop(question, visitor, trace)


async def _knowledge(question: str, visitor: Visitor, trace: Trace) -> tuple[str, list[dict[str, str]]]:
    trace.engine = "kb"
    with trace.step("tool", "knowledge", "Поиск по регламентам и ответ", "База знаний") as info:
        ans = await knowledge.answer(question, visitor.quota)
        info["detail"] = {
            "model": "ответ модели, цитаты проверены",
            "extract": "выдержки из регламентов",
            "refusal": "в регламентах нет",
        }[ans.mode]
        info["cost"] = ans.cost_usd
    trace.model = ans.model
    text = ans.text
    if ans.sources:
        text += "\n\n" + "\n".join(f"[{s.id}] {s.title}, {s.section}" for s in ans.sources)
    if ans.note:
        text += f"\n\n{ans.note}."
    return text, [{"label": "Знания", "href": "/knowledge?q=" + question[:120]}] if ans.grounded else []


async def _hermes(question: str, visitor: Visitor, trace: Trace) -> tuple[str, list[dict[str, str]]]:
    try:
        reserve_id = budget.reserve(visitor.quota, "question", llm.ESTIMATE_USD["question"])
    except RuntimeError as exc:
        trace.engine = "none"
        return WITHOUT_MODEL.format(reason=_reason(exc)), []
    trace.engine = "hermes"
    try:
        res = await hermes.run(question, visitor.session, trace)
    except hermes.HermesUnavailable:
        budget.settle(reserve_id, 0.0, {"error": "hermes"})
        raise
    budget.settle(
        reserve_id,
        res.cost_usd,
        {"engine": "hermes", "tokens": res.prompt_tokens + res.completion_tokens, "model": res.model},
    )
    trace.model = res.model
    trace.tokens = res.prompt_tokens + res.completion_tokens
    trace.cost_usd = res.cost_usd or llm.ESTIMATE_USD["question"]  # no reported cost: the estimate stays booked
    return res.text or "Hermes не дал ответа — переформулируйте вопрос.", _sources(res.tools)


async def _loop(question: str, visitor: Visitor, trace: Trace) -> tuple[str, list[dict[str, str]]]:
    """The built-in agent: the model chooses tools, we run them, up to MAX_TURNS rounds."""
    trace.engine = "model"
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM.format(today=f"{clock.today():%d.%m.%Y}")},
        {"role": "user", "content": question},
    ]
    used: list[str] = []
    for turn in range(MAX_TURNS):
        start = trace.elapsed()
        try:
            res = await llm.chat(messages, visitor=visitor.quota, tools=tools.specs(), reserve=turn == 0)
        except llm.LlmUnavailable as exc:
            if turn == 0:
                trace.engine = "none"
                return WITHOUT_MODEL.format(reason=_reason(exc)), []
            return "Модель перестала отвечать посреди ответа — попробуйте ещё раз.", _sources(used)
        calls = res.message.get("tool_calls") or []
        trace.model = res.model
        trace.tokens += res.tokens
        what = ", ".join(c["function"]["name"] for c in calls) if calls else "ответ"
        trace.add("llm", "model", f"Модель: {what}", "Модель", start, res.ms, f"{res.tokens} ток.", res.cost_usd)
        if not calls:
            return res.text or "Модель не дала ответа — переформулируйте вопрос.", _sources(used)
        messages.append({"role": "assistant", "content": res.message.get("content") or "", "tool_calls": calls})
        for c in calls:
            name = c["function"]["name"]
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except ValueError:
                args = {}
            result = await quick.call(trace, name, args if isinstance(args, dict) else {})
            used.append(name)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": c["id"],
                    "content": json.dumps(result, ensure_ascii=False, default=str)[:12_000],
                }
            )
    return "Вопрос оказался слишком составным для одного хода — разбейте его на части.", _sources(used)


latest = traces.latest
