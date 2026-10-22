from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from pulse.core import clock
from pulse.core.config import get_settings

# A fixed Wednesday afternoon: the planted story (missed calls at 11:20 and 13:35) is already visible.
NOW = datetime(2026, 10, 21, 16, 40, tzinfo=ZoneInfo("Europe/Moscow"))


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("PULSE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CRM_MODE", "emulator")
    monkeypatch.setenv("ERP_MODE", "emulator")
    monkeypatch.setenv("ADMIN_KEY", "test-admin")
    get_settings.cache_clear()
    clock.freeze(NOW)
    yield tmp_path
    clock.freeze(None)
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def dataset() -> tuple[dict, dict]:  # type: ignore[type-arg]
    from pulse.seed import b24

    return b24.generate(NOW)


@pytest.fixture
async def ready() -> None:
    """A synced demo company in the test's own data dir."""
    from pulse import sync
    from pulse.core import db

    db.init()
    await sync.reset()


class Script(list):  # type: ignore[type-arg]
    """Scripted model replies (OpenRouter response bodies) and the requests that were sent."""

    requests: list[dict]  # type: ignore[type-arg]


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> Iterator[Script]:
    """A connected model: append replies to the script, read what was sent from `script.requests`."""
    import json

    import httpx

    from pulse.core import llm

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    get_settings.cache_clear()
    replies = Script()
    sent: list[dict] = []  # type: ignore[type-arg]
    replies.requests = sent

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        if not replies:
            return httpx.Response(503)
        return httpx.Response(200, json=replies.pop(0))

    llm._transport = httpx.MockTransport(handle)
    yield replies
    llm._transport = None


def reply(content: str = "", tool_calls: list[dict] | None = None, cost: float = 0.0012) -> dict:  # type: ignore[type-arg]
    message: dict = {"role": "assistant", "content": content}  # type: ignore[type-arg]
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "model": "deepseek/deepseek-chat",
        "choices": [{"message": message}],
        "usage": {"prompt_tokens": 900, "completion_tokens": 60, "cost": cost},
    }


def tool_call(name: str, args: dict, call_id: str = "c1") -> dict:  # type: ignore[type-arg]
    import json

    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
    }
