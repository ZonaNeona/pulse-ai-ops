"""One door to the language model: an OpenAI-compatible chat call that is always metered.

Every call reserves money in the daily budget first and settles the real cost afterwards — OpenRouter
reports it in `usage.cost` when asked to. No key, no budget or a provider failure raise `LlmUnavailable`,
and the callers fall back to an answer that needs no model.
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from pulse.core import budget
from pulse.core.config import get_settings

ESTIMATE_USD = {"question": 0.004, "document": 0.006}


class LlmUnavailable(RuntimeError):
    """The model cannot be used right now; the message is safe to show to a visitor."""


@dataclass
class LlmResult:
    message: dict[str, Any]
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    ms: int = 0
    raw_usage: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return str(self.message.get("content") or "").strip()

    @property
    def tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


_transport: httpx.AsyncBaseTransport | None = None  # tests plug a mock transport in here


_prices: dict[str, tuple[float, float]] = {}


async def cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Cost of a call whose provider did not report it (Hermes runs), from the provider's price list."""
    s = get_settings()
    if not _prices and s.llm_api_key:
        try:
            async with httpx.AsyncClient(timeout=20, transport=_transport) as client:
                resp = await client.get(
                    s.llm_base_url.rstrip("/") + "/models", headers={"Authorization": f"Bearer {s.llm_api_key}"}
                )
                for m in resp.json().get("data", []):
                    p = m.get("pricing") or {}
                    _prices[m["id"]] = (float(p.get("prompt") or 0), float(p.get("completion") or 0))
        except (httpx.HTTPError, ValueError, KeyError):
            return 0.0
    prompt, completion = _prices.get(model, (0.0, 0.0))
    return prompt * prompt_tokens + completion * completion_tokens


def available() -> bool:
    return bool(get_settings().llm_api_key)


async def chat(
    messages: list[dict[str, Any]],
    *,
    visitor: str,
    action: str = "question",
    model: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    json_mode: bool = False,
    temperature: float = 0.1,
    reserve: bool = True,
) -> LlmResult:
    """One metered completion. `reserve=False` is for the follow-up turns of one already-paid request."""
    s = get_settings()
    if not s.llm_api_key:
        raise LlmUnavailable("На стенде не задан ключ модели")
    reserve_id = None
    if reserve:
        try:
            reserve_id = budget.reserve(visitor, action, ESTIMATE_USD.get(action, 0.004))
        except RuntimeError as exc:
            raise LlmUnavailable(str(exc)) from None
    body: dict[str, Any] = {
        "model": model or s.llm_model,
        "messages": messages,
        "temperature": temperature,
        "usage": {"include": True},  # OpenRouter: return the real cost of the call
    }
    if tools:
        body["tools"] = tools
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=45, transport=_transport) as client:
            resp = await client.post(
                s.llm_base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": f"Bearer {s.llm_api_key}", "X-Title": "Pulse demo"},
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError):
        if reserve_id:
            budget.settle(reserve_id, 0.0, {"error": "provider"})
        raise LlmUnavailable("Модель не ответила, попробуйте позже") from None
    usage = data.get("usage") or {}
    result = LlmResult(
        message=data["choices"][0]["message"],
        model=str(data.get("model") or body["model"]),
        prompt_tokens=int(usage.get("prompt_tokens") or 0),
        completion_tokens=int(usage.get("completion_tokens") or 0),
        cost_usd=float(usage.get("cost") or 0.0),
        ms=int((time.monotonic() - started) * 1000),
        raw_usage=usage,
    )
    if reserve_id:
        budget.settle(reserve_id, result.cost_usd, {"tokens": result.tokens, "model": result.model})
    else:
        budget.add_cost(visitor, action, result.cost_usd)
    return result


def parse_json(text: str) -> dict[str, Any]:
    """Models sometimes wrap JSON in ``` fences; take the first object that parses."""
    cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        value = json.loads(cleaned)
    except ValueError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise
        value = json.loads(cleaned[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value
