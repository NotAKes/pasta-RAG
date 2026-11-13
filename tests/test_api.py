"""HTTP contracts against an isolated, offline application lifecycle."""

import base64
import json
import sqlite3
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from pastabar.app import create_app
from pastabar.config import Settings


@pytest.fixture
def raw_menu():
    return [
        {
            "text": "Mushroom pasta 250 PHP",
            "metadata": {"dish_name": "Mushroom pasta", "price": 250, "categories": ["menu", "pasta"]},
        },
        {
            "text": "Tomato pasta 180.50 PHP",
            "metadata": {"dish_name": "Tomato pasta", "price": 180.50, "categories": ["menu", "vegan"]},
        },
        {"text": "Open every day from 8 AM", "metadata": {"categories": ["info", "hours"]}},
    ]


@pytest.fixture
def settings(tmp_path, raw_menu):
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps(raw_menu), encoding="utf-8")
    return Settings(
        data_dir=tmp_path / "data",
        menu_path=seed,
        static_dir=tmp_path / "static",
        database_url="",
        admin_token="test-admin-token-at-least-16-characters",
        bot_token="",
        deepseek_key="",
        rag_enabled=False,
        telegram_enabled=False,
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        yield client


@pytest.fixture
def admin_headers(settings):
    return {"X-Admin-Token": settings.admin_token}


def order_body(client):
    dishes = client.get("/api").json()
    return {
        "user_id": 123456789,
        "name": " Alice ",
        "phone": " +63 123456 ",
        "table": " Hotel 7 ",
        "items": [
            {"id": dishes[0]["id"], "quantity": 2, "price": 0.01, "title": "FAKE"},
            {"id": dishes[1]["id"], "quantity": 1},
        ],
        "total": "0.01",
    }


def stored_orders(settings):
    with sqlite3.connect(settings.data_dir / "pastabar.db") as connection:
        return connection.execute("SELECT id, payload, notification_status FROM orders").fetchall()


def test_public_menu_and_health_are_offline_and_ids_are_persisted(client, settings, raw_menu):
    response = client.get("/api")
    assert response.status_code == 200
    assert len(response.json()) == 2
    assert all("info" not in dish["metadata"]["categories"] for dish in response.json())
    assert len({dish["id"] for dish in response.json()}) == 2
    persisted = json.loads((settings.data_dir / "menu.json").read_text())
    assert len(persisted) == 3
    assert all(isinstance(item["id"], str) and item["id"] for item in persisted)
    assert [item["id"] for item in persisted[:2]] == [item["id"] for item in response.json()]
    assert json.loads(settings.menu_path.read_text()) == raw_menu  # Seed remains untouched.
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["telegram"] == "disabled"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_order_uses_server_prices_and_stores_guest_contact(client, settings):
    response = client.post("/api/create_order", json=order_body(client))
    assert response.status_code == 201
    result = response.json()
    assert result["status"] == "ok"
    assert result["order_id"]
    assert result["total"] == "680.50"
    assert result["currency"] == "PHP"
    assert result["notification_status"] == "pending"
    rows = stored_orders(settings)
    assert len(rows) == 1
    order_id, raw_payload, delivery = rows[0]
    assert order_id == result["order_id"]
    assert delivery == "pending"
    payload = json.loads(raw_payload)
    assert payload["phone"] == "+63 123456"
    assert payload["table"] == "Hotel 7"
    assert payload["name"] == "Alice"
    assert payload["telegram_id"] is None
    assert payload["total"] == "680.50"
    assert payload["items"][0]["title"] == "Mushroom pasta"
    assert payload["items"][0]["price"] == "250.00"
    assert payload["items"][0]["subtotal"] == "500.00"


@pytest.mark.parametrize(
    "invalid", ["unknown", "duplicate", "blank-phone", "blank-table", "bool-qty", "zero-qty", "empty"]
)
def test_invalid_orders_are_not_stored(client, settings, invalid):
    body = order_body(client)
    if invalid == "unknown":
        body["items"][0]["id"] = "not-in-the-menu"
    elif invalid == "duplicate":
        body["items"][1]["id"] = body["items"][0]["id"]
    elif invalid.startswith("blank-"):
        body[invalid.split("-", 1)[1]] = " \t\n "
    elif invalid == "bool-qty":
        body["items"][0]["quantity"] = True
    elif invalid == "zero-qty":
        body["items"][0]["quantity"] = 0
    else:
        body["items"] = []
    assert client.post("/api/create_order", json=body).status_code == 422
    assert stored_orders(settings) == []


def test_invalid_telegram_signature_is_not_treated_as_guest(client, settings):
    response = client.post(
        "/api/create_order", json=order_body(client), headers={"X-Telegram-Init-Data": "user=123&hash=forged"}
    )
    assert response.status_code == 401
    assert stored_orders(settings) == []


@pytest.mark.parametrize("token", [None, "wrong-token"])
@pytest.mark.parametrize(
    "method,path,kwargs",
    [
        ("GET", "/api/admin/menu", {}),
        ("POST", "/api/admin/menu", {"json": []}),
        ("POST", "/api/admin/upload", {"json": {"data": "invalid"}}),
        ("POST", "/api/admin/banner", {"content": b"video", "headers": {"Content-Type": "video/mp4"}}),
        ("DELETE", "/api/admin/banner", {}),
    ],
)
def test_admin_endpoints_require_auth(client, token, method, path, kwargs):
    kwargs = dict(kwargs)
    headers = dict(kwargs.pop("headers", {}))
    if token is not None:
        headers["X-Admin-Token"] = token
    assert client.request(method, path, headers=headers, **kwargs).status_code == 403


def test_admin_menu_same_size_update_visible_and_survives_restart(client, settings, admin_headers):
    response = client.get("/api/admin/menu", headers=admin_headers)
    assert response.status_code == 200
    menu = response.json()
    ids = [item["id"] for item in menu]
    menu[0]["metadata"]["price"] = 350
    menu[0]["metadata"]["dish_name"] = "Renamed pasta"
    menu[0]["text"] = "Renamed pasta 350 PHP"
    menu.reverse()
    response = client.post("/api/admin/menu", headers=admin_headers, json=menu)
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "count": 3}
    public = client.get("/api").json()
    updated = next(item for item in public if item["id"] == ids[0])
    assert updated["metadata"]["price"] == 350
    assert updated["metadata"]["dish_name"] == "Renamed pasta"
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get("/api/admin/menu", headers=admin_headers).json() == menu


@pytest.mark.parametrize("invalid", ["empty", "negative-price", "missing-price", "bad-categories", "duplicate-id"])
def test_invalid_admin_menu_does_not_replace_saved_menu(client, admin_headers, invalid):
    original = client.get("/api/admin/menu", headers=admin_headers).json()
    menu = json.loads(json.dumps(original))
    if invalid == "empty":
        menu = []
    elif invalid == "negative-price":
        menu[0]["metadata"]["price"] = -1
    elif invalid == "missing-price":
        del menu[0]["metadata"]["price"]
    elif invalid == "bad-categories":
        menu[0]["metadata"]["categories"] = "menu"
    else:
        menu[1]["id"] = menu[0]["id"]
    assert client.post("/api/admin/menu", headers=admin_headers, json=menu).status_code == 422
    assert client.get("/api/admin/menu", headers=admin_headers).json() == original


@pytest.mark.parametrize(
    "data", ["", "%%%", "data:image/png;base64,%%%", base64.b64encode(b"not an image").decode(), 123]
)
def test_image_upload_rejects_invalid_data(client, settings, admin_headers, data):
    assert client.post("/api/admin/upload", headers=admin_headers, json={"data": data}).status_code == 422
    assert list((settings.data_dir / "uploads").glob("dish_upload_*")) == []


def test_image_upload_validates_actual_format_and_is_publicly_served(client, admin_headers):
    stream = BytesIO()
    Image.new("RGB", (2, 2), "red").save(stream, format="PNG")
    binary = stream.getvalue()
    response = client.post(
        "/api/admin/upload",
        headers=admin_headers,
        json={"data": "data:image/jpeg;base64," + base64.b64encode(binary).decode()},
    )
    assert response.status_code == 200
    url = response.json()["url"]
    assert url.startswith("/uploads/") and url.endswith(".png")
    assert client.get(url).content == binary


def test_empty_banner_is_rejected_without_orphan_file(client, settings, admin_headers):
    assert client.get("/api/banner").json() == {"video_url": None}
    response = client.post("/api/admin/banner", content=b"", headers={**admin_headers, "Content-Type": "video/mp4"})
    assert response.status_code == 422
    assert client.get("/api/banner").json() == {"video_url": None}
    assert list((settings.data_dir / "uploads").glob("banner_*")) == []


def test_banner_delete_removes_saved_file(client, settings, admin_headers):
    response = client.post(
        "/api/admin/banner", content=b"test-video-bytes", headers={**admin_headers, "Content-Type": "video/mp4"}
    )
    assert response.status_code == 200
    url = response.json()["video_url"]
    assert client.get("/api/banner").json() == {"video_url": url}
    assert client.get(url).content == b"test-video-bytes"
    assert client.delete("/api/admin/banner", headers=admin_headers).json() == {"video_url": None}
    assert not (settings.data_dir / "uploads" / url.rsplit("/", 1)[1]).exists()


def test_admin_can_review_orders(client):
    # Saved orders remain reviewable even when demo mode cannot deliver Telegram.
    menu = client.get("/api").json()
    placed = client.post(
        "/api/create_order",
        json={
            "name": "Review guest",
            "phone": "@review",
            "table": "Hotel",
            "items": [{"id": menu[0]["id"], "quantity": 1}],
        },
    )
    assert placed.status_code == 201
    assert client.get("/api/admin/orders").status_code == 403
    # Fixture exposes its configured secret through the runtime, not production env.
    token = client.app.state.runtime.settings.admin_token
    response = client.get("/api/admin/orders", headers={"X-Admin-Token": token})
    assert response.status_code == 200
    order = response.json()[0]
    assert order["id"] == placed.json()["order_id"]
    assert order["payload"]["phone"] == "@review"
    assert order["notification_status"] == "pending"
