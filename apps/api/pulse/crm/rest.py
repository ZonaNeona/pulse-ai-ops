"""Live Bitrix24 over an inbound webhook — read-only by construction.

Only methods from a closed allowlist can be called, with a fixed set of parameters each; the check runs
before any network I/O. Calls are spaced to stay under the portal's rate limit, responses are size-capped,
and error messages never echo the webhook URL (it carries a secret token).
"""

import asyncio
import json
import re
import time
from typing import Any
from urllib.parse import urlsplit

import httpx

LIST = frozenset({"filter", "order", "select", "start"})
ALLOWED: dict[str, frozenset[str]] = {
    "scope": frozenset(),
    "server.time": frozenset(),
    "department.get": frozenset({"sort", "order", "start", "ID"}),
    "user.get": frozenset({"filter", "select", "sort", "order", "start"}),
    "crm.category.list": frozenset({"entityTypeId", "start"}),
    "crm.status.list": LIST,
    "crm.deal.fields": frozenset(),
    "crm.deal.list": LIST,
    "crm.company.list": LIST,
    "crm.contact.list": LIST,
    "crm.lead.list": LIST,
    "crm.activity.list": LIST,
    "crm.stagehistory.list": LIST | {"entityTypeId"},
    "crm.item.list": LIST | {"entityTypeId"},
    "crm.activity.call.getTranscript": frozenset({"activityId"}),
    "tasks.task.list": LIST,
    "voximplant.statistic.get": frozenset({"FILTER", "SORT", "ORDER", "start"}),
}
WEBHOOK = re.compile(r"/rest/\d+/[A-Za-z0-9]+/?")
MAX_BYTES = 8 * 1024 * 1024


class ReadOnlyViolation(ValueError):
    """The call is not in the allowlist or has parameters outside it."""


class BitrixUnavailable(RuntimeError):
    """The portal did not answer or answered with an error."""


def validate(method: str, params: dict[str, Any]) -> None:
    if method not in ALLOWED:
        raise ReadOnlyViolation(f"Метод {method} не входит в список чтения")
    extra = set(params) - ALLOWED[method]
    if extra:
        raise ReadOnlyViolation(f"Недопустимые параметры: {', '.join(sorted(extra))}")
    if len(json.dumps(params, default=str)) > 32_000:
        raise ReadOnlyViolation("Слишком большой запрос")
    start = params.get("start")
    if start is not None and (type(start) is not int or not 0 <= start <= 500_000):
        raise ReadOnlyViolation("Недопустимая страница")
    for key in ("filter", "FILTER"):
        if key in params and not isinstance(params[key], dict):
            raise ReadOnlyViolation("Фильтр должен быть объектом")


class Bitrix24RestAdapter:
    def __init__(self, webhook: str, *, interval: float = 0.6, transport: httpx.AsyncBaseTransport | None = None):
        parts = urlsplit(webhook)
        if parts.scheme != "https" or not parts.netloc or parts.query or not WEBHOOK.fullmatch(parts.path):
            raise ReadOnlyViolation("Ожидается входящий вебхук вида https://<портал>/rest/<id>/<токен>/")
        self._base = webhook.rstrip("/") + "/"
        self._interval = max(0.5, interval)  # Bitrix24 allows ~2 requests per second per portal
        self._transport = transport
        self._lock = asyncio.Lock()
        self._last = 0.0
        self.calls = 0

    async def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        validate(method, params)  # must precede any network activity
        async with self._lock:
            await asyncio.sleep(max(0.0, self._interval - (time.monotonic() - self._last)))
            self._last = time.monotonic()
            try:
                async with (
                    httpx.AsyncClient(timeout=20, transport=self._transport, follow_redirects=False) as client,
                    client.stream("POST", f"{self._base}{method}.json", json=params) as response,
                ):
                    self.calls += 1
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_BYTES:
                            raise BitrixUnavailable("Ответ больше 8 МБ")
                    if response.status_code == 503:
                        raise BitrixUnavailable("QUERY_LIMIT_EXCEEDED")
                    payload: dict[str, Any] = json.loads(body)
            except BitrixUnavailable:
                raise
            except Exception:
                # httpx errors include the request URL, and the URL contains the webhook token.
                raise BitrixUnavailable("Портал недоступен или ответ не в формате JSON") from None
        if payload.get("error"):
            code = str(payload["error"])
            raise BitrixUnavailable(code if re.fullmatch(r"[A-Za-z0-9_]+", code) else "API_ERROR")
        return payload
