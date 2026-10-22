"""Telegram bot (aiogram 3) running inside the API process: webhook in, the same modules out."""

from pulse.bot.service import check_secret, feed, setup_webhook, status

__all__ = ["check_secret", "feed", "setup_webhook", "status"]
