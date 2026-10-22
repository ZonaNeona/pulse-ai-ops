"""Telegram bot module (aiogram 3 + Telegram Mini App integration)."""

from pulse.bot.security import validate_init_data
from pulse.bot.service import feed_update, get_bot, get_dispatcher, get_status, setup_webhook

__all__ = [
    "feed_update",
    "get_bot",
    "get_dispatcher",
    "get_status",
    "setup_webhook",
    "validate_init_data",
]
