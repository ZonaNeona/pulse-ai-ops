"""Telegram bot: the webhook is closed without the secret, replies come from the same modules as the screens."""

from collections.abc import AsyncGenerator, Iterator
from datetime import datetime
from typing import Any

import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.methods import SendMessage, TelegramMethod
from aiogram.types import Chat, Message
from fastapi.testclient import TestClient

from pulse.bot import handlers, service
from pulse.core.config import get_settings
from pulse.main import app

TOKEN = "123456:TEST-token-for-tests"


class Capture(BaseSession):
    """Records what the bot sends instead of calling Telegram."""

    def __init__(self) -> None:
        super().__init__()
        self.sent: list[TelegramMethod[Any]] = []

    async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None) -> Any:  # noqa: ASYNC109
        self.sent.append(method)
        if isinstance(method, SendMessage):
            return Message(
                message_id=len(self.sent), date=datetime.now(), chat=Chat(id=1, type="private"), text=method.text
            )
        return True

    async def stream_content(self, *args: Any, **kwargs: Any) -> AsyncGenerator[bytes, None]:  # pragma: no cover
        yield b""

    async def close(self) -> None:
        pass

    def texts(self) -> list[str]:
        return [m.text for m in self.sent if isinstance(m, SendMessage)]


@pytest.fixture
def telegram(monkeypatch: pytest.MonkeyPatch) -> Iterator[Capture]:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    get_settings.cache_clear()
    capture = Capture()
    service._bot = Bot(TOKEN, session=capture, default=DefaultBotProperties(parse_mode="HTML"))
    yield capture
    service._bot = None  # the dispatcher and its router are kept: a router attaches once


def update(text: str, user: int = 42) -> dict[str, Any]:
    chat = {"id": user, "type": "private"}
    sender = {"id": user, "is_bot": False, "first_name": "Гость"}
    return {
        "update_id": 1,
        "message": {"message_id": 1, "date": 1_760_000_000, "chat": chat, "from": sender, "text": text},
    }


def test_webhook_is_closed_without_a_bot_or_with_a_wrong_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app)
    assert client.post("/api/bot/webhook", json=update("/start")).status_code == 403
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    get_settings.cache_clear()
    wrong = {"X-Telegram-Bot-Api-Secret-Token": "guess"}
    assert client.post("/api/bot/webhook", json=update("/start"), headers=wrong).status_code == 403


async def test_doc_command_shows_the_visitors_queue_with_decision_buttons(ready: None, telegram: Capture) -> None:
    await service.feed(update("/doc"))
    [text] = telegram.texts()
    assert "№ 2417" in text and "❌ Сумма совпадает с заказом" in text
    markup = next(m for m in telegram.sent if isinstance(m, SendMessage)).reply_markup
    assert [b.text for b in markup.inline_keyboard[0]] == ["Провести", "Отклонить"]  # type: ignore[union-attr]


async def test_text_question_is_answered_by_the_copilot(ready: None, telegram: Capture) -> None:
    await service.feed(update("Какие сделки зависли больше 7 дней?"))
    [text] = telegram.texts()
    assert "без движения" in text and "<b>" in text and "**" not in text


async def test_secret_header_lets_telegram_in(ready: None, telegram: Capture) -> None:
    headers = {"X-Telegram-Bot-Api-Secret-Token": service.secret()}
    response = TestClient(app).post("/api/bot/webhook", json=update("/start"), headers=headers)
    assert response.status_code == 200
    assert "Норд Инжиниринг" in telegram.texts()[0]


def test_rich_text_escapes_html_and_keeps_bold() -> None:
    assert handlers.rich("**7 сделок** <script>") == "<b>7 сделок</b> &lt;script&gt;"


def test_each_telegram_user_is_a_separate_visitor() -> None:
    from aiogram.types import User

    a, b = (handlers.who(User(id=i, is_bot=False, first_name="x")) for i in (1, 2))
    assert a.session != b.session and a.quota != b.quota
