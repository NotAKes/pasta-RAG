"""Durability and single-winner acceptance with real temporary SQLite databases."""

import asyncio

import pytest

from pastabar.database import OrderRepository
from pastabar.orders import OrderService, price_order
from pastabar.schemas import OrderRequest


@pytest.fixture
def catalog():
    return [
        {"id": "pasta", "text": "Pasta", "metadata": {"dish_name": "Pasta", "price": "123.45", "categories": ["menu"]}}
    ]


@pytest.fixture
def request_order():
    return OrderRequest.model_validate(
        {
            "name": " Alice ",
            "phone": " +63 123 ",
            "table": " Hotel A ",
            "user_id": 999,
            "items": [{"id": "pasta", "quantity": 3, "price": 0, "title": "Spoofed"}],
        }
    )


def test_authoritative_pricing_does_not_trust_unsigned_identity(catalog, request_order):
    payload = price_order(request_order, catalog)
    assert payload["total"] == "370.35"
    assert payload["telegram_id"] is None
    assert payload["phone"] == "+63 123"
    assert payload["items"] == [
        {"id": "pasta", "title": "Pasta", "price": "123.45", "quantity": 3, "subtotal": "370.35"}
    ]
    assert price_order(request_order, catalog, {"id": 42})["telegram_id"] == 42


def test_unavailable_dish_cannot_be_ordered(catalog, request_order):
    catalog[0]["metadata"]["available"] = False
    with pytest.raises(ValueError, match="unavailable"):
        price_order(request_order, catalog)


@pytest.mark.asyncio
async def test_notification_failure_leaves_order_durable(tmp_path, catalog, request_order):
    url = f"sqlite+aiosqlite:///{tmp_path / 'orders.db'}"
    repository = OrderRepository(url)
    await repository.start()
    notified = []

    class Menu:
        def public_items(self):
            return catalog

    class FailingNotifier:
        async def notify(self, order_id, payload):
            # Verify persistence through a separate repository before external effects.
            reader = OrderRepository(url)
            try:
                stored = await reader.get(order_id)
                assert stored is not None
                assert stored.payload == payload
            finally:
                await reader.close()
            notified.append(order_id)
            raise RuntimeError("Telegram unavailable")

    try:
        result = await OrderService(Menu(), repository, FailingNotifier()).place(request_order)
        assert result["status"] == "ok"
        assert result["notification_status"] == "pending"
        assert result["total"] == "370.35"
        assert notified == [result["order_id"]]
    finally:
        await repository.close()

    restarted = OrderRepository(url)
    try:
        await restarted.start()
        stored = await restarted.get(result["order_id"])
        assert stored is not None
        assert stored.status == "pending"
        assert stored.notification_status == "pending"
        assert stored.payload["total"] == "370.35"
        assert stored.payload["telegram_id"] is None
        assert stored.payload["phone"] == "+63 123"
    finally:
        await restarted.close()


@pytest.mark.asyncio
async def test_accept_has_exactly_one_winner_and_persists(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'orders.db'}"
    repository = OrderRepository(url)
    rival = OrderRepository(url)
    await repository.start()
    try:
        order = await repository.create({"total": "10.00", "items": []})
        results = await asyncio.gather(repository.accept(order.id, 101), rival.accept(order.id, 202))
        assert sum(results) == 1
        winner = 101 if results[0] else 202
        assert not await repository.accept(order.id, 303)
        assert not await repository.accept("does-not-exist", 303)
    finally:
        await repository.close()
        await rival.close()

    restarted = OrderRepository(url)
    try:
        stored = await restarted.get(order.id)
        assert stored is not None
        assert stored.status == "accepted"
        assert stored.accepted_by == str(winner)
        assert stored.payload == {"total": "10.00", "items": []}
        assert not await restarted.accept(order.id, 404)
    finally:
        await restarted.close()


@pytest.mark.asyncio
async def test_notification_status_update_does_not_change_order_snapshot(tmp_path):
    repository = OrderRepository(f"sqlite+aiosqlite:///{tmp_path / 'orders.db'}")
    await repository.start()
    try:
        payload = {"total": "22.00", "phone": "guest contact", "items": []}
        order = await repository.create(payload)
        await repository.mark_notification(order.id, "sent")
        stored = await repository.get(order.id)
        assert stored.notification_status == "sent"
        assert stored.status == "pending"
        assert stored.payload == payload
        assert await repository.get("missing") is None
    finally:
        await repository.close()
