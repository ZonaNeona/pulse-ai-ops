"""Client for the Hermes Agent API server: a turn is `POST /v1/runs` plus the SSE stream of its events.

Hermes calls our tools through the MCP server (`pulse.agents.mcp_server`, a separate process it spawns),
so before a turn we write the visitor's session into `var/agent_turn.json` — that is how a draft created
by Hermes lands in the right visitor's list. Turns go one at a time for the same reason.

Every tool event becomes a trace step with the time Hermes reported it. A run that exceeds the time limit
is stopped (`/v1/runs/{id}/stop`) — it must not keep calling tools unseen.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field

import httpx

from pulse.agents.trace import Trace
from pulse.core.config import get_settings

log = logging.getLogger(__name__)

RUN_TIMEOUT_S = 75
QUEUE_WAIT_S = 20  # a visitor waits this long for the previous turn, then the built-in loop answers instead
_lock = asyncio.Lock()
_transport: httpx.AsyncBaseTransport | None = None  # tests plug a mock transport in here


class HermesUnavailable(RuntimeError):
    """Hermes is not configured, busy or failed; the caller falls back to the built-in loop."""


@dataclass
class HermesResult:
    text: str
    model: str
    tools: list[str] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0


def configured() -> bool:
    return bool(get_settings().hermes_api_url)


def _client(timeout: float | httpx.Timeout) -> httpx.AsyncClient:
    s = get_settings()
    return httpx.AsyncClient(
        base_url=s.hermes_api_url.rstrip("/"),
        headers={"Authorization": f"Bearer {s.hermes_api_key}"},
        timeout=timeout,
        transport=_transport,
        trust_env=False,
    )


def _write_turn(session: str) -> None:
    path = get_settings().pulse_data_dir / "agent_turn.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"session": session, "at": time.time()}), encoding="utf-8")


async def run(question: str, session: str, trace: Trace) -> HermesResult:
    if not configured():
        raise HermesUnavailable("Hermes не настроен")
    try:
        await asyncio.wait_for(_lock.acquire(), QUEUE_WAIT_S)
    except TimeoutError:
        raise HermesUnavailable("Hermes занят другим ходом") from None
    try:
        _write_turn(session)
        return await _turn(question, session, trace)
    finally:
        _lock.release()


async def _turn(question: str, session: str, trace: Trace) -> HermesResult:
    run_id = None
    start = trace.elapsed()
    try:
        async with _client(20) as client:
            resp = await client.post("/v1/runs", json={"input": question, "session_id": f"pulse-{session}"})
            resp.raise_for_status()
            body = resp.json()
            run_id = body.get("run_id") or body.get("id")
        trace.add("llm", "hermes.run", "Hermes принял ход", "Hermes", start, trace.elapsed() - start, f"run {run_id}")
        return await asyncio.wait_for(_events(str(run_id), trace), RUN_TIMEOUT_S)
    except (httpx.HTTPError, ValueError, TimeoutError) as exc:
        log.warning("hermes turn failed: %s", type(exc).__name__)
        if run_id:
            await _stop(str(run_id))
        raise HermesUnavailable("Hermes не ответил") from None


async def _events(run_id: str, trace: Trace) -> HermesResult:
    open_tools: dict[str, float] = {}
    used: list[str] = []
    answer = ""
    client = _client(httpx.Timeout(RUN_TIMEOUT_S, connect=10))
    async with client, client.stream("GET", f"/v1/runs/{run_id}/events") as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line.startswith("data:"):
                continue
            try:
                event = json.loads(line[5:].strip())
            except ValueError:
                continue
            kind = event.get("event") or event.get("type")
            name = str(event.get("tool") or event.get("tool_name") or "").split("__")[-1]
            if kind == "tool.started" and name:
                open_tools[name] = trace.elapsed()
                used.append(name)
            elif kind == "tool.completed" and name:
                began = open_tools.pop(name, trace.elapsed())
                detail = "ошибка" if event.get("error") else str(event.get("preview") or "")[:120]
                trace.add("tool", name, name, "Инструменты (MCP)", began, trace.elapsed() - began, detail)
            elif kind and kind.startswith("subagent.") and kind.endswith(("complete", "completed")):
                label = str(event.get("goal") or event.get("name") or "подагент")[:80]
                dur = float(event.get("duration") or 0) * 1000
                trace.add("subagent", "subagent", label, "Подагенты", trace.elapsed() - dur, dur)
            elif kind == "message.delta":
                answer += str(event.get("delta") or "")
            elif kind == "run.completed":
                usage = event.get("usage") or {}
                runtime = event.get("runtime") or {}
                return HermesResult(
                    text=str(event.get("output") or answer).strip(),
                    model=str(runtime.get("model") or ""),
                    tools=used,
                    prompt_tokens=int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0),
                    completion_tokens=int(usage.get("completion_tokens") or usage.get("output_tokens") or 0),
                    cost_usd=float(usage.get("cost") or usage.get("cost_usd") or 0.0),
                )
            elif kind in ("run.failed", "run.cancelled", "run.interrupted"):
                raise HermesUnavailable(str(event.get("error") or kind))
    raise HermesUnavailable("поток событий оборвался")


async def _stop(run_id: str) -> None:
    try:
        async with _client(10) as client:
            await client.post(f"/v1/runs/{run_id}/stop", json={})
    except httpx.HTTPError:
        log.warning("hermes stop failed")
