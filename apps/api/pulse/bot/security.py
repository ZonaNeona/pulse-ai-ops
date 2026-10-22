"""Security utilities for Telegram WebApp (initData HMAC-SHA256 validation)."""

import hashlib
import hmac
import time
from urllib.parse import parse_qsl


def validate_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> bool:
    """Validates Telegram WebApp initData string against the bot token.

    See https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not init_data:
        return False
    if not bot_token:
        # In demo / test mode without a real token, accept well-formed initData
        return "hash=" in init_data or "user=" in init_data

    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return False

        # Check auth_date expiration if provided
        auth_date_str = parsed.get("auth_date")
        if auth_date_str:
            try:
                auth_date = int(auth_date_str)
                if time.time() - auth_date > max_age_seconds:
                    return False
            except ValueError:
                return False

        # Construct data_check_string
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))

        # Secret key = HMAC-SHA256("WebAppData", bot_token)
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()

        # Calculated hash = HMAC-SHA256(secret_key, data_check_string)
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        return hmac.compare_digest(calculated_hash, received_hash)
    except Exception:
        return False
