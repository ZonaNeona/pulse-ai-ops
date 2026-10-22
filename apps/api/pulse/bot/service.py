"""Telegram bot service initialization, webhook management and dispatching."""

import logging
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Chat, Message, Update

from pulse.bot.handlers import router
from pulse.core.config import get_settings

log = logging.getLogger(__name__)

_bot: Bot | None = None
_dp: Dispatcher | None = None
_bot_info: dict[str, Any] = {}


def get_dispatcher() -> Dispatcher:
    global _dp
    if _dp is None:
        _dp = Dispatcher()
        _dp.include_router(router)
    return _dp


def get_bot() -> Bot | None:
    global _bot, _bot_info
    s = get_settings()
    token = s.telegram_bot_token.strip()

    if not token:
        return None

    if _bot is None:
        try:
            _bot = Bot(
                token=token,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            )
        except Exception as e:
            log.warning("Could not initialize Telegram Bot: %s", e)
            return None

    return _bot


async def setup_webhook() -> bool:
    """Configures public Telegram webhook if token and public URL are set."""
    bot = get_bot()
    if not bot:
        return False

    s = get_settings()
    public_url = s.public_url.rstrip("/")
    webhook_url = f"{public_url}/api/bot/webhook"

    try:
        current_info = await bot.get_webhook_info()
        if current_info.url != webhook_url:
            await bot.set_webhook(
                url=webhook_url,
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query"],
            )
            log.info("Telegram webhook set to %s", webhook_url)
        return True
    except Exception as e:
        log.warning("Failed to setup Telegram webhook: %s", e)
        return False


async def feed_update(data: dict[str, Any]) -> None:
    """Feeds incoming Telegram JSON update dictionary to aiogram dispatcher."""
    bot = get_bot()
    dp = get_dispatcher()

    update = Update.model_validate(data, context={"bot": bot})
    if bot:
        await dp.feed_update(bot=bot, update=update)
    else:
        # Mock bot for testing handlers in environments without a live Telegram bot token
        mock_bot = Bot(
            token="123456789:AABBCCDDEEFFGGHHIIJJKKLLMMNNOOPPQQR",  # noqa: S106
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        mock_msg = Message(
            message_id=999,
            date=datetime.now(),
            chat=Chat(id=1, type="private"),
            text="mock response",
        )
        setattr(mock_bot.session, "make_request", AsyncMock(return_value=mock_msg))  # noqa: B010
        try:
            await dp.feed_update(bot=mock_bot, update=update)
        finally:
            await mock_bot.session.close()


def get_status() -> dict[str, Any]:
    """Returns Telegram bot configuration and connectivity status."""
    s = get_settings()
    token = s.telegram_bot_token.strip()
    is_configured = bool(token)
    public_url = s.public_url.rstrip("/")
    if public_url.startswith("http://127.0.0.1") or public_url.startswith("http://localhost"):
        public_url = "https://demo.shvarev-demo.ru"

    return {
        "configured": is_configured,
        "tokenConfigured": is_configured,
        "miniAppUrl": public_url,
        "webhookUrl": f"{public_url}/api/bot/webhook" if is_configured else "",
        "commands": [
            {"command": "/start", "description": "Приветствие и запуск Mini App"},
            {"command": "/today", "description": "Сводка дня и светофор модулей"},
            {"command": "/team", "description": "Рейтинг и статус команды продаж"},
            {"command": "/doc", "description": "Очередь документов LangGraph"},
        ],
    }
