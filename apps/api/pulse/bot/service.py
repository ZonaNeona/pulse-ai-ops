"""Bot lifecycle: one aiogram Bot + Dispatcher, a webhook protected by Telegram's secret token header.

No token — no bot: the webhook answers 403 and the status says the bot is not connected yet.
"""

import hashlib
import hmac
import logging
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, Update

from pulse.bot.handlers import COMMANDS, router
from pulse.core.config import get_settings

log = logging.getLogger(__name__)
_bot: Bot | None = None
_dp: Dispatcher | None = None


def _token() -> str:
    return get_settings().telegram_bot_token.strip()


def secret() -> str:
    """Derived from the token, so there is no second secret to keep; Telegram echoes it in every update."""
    return hmac.new(_token().encode(), b"pulse-webhook", hashlib.sha256).hexdigest()[:48]


def check_secret(value: str) -> bool:
    return bool(_token()) and hmac.compare_digest(value, secret())


def _get() -> tuple[Bot, Dispatcher]:
    global _bot, _dp
    if _bot is None:
        _bot = Bot(_token(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    if _dp is None:
        _dp = Dispatcher()
        _dp.include_router(router)
    return _bot, _dp


async def feed(update: dict[str, Any]) -> None:
    bot, dp = _get()
    await dp.feed_update(bot, Update.model_validate(update, context={"bot": bot}))


async def setup_webhook() -> None:
    """On start: point Telegram at our webhook (public HTTPS URL only) and publish the command menu."""
    s = get_settings()
    if not _token() or not s.public_url.startswith("https://"):
        return
    bot, _ = _get()
    try:
        await bot.set_webhook(
            f"{s.public_url.rstrip('/')}/api/bot/webhook",
            secret_token=secret(),
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True,
        )
        await bot.set_my_commands([BotCommand(command=c, description=d) for c, d in COMMANDS])
    except Exception:  # Telegram unreachable: the web app works without the bot
        log.warning("telegram webhook setup failed", exc_info=True)


def status() -> dict[str, Any]:
    s = get_settings()
    return {
        "connected": bool(_token()),
        "miniAppUrl": s.public_url.rstrip("/"),
        "commands": [{"command": f"/{c}", "description": d} for c, d in COMMANDS],
    }
