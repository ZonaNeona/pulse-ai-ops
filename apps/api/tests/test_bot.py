"""Tests for Telegram bot handlers, webhook dispatching, and WebApp security."""

import hashlib
import hmac
import time
from typing import Any

import pytest
from starlette.testclient import TestClient

from pulse.bot import feed_update, get_status, validate_init_data
from pulse.core import db
from pulse.main import app
from pulse.modules import docs as docs_mod


def _generate_test_init_data(bot_token: str, user_id: int = 123456) -> str:
    auth_date = int(time.time())
    data_dict = {
        "auth_date": str(auth_date),
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": f'{{"id":{user_id},"first_name":"Иван","username":"ivan_nord"}}',
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data_dict.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    data_dict["hash"] = calc_hash
    return "&".join(f"{k}={v}" for k, v in data_dict.items())


def test_validate_init_data() -> None:
    """Tests Telegram initData HMAC-SHA256 signature validation."""
    token = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
    valid_data = _generate_test_init_data(token, 101)

    assert validate_init_data(valid_data, token) is True
    # Tampered data
    tampered_data = valid_data.replace("ivan_nord", "hacker")
    assert validate_init_data(tampered_data, token) is False
    # Empty string
    assert validate_init_data("", token) is False


def test_bot_status_endpoint() -> None:
    """Tests GET /api/bot/status."""
    status_direct = get_status()
    assert "commands" in status_direct

    client = TestClient(app)
    resp = client.get("/api/bot/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "configured" in data
    assert "miniAppUrl" in data
    assert len(data["commands"]) >= 4
    cmds = [c["command"] for c in data["commands"]]
    assert "/start" in cmds
    assert "/today" in cmds
    assert "/team" in cmds
    assert "/doc" in cmds


def test_validate_init_data_endpoint() -> None:
    """Tests POST /api/bot/validate_init_data."""
    client = TestClient(app)
    resp = client.post("/api/bot/validate_init_data", json={"init_data": "user=123&hash=abc"})
    assert resp.status_code == 200
    assert "valid" in resp.json()


@pytest.mark.asyncio
async def test_bot_webhook_feed_updates() -> None:
    """Feeds simulated Telegram updates (/start, /today, /team, /doc) through the dispatcher."""
    db.init()
    docs_mod.list_docs()

    # 1. /start update
    start_update: dict[str, Any] = {
        "update_id": 1001,
        "message": {
            "message_id": 1,
            "date": int(time.time()),
            "chat": {"id": 999001, "type": "private"},
            "from": {"id": 999001, "is_bot": False, "first_name": "Тестер"},
            "text": "/start",
        },
    }
    await feed_update(start_update)

    # 2. /today update
    today_update: dict[str, Any] = {
        "update_id": 1002,
        "message": {
            "message_id": 2,
            "date": int(time.time()),
            "chat": {"id": 999001, "type": "private"},
            "from": {"id": 999001, "is_bot": False, "first_name": "Тестер"},
            "text": "/today",
        },
    }
    await feed_update(today_update)

    # 3. /team update
    team_update: dict[str, Any] = {
        "update_id": 1003,
        "message": {
            "message_id": 3,
            "date": int(time.time()),
            "chat": {"id": 999001, "type": "private"},
            "from": {"id": 999001, "is_bot": False, "first_name": "Тестер"},
            "text": "/team",
        },
    }
    await feed_update(team_update)

    # 4. /doc update
    doc_update: dict[str, Any] = {
        "update_id": 1004,
        "message": {
            "message_id": 4,
            "date": int(time.time()),
            "chat": {"id": 999001, "type": "private"},
            "from": {"id": 999001, "is_bot": False, "first_name": "Тестер"},
            "text": "/doc",
        },
    }
    await feed_update(doc_update)


@pytest.mark.asyncio
async def test_bot_callback_confirm_doc() -> None:
    """Tests confirming a document through Telegram callback query."""
    db.init()
    docs_mod.list_docs()

    # Callback query for confirm_doc:1
    callback_update: dict[str, Any] = {
        "update_id": 2001,
        "callback_query": {
            "id": "cb_query_123",
            "from": {"id": 999001, "is_bot": False, "first_name": "Тестер"},
            "message": {
                "message_id": 10,
                "date": int(time.time()),
                "chat": {"id": 999001, "type": "private"},
                "text": "Входящий документ ждёт подтверждения",
            },
            "chat_instance": "123456",
            "data": "confirm_doc:1",
        },
    }
    await feed_update(callback_update)

    # Verify document 1 was confirmed in SQLite
    doc = docs_mod.get_doc(1)
    assert doc is not None
    assert doc.status == "posted"
