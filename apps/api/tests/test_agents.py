"""Agents: one tool registry, honest routing, the built-in tool loop, Hermes over SSE, drafts a person decides."""

import json
from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient
from mcp import types

from pulse.agents import hermes, mcp_server, quick, runner, tools
from pulse.core import budget
from pulse.core.visitor import Visitor
from pulse.main import app
from tests.conftest import Script, reply, tool_call

ME = Visitor(session="sess-1", quota="quota-1")
PRESETS = [
    "Кто из менеджеров просел на этой неделе?",
    "Какие сделки зависли больше 7 дней?",
    "Сравни продажи октября с оплатами в 1С",
    "Разбери худший звонок за вчера",
    "Какие документы ждут подтверждения?",
]


def test_registry_is_read_only_except_task_drafts() -> None:
    specs = tools.specs()
    names = [s["function"]["name"] for s in specs]
    assert len(names) == len(set(names)) == 11
    assert [t.name for t in tools.TOOLS.values() if t.writes] == ["draft_task"]
    assert not any("confirm" in n or "undo" in n for n in names), "an agent never confirms its own drafts"


async def test_quick_answers_only_clear_intents(ready: None) -> None:
    assert all(quick.match(q) for q in PRESETS)
    assert quick.match("Какие сделки зависли у Кузнецовой?") is None, "a narrowed question is the agent's job"
    assert quick.match("Почему зависли сделки?") is None
    assert quick.match("Что посоветуешь сделать с Медиусом?") is None
    assert quick.match("Напиши стих про весну") is None


async def test_preset_is_answered_from_tools_with_a_measured_trace(ready: None) -> None:
    stale = await tools.run("get_deals", {"stale_only": True, "limit": 50})
    answer = await runner.ask("Какие сделки зависли больше 7 дней?", ME)
    assert answer["engine"] == "rules"
    assert answer["text"].startswith(f"**{len(stale)} сдел")
    steps = answer["trace"]["steps"]
    assert [s["name"] for s in steps] == ["router", "get_deals"]
    assert all(s["durMs"] > 0 for s in steps) and answer["trace"]["costUsd"] == 0
    assert runner.latest()["question"] == "Какие сделки зависли больше 7 дней?"  # type: ignore[index]


async def test_documents_preset_sees_this_visitors_queue(ready: None) -> None:
    answer = await runner.ask("Какие документы ждут подтверждения?", ME)
    assert "№ 2417" in answer["text"] and "+9 000" in answer["text"]


async def test_rules_question_goes_to_the_knowledge_base(ready: None) -> None:
    answer = await runner.ask("Какая скидка допустима для дилера?", ME)
    assert answer["engine"] == "kb"
    assert "Ценовая политика и скидки 2026" in answer["text"]


async def test_free_question_without_a_model_says_so(ready: None) -> None:
    answer = await runner.ask("Что посоветуешь сделать с Медиусом?", ME)
    assert answer["engine"] == "none"
    assert "недоступна" in answer["text"] and "готовые вопросы" in answer["text"]


async def test_model_loop_calls_tools_and_reports_the_real_cost(ready: None, model: Script) -> None:
    model.append(reply(tool_calls=[tool_call("get_deals", {"manager": "Кузнецова", "stale_only": True})], cost=0.001))
    model.append(reply("У **Ольги Кузнецовой** три зависшие сделки.", cost=0.0015))
    answer = await runner.ask("Что с зависшими у Кузнецовой и почему?", ME)
    assert answer["engine"] == "model"
    assert answer["text"].startswith("У **Ольги")
    assert [s["name"] for s in answer["trace"]["steps"]] == ["router", "model", "get_deals", "model"]
    assert answer["trace"]["costUsd"] == pytest.approx(0.0025)
    assert answer["sources"] == [{"label": "Сделки", "href": "/sales/deals"}]
    tool_message = model.requests[1]["messages"][-1]
    assert tool_message["role"] == "tool" and "Кузнецова" in tool_message["content"]
    spend = budget.summary(ME.quota)
    assert spend["questionsLeft"] == 9 and spend["spentUsd"] == pytest.approx(0.0025)


async def test_agent_proposes_a_draft_and_only_a_person_confirms_it(ready: None, model: Script) -> None:
    args = {"title": "Перезвонить в Медиус", "responsible": "Елена Морозова", "deadline_days": 0}
    model.append(reply(tool_calls=[tool_call("draft_task", args)]))
    model.append(reply("Подготовил черновик задачи — подтвердите его."))
    answer = await runner.ask("Поставь задачу перезвонить в Медиус", ME)
    [draft] = answer["drafts"]
    assert draft["status"] == "pending" and draft["responsible"] == "Елена Морозова"
    assert tools.set_draft(draft["draft_id"], "someone-else", "confirmed") is None
    assert tools.set_draft(draft["draft_id"], ME.session, "confirmed") == {
        "draft_id": draft["draft_id"],
        "status": "confirmed",
    }
    assert tools.set_draft(draft["draft_id"], ME.session, "discarded") is None


async def test_spent_daily_budget_stops_the_model_honestly(
    ready: None, model: Script, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pulse.core.config import get_settings

    monkeypatch.setenv("AI_DAILY_USD", "0.001")
    get_settings.cache_clear()
    answer = await runner.ask("Что посоветуешь сделать с Медиусом?", ME)
    assert answer["engine"] == "none" and "бюджет" in answer["text"]
    assert not model.requests


def sse(*events: dict) -> bytes:  # type: ignore[type-arg]
    return "".join(f"data: {json.dumps(e, ensure_ascii=False)}\n\n" for e in events).encode()


@pytest.fixture
def hermes_up(monkeypatch: pytest.MonkeyPatch, model: Script) -> Iterator[list[str]]:
    from pulse.core.config import get_settings

    monkeypatch.setenv("HERMES_API_URL", "http://hermes.test")
    get_settings.cache_clear()
    calls: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path == "/v1/runs":
            return httpx.Response(200, json={"run_id": "r1"})
        events = sse(
            {"event": "tool.started", "tool": "mcp_pulse__get_signals"},
            {"event": "tool.completed", "tool": "mcp_pulse__get_signals", "preview": "[...]"},
            {
                "event": "run.completed",
                "output": "Два пропущенных без перезвона.",
                "runtime": {"model": "deepseek/deepseek-chat"},
                "usage": {"input_tokens": 1200, "output_tokens": 80, "cost": 0.0009},
            },
        )
        return httpx.Response(200, content=events, headers={"content-type": "text/event-stream"})

    hermes._transport = httpx.MockTransport(handle)
    yield calls
    hermes._transport = None


async def test_hermes_turn_is_traced_from_its_events(ready: None, hermes_up: list[str]) -> None:
    answer = await runner.ask("Что горит у отдела продаж?", ME)
    assert answer["engine"] == "hermes" and answer["text"] == "Два пропущенных без перезвона."
    names = [s["name"] for s in answer["trace"]["steps"]]
    assert names == ["router", "hermes.run", "get_signals"]
    assert answer["trace"]["tokens"] == 1280 and answer["trace"]["costUsd"] == 0.0009
    assert hermes_up == ["POST /v1/runs", "GET /v1/runs/r1/events"]


async def test_hermes_down_falls_back_to_the_built_in_loop(
    ready: None, model: Script, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pulse.core.config import get_settings

    monkeypatch.setenv("HERMES_API_URL", "http://hermes.test")
    get_settings.cache_clear()
    hermes._transport = httpx.MockTransport(lambda request: httpx.Response(502))
    model.append(reply("Ответ встроенного цикла."))
    try:
        answer = await runner.ask("Что горит у отдела продаж?", ME)
    finally:
        hermes._transport = None
    assert answer["engine"] == "model" and answer["text"] == "Ответ встроенного цикла."
    assert any("Hermes недоступен" in s["label"] for s in answer["trace"]["steps"])
    assert budget.summary(ME.quota)["questionsLeft"] == 9, "the failed Hermes turn is not charged"


async def test_mcp_server_serves_the_same_registry(ready: None) -> None:
    listed = await mcp_server.list_tools(None, None)
    assert {t.name for t in listed.tools} == set(tools.TOOLS)
    result = await mcp_server.call_tool(None, types.CallToolRequestParams(name="team_status", arguments={}))
    assert not result.is_error and "callsNorm" in result.content[0].text  # type: ignore[union-attr]
    missing = await mcp_server.call_tool(None, types.CallToolRequestParams(name="drop_tables", arguments={}))
    assert missing.is_error


async def test_api_keeps_visitors_apart_by_cookie(ready: None) -> None:
    alice, bob = TestClient(app), TestClient(app)
    first = alice.post("/api/copilot/chat", json={"message": "Какие сделки зависли больше 7 дней?"})
    assert first.status_code == 200 and "pulse_sid" in alice.cookies
    assert alice.get("/api/docs").json()[0]["id"] != bob.get("/api/docs").json()[0]["id"]
    assert bob.post("/api/drafts/draft_nope/confirm").status_code == 409
    assert alice.post("/api/copilot/chat", json={"message": ""}).status_code == 422
