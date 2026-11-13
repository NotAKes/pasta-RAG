"""Admin token and Telegram Web App signature verification."""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


def verify_telegram_init_data(raw: str, bot_token: str, *, now: int | None = None) -> dict:
    if not raw or not bot_token:
        raise ValueError("Missing Telegram credentials")
    pairs = parse_qsl(raw, keep_blank_values=True)
    fields = dict(pairs)
    if len(pairs) != len(fields):
        raise ValueError("Duplicate Telegram fields")
    signature = fields.pop("hash", "")
    check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(signature, expected):
        raise ValueError("Invalid Telegram signature")
    try:
        age = (int(time.time()) if now is None else now) - int(fields["auth_date"])
        user = json.loads(fields["user"])
        if not isinstance(user, dict) or not isinstance(user.get("id"), int) or user["id"] <= 0:
            raise ValueError("Invalid Telegram user")
    except (KeyError, TypeError, json.JSONDecodeError):
        raise ValueError("Invalid Telegram authentication data") from None
    if age < -30 or age > 86400:
        raise ValueError("Expired Telegram authentication")
    return user
