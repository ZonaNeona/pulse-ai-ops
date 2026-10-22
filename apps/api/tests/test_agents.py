"""Tests for AI agents layer: tools registry, cache, budget, runner, and endpoints."""

import pytest
from fastapi.testclient import TestClient

from pulse import data, sync
from pulse.agents import cache, runner, tools
from pulse.core import budget, db


@pytest.fixture
async def snapshot() -> data.Data:
    db.init()
    await sync.reset()
    return data.load()


def test_tools_execution(snapshot: data.Data) -> None:
    pulse_res = tools.run_tool("sales_pulse", {})
    assert "kpis" in pulse_res
    assert pulse_res["signals_count"] > 0

    sigs = tools.run_tool("get_signals", {"limit": 5})
    assert len(sigs) <= 5

    team_res = tools.run_tool("team_status", {})
    assert len(team_res) >= 5

    rec = tools.run_tool("reconciliation", {})
    assert len(rec["gaps"]) == 4

    stocks = tools.run_tool("erp_stock", {"query": "\u0447\u0438\u043b\u043b\u0435\u0440"})
    assert len(stocks) > 0
    assert "available" in stocks[0]

    # Test draft workflow: create -> confirm -> undo
    draft = tools.run_tool(
        "draft_task",
        {
            "title": "Устранить расхождение",
            "responsible": "Елена Морозова",
            "deadline_days": 2,
        },
    )
    assert draft["status"] == "pending_confirmation"
    draft_id = draft["draft_id"]

    confirmed = tools.run_tool("confirm_draft", {"draft_id": draft_id})
    assert confirmed["status"] == "confirmed"

    undone = tools.run_tool("undo_draft", {"draft_id": draft_id})
    assert undone["status"] == "undone"


def test_cache_answers_all_presets(snapshot: data.Data) -> None:
    presets = [
        "Кто из менеджеров просел на этой неделе?",
        "Какие сделки зависли больше 7 дней?",
        "Сравни продажи октября с оплатами в 1С",
        "Разбери худший звонок за вчера",
        "Какие документы ждут подтверждения?",
        "Какая скидка допустима для дилера?",
        "Что требует внимания сегодня?",
        "Где пропущенные без перезвона?",
        "Сколько чиллеров осталось на складе?",
    ]
    for q in presets:
        ans = cache.find_answer(q, snapshot)
        assert ans is not None, f"Preset '{q}' must be matched in cache"
        assert len(ans["text"]) > 20
        assert len(ans["sources"]) > 0

        trace = cache.build_trace(q, ans)
        assert trace["engine"] == "hermes"
        assert len(trace["steps"]) >= 2
        assert trace["totalMs"] > 0


def test_budget_limits_and_reservation(snapshot: data.Data) -> None:
    s = budget.summary("test_visitor_1")
    assert s["capUsd"] == 1.5
    assert s["questionsLeft"] == 10

    # Reserve amount
    res_id = budget.reserve("test_visitor_1", "question", 0.005, {"q": "test"})
    assert res_id.startswith("res_")

    s2 = budget.summary("test_visitor_1")
    assert s2["spentUsd"] == 0.005
    assert s2["questionsLeft"] == 9

    # Settle
    budget.settle(res_id, actual_usd=0.0025)
    s3 = budget.summary("test_visitor_1")
    assert s3["spentUsd"] == 0.0025


@pytest.mark.asyncio
async def test_runner_answers_from_cache(snapshot: data.Data) -> None:
    res = await runner.answer("Кто из менеджеров просел?")
    assert res["role"] == "assistant"
    assert res["cached"] is True
    assert "Лебедев" in res["text"]
    assert "trace" in res
    assert res["trace"]["engine"] == "hermes"


def test_api_chat_and_trace_endpoints() -> None:
    from pulse.main import app

    with TestClient(app) as client:
        # Chat endpoint
        r = client.post(
            "/api/copilot/chat",
            json={"message": "Сравни продажи октября с оплатами в 1С"},
            headers={"x-visitor-id": "web_test_user"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["role"] == "assistant"
        assert "trace" in body

        # Latest trace endpoint
        tr_resp = client.get("/api/trace/latest")
        assert tr_resp.status_code == 200
        tr_body = tr_resp.json()
        assert "steps" in tr_body
        assert len(tr_body["steps"]) > 0

        # Budget endpoint
        b_resp = client.get("/api/budget", headers={"x-visitor-id": "web_test_user"})
        assert b_resp.status_code == 200
        b_body = b_resp.json()
        assert b_body["capUsd"] == 1.5
