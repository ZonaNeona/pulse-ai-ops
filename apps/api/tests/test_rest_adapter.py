import json

import httpx
import pytest

from pulse.crm.rest import Bitrix24RestAdapter, BitrixUnavailable, ReadOnlyViolation

HOOK = "https://portal.example.ru/rest/1/secrettoken123/"


def adapter(handler: httpx.MockTransport) -> Bitrix24RestAdapter:
    a = Bitrix24RestAdapter(HOOK, transport=handler)
    a._interval = 0  # no rate-limit sleeps in tests
    return a


async def test_calls_allowed_method_with_json_body() -> None:
    seen: list[httpx.Request] = []

    def handle(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200, json={"result": [{"ID": "1"}], "total": 1})

    res = await adapter(httpx.MockTransport(handle)).call("crm.deal.list", {"select": ["ID"]})
    assert res["result"] == [{"ID": "1"}]
    assert str(seen[0].url) == HOOK + "crm.deal.list.json"
    assert json.loads(seen[0].content) == {"select": ["ID"]}


async def test_write_methods_never_reach_the_network() -> None:
    def handle(_: httpx.Request) -> httpx.Response:
        raise AssertionError("network must not be touched")

    with pytest.raises(ReadOnlyViolation):
        await adapter(httpx.MockTransport(handle)).call("crm.deal.update", {"id": 1, "fields": {}})


@pytest.mark.parametrize(
    "hook",
    [
        "http://portal.example.ru/rest/1/abc/",
        "https://portal.example.ru/rest/abc/",
        "https://portal.example.ru/rest/1/abc/?x=1",
    ],
)
def test_rejects_anything_but_an_https_inbound_webhook(hook: str) -> None:
    with pytest.raises(ReadOnlyViolation):
        Bitrix24RestAdapter(hook)


async def test_errors_never_leak_the_webhook_token() -> None:
    def handle(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("failed to connect to " + HOOK)

    with pytest.raises(BitrixUnavailable) as err:
        await adapter(httpx.MockTransport(handle)).call("crm.deal.list")
    assert "secrettoken123" not in str(err.value)


async def test_portal_error_code_is_passed_through_sanitised() -> None:
    def handle(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": "ACCESS_DENIED", "error_description": "token " + HOOK})

    with pytest.raises(BitrixUnavailable, match=r"^ACCESS_DENIED$"):
        await adapter(httpx.MockTransport(handle)).call("crm.deal.list")
