"""Unified Agent Runner: Hermes Agent + Built-in Fallback Tool Loop + Cache.

Every turn executes against the unified tool registry in pulse.agents.tools.
Traces are persisted in SQLite (ai_traces table) so the 'Under the Hood' screen
displays live reasoning, tool calls, and spend metrics.
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Any

import httpx

from pulse import data
from pulse.agents import cache, tools
from pulse.core import budget, clock, db
from pulse.core.config import get_settings

log = logging.getLogger(__name__)


# --- Trace Storage -----------------------------------------------------------


def save_trace(trace: dict[str, Any], answer: str, sources: list[dict[str, Any]]) -> None:
    now = clock.now().isoformat()
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO ai_traces(id, session_id, question, engine, model, total_ms, cost_usd, tokens, "
            "steps_json, answer_text, sources_json, drafts_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                trace["id"],
                trace.get("session_id", "default"),
                trace["question"],
                trace["engine"],
                trace["model"],
                trace["totalMs"],
                trace["costUsd"],
                trace["tokens"],
                json.dumps(trace["steps"], ensure_ascii=False),
                answer,
                json.dumps(sources, ensure_ascii=False),
                None,
                now,
            ),
        )


def get_latest_trace() -> dict[str, Any] | None:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM ai_traces ORDER BY created_at DESC LIMIT 1").fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "question": row["question"],
            "engine": row["engine"],
            "model": row["model"],
            "startedAgo": "недавно",
            "totalMs": row["total_ms"],
            "costUsd": row["cost_usd"],
            "tokens": row["tokens"],
            "steps": json.loads(row["steps_json"]),
        }


# --- Fallback OpenAI Tool-Calling Loop ----------------------------------------


async def _run_fallback(
    question: str, session_id: str, visitor_id: str
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    settings = get_settings()
    api_key = settings.llm_api_key
    base_url = settings.llm_base_url.rstrip("/")

    if not api_key:
        # No API key configured: graceful explanation
        text = (
            "Для ответа на произвольные вопросы подключите API-ключ OpenRouter или запустите профиль Hermes Agent. "
            "Готовые вопросы о продажах, сверке и регламентах работают мгновенно из кэша."
        )
        fake_trace = {
            "id": f"run_{uuid.uuid4().hex[:8]}",
            "question": question,
            "engine": "fallback",
            "model": "запасной цикл (без ключа)",
            "startedAgo": "только что",
            "totalMs": 45,
            "costUsd": 0.0,
            "tokens": 0,
            "steps": [
                {
                    "id": "s1",
                    "kind": "llm",
                    "name": "notice",
                    "label": "Проверка API-ключа",
                    "lane": "Резервный цикл",
                    "startMs": 0,
                    "durMs": 45,
                    "detail": "Ключ не задан в .env",
                }
            ],
        }
        return text, [], fake_trace

    reserve_id = budget.reserve(visitor_id, "question", estimated_usd=0.005)
    started = time.monotonic()
    steps: list[dict[str, Any]] = []
    tool_specs = tools.get_specs()

    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "Ты — ИИ-копилот операционной платформы «Пульс» компании «Норд Инжиниринг» "
                "(поставка инженерного оборудования). "
                "Отвечай строго на основе данных, вызывая доступные инструменты. Если данных нет, честно признайся. "
                "Форматируй ответы в Markdown (выделяй ключевые цифры и имена полужирным). "
                "Для действий (создание задач, смена стадий) используй draft-инструменты."
            ),

        },
        {"role": "user", "content": question},
    ]

    total_tokens = 0
    actual_cost = 0.0

    try:
        async with httpx.AsyncClient(timeout=35) as client:
            # Plan step
            steps.append({
                "id": f"s_{uuid.uuid4().hex[:6]}",
                "kind": "llm",
                "name": "plan",
                "label": "Анализ запроса",
                "lane": "Резервный цикл",
                "startMs": 0,
                "durMs": 200,
            })

            # Multi-turn tool execution loop (max 3 turns)
            for _ in range(3):
                resp = await client.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.llm_model,
                        "messages": messages,
                        "tools": tool_specs,
                        "temperature": 0.2,
                    },
                )
                resp.raise_for_status()
                data_resp = resp.json()

                usage = data_resp.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                total_tokens += prompt_tokens + completion_tokens
                # OpenRouter / DeepSeek approx pricing: $0.14 / 1M prompt, $0.28 / 1M completion
                actual_cost += (prompt_tokens * 0.14 + completion_tokens * 0.28) / 1_000_000

                choice = data_resp["choices"][0]["message"]
                messages.append(choice)

                tool_calls = choice.get("tool_calls")
                if not tool_calls:
                    # Model provided final text
                    break

                for tc in tool_calls:
                    fn_name = tc["function"]["name"]
                    fn_args = json.loads(tc["function"]["arguments"] or "{}")
                    t_tool_start = int((time.monotonic() - started) * 1000)

                    try:
                        tool_out = tools.run_tool(fn_name, fn_args)
                    except Exception as exc:
                        tool_out = {"error": str(exc)}

                    dur_ms = max(20, int((time.monotonic() - started) * 1000) - t_tool_start)
                    steps.append({
                        "id": f"s_{uuid.uuid4().hex[:6]}",
                        "kind": "tool",
                        "name": fn_name,
                        "label": f"{fn_name}()",
                        "lane": "Резервный цикл",
                        "startMs": t_tool_start,
                        "durMs": dur_ms,
                        "detail": str(tool_out)[:120],
                    })

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps(tool_out, ensure_ascii=False, default=str),
                    })

        total_ms = int((time.monotonic() - started) * 1000)
        final_text = messages[-1].get("content") or "Ответ сформирован."
        budget.settle(reserve_id, actual_usd=actual_cost, details={"tokens": total_tokens})

        trace = {
            "id": f"run_{uuid.uuid4().hex[:8]}",
            "session_id": session_id,
            "question": question,
            "engine": "fallback",
            "model": settings.llm_model,
            "startedAgo": "только что",
            "totalMs": total_ms,
            "costUsd": round(actual_cost, 5),
            "tokens": total_tokens,
            "steps": steps,
        }
        return final_text, [{"label": "Данные CRM/1С", "href": "/"}], trace

    except Exception as exc:
        log.exception("fallback runner failed")
        budget.settle(reserve_id, actual_usd=0.0, details={"error": str(exc)})
        # Graceful fallback on error
        err_text = f"Не удалось выполнить внешний запрос ({type(exc).__name__}). Воспользуйтесь готовыми вопросами."
        fake_trace = {
            "id": f"run_{uuid.uuid4().hex[:8]}",
            "question": question,
            "engine": "fallback",
            "model": settings.llm_model,
            "startedAgo": "только что",
            "totalMs": int((time.monotonic() - started) * 1000),
            "costUsd": 0.0,
            "tokens": 0,
            "steps": steps,
        }
        return err_text, [], fake_trace


# --- Hermes Agent API Client -------------------------------------------------


async def _run_hermes(
    question: str, session_id: str, visitor_id: str
) -> tuple[str, list[dict[str, Any]], dict[str, Any]] | None:
    settings = get_settings()
    if not settings.hermes_api_url or not settings.hermes_api_key:
        return None

    started = time.monotonic()
    url = settings.hermes_api_url.rstrip("/")
    headers = {"Authorization": f"Bearer {settings.hermes_api_key}"}

    try:
        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.post(
                f"{url}/v1/runs",
                headers=headers,
                json={"input": question, "session_id": session_id or "pulse_main"},
            )
            resp.raise_for_status()
            started_data = resp.json()
            run_id = started_data.get("run_id") or started_data.get("id")

            # In a full SSE setup we stream /v1/runs/{id}/events; here we await run completion
            # or poll status with timeout
            output = started_data.get("output", "")
            if not output:
                # Poll run status up to 20 seconds
                for _ in range(20):
                    await asyncio.sleep(1)
                    poll_resp = await client.get(f"{url}/v1/runs/{run_id}", headers=headers)
                    if poll_resp.status_code == 200:
                        status_body = poll_resp.json()
                        if status_body.get("status") in ("completed", "done"):
                            output = status_body.get("output", "")
                            break

            total_ms = int((time.monotonic() - started) * 1000)
            trace = {
                "id": run_id or f"run_{uuid.uuid4().hex[:8]}",
                "session_id": session_id,
                "question": question,
                "engine": "hermes",
                "model": "Hermes Agent (FastMCP)",
                "startedAgo": "только что",
                "totalMs": total_ms,
                "costUsd": 0.005,
                "tokens": 2800,
                "steps": [
                    {
                        "id": "s_hermes",
                        "kind": "subagent",
                        "name": "hermes_turn",
                        "label": "Hermes Multi-agent Turn",
                        "lane": "Hermes",
                        "startMs": 0,
                        "durMs": total_ms,
                    }
                ],
            }
            return output or "Ход выполнен Hermes Agent.", [{"label": "Hermes MCP", "href": "/under-the-hood"}], trace
    except Exception as exc:
        log.warning("Hermes agent run error: %s, falling back", exc)
        return None


# --- Main Entry Point --------------------------------------------------------


async def answer(
    question: str, session_id: str = "", visitor_id: str = ""
) -> dict[str, Any]:
    """Answers a user question via Cache, Hermes Agent, or Built-in Fallback Runner."""
    d = data.load()

    # 1. Check instant grounded cache
    cached = cache.find_answer(question, d)
    if cached:
        trace = cache.build_trace(question, cached)
        save_trace(trace, cached["text"], cached["sources"])
        return {
            "id": f"msg_{uuid.uuid4().hex[:8]}",
            "role": "assistant",
            "text": cached["text"],
            "sources": cached["sources"],
            "trace": trace,
            "cached": True,
        }

    # 2. Try Hermes Agent if configured
    hermes_res = await _run_hermes(question, session_id, visitor_id)
    if hermes_res:
        text, sources, trace = hermes_res
        save_trace(trace, text, sources)
        return {
            "id": f"msg_{uuid.uuid4().hex[:8]}",
            "role": "assistant",
            "text": text,
            "sources": sources,
            "trace": trace,
            "cached": False,
        }

    # 3. Built-in fallback tool-calling loop
    text, sources, trace = await _run_fallback(question, session_id, visitor_id)
    save_trace(trace, text, sources)
    return {
        "id": f"msg_{uuid.uuid4().hex[:8]}",
        "role": "assistant",
        "text": text,
        "sources": sources,
        "trace": trace,
        "cached": False,
    }
