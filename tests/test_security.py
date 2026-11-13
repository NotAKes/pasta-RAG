"""Telegram Web App HMAC test vectors generated independently of the verifier."""

import hashlib
import hmac
import json
from urllib.parse import parse_qsl, urlencode

import pytest

from pastabar.security import verify_telegram_init_data

BOT_TOKEN = "123456:test-secret-token"
NOW = 1_800_000_000


def signed_data(*, auth_date=NOW, user=None, token=BOT_TOKEN):
    fields = {
        "auth_date": str(auth_date),
        "query_id": "query-test-123",
        "user": json.dumps(
            user if user is not None else {"id": 42, "first_name": "Alice & Bob"},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }
    check = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret = hmac.digest(b"WebAppData", token.encode(), "sha256")
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def test_valid_hmac_returns_verified_user():
    assert verify_telegram_init_data(signed_data(), BOT_TOKEN, now=NOW) == {"id": 42, "first_name": "Alice & Bob"}


def test_field_order_does_not_change_valid_signature():
    pairs = parse_qsl(signed_data())
    assert verify_telegram_init_data(urlencode(list(reversed(pairs))), BOT_TOKEN, now=NOW)["id"] == 42


@pytest.mark.parametrize(
    "field,value", [("auth_date", str(NOW - 1)), ("user", '{"id":999}'), ("hash", "0" * 64), ("query_id", "tampered")]
)
def test_tampered_fields_fail_hmac(field, value):
    fields = dict(parse_qsl(signed_data()))
    fields[field] = value
    with pytest.raises(ValueError):
        verify_telegram_init_data(urlencode(fields), BOT_TOKEN, now=NOW)


@pytest.mark.parametrize("age", [86401, 100000, -31])
def test_expired_or_future_signatures_rejected(age):
    with pytest.raises(ValueError, match="Expired"):
        verify_telegram_init_data(signed_data(auth_date=NOW - age), BOT_TOKEN, now=NOW)


@pytest.mark.parametrize("age", [0, 86400, -30])
def test_allowed_time_boundaries(age):
    assert verify_telegram_init_data(signed_data(auth_date=NOW - age), BOT_TOKEN, now=NOW)["id"] == 42


@pytest.mark.parametrize("user", [{"id": 0}, {"id": -1}, {"id": "42"}, {}, [42]])
def test_correctly_signed_invalid_user_is_rejected(user):
    with pytest.raises(ValueError):
        verify_telegram_init_data(signed_data(user=user), BOT_TOKEN, now=NOW)


@pytest.mark.parametrize("raw,token", [("", BOT_TOKEN), ("hash=foo", ""), ("user=42", BOT_TOKEN)])
def test_missing_credentials_or_signature_rejected(raw, token):
    with pytest.raises(ValueError):
        verify_telegram_init_data(raw, token, now=NOW)


def test_duplicate_fields_rejected_even_with_original_valid_signature():
    with pytest.raises(ValueError, match="Duplicate"):
        verify_telegram_init_data(signed_data() + f"&auth_date={NOW}", BOT_TOKEN, now=NOW)


def test_wrong_bot_token_rejected():
    with pytest.raises(ValueError):
        verify_telegram_init_data(signed_data(), "different-token", now=NOW)
