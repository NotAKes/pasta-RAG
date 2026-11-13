"""Authoritative pricing and durable order acceptance, independent of HTTP."""

import logging
from decimal import Decimal

from .schemas import OrderRequest

logger = logging.getLogger(__name__)


def price_order(request: OrderRequest, menu: list[dict], telegram_user: dict | None = None) -> dict:
    catalog = {item["id"]: item for item in menu}
    seen = set()
    lines = []
    total = Decimal("0")
    for item in request.items:
        if item.id in seen:
            raise ValueError("Duplicate dish ID")
        seen.add(item.id)
        dish = catalog.get(item.id)
        if dish is None:
            raise ValueError("A selected dish is no longer available; please reload the menu")
        meta = dish["metadata"]
        if meta.get("available") is False:
            raise ValueError("A selected dish is currently unavailable")
        price = Decimal(str(meta["price"])).quantize(Decimal("0.01"))
        subtotal = price * item.quantity
        total += subtotal
        lines.append(
            {
                "id": item.id,
                "title": meta["dish_name"],
                "price": str(price),
                "quantity": item.quantity,
                "subtotal": str(subtotal),
            }
        )
    return {
        "name": request.name.strip() or "Guest",
        "phone": request.phone,
        "table": request.table,
        "telegram_id": telegram_user["id"] if telegram_user else None,
        "items": lines,
        "total": str(total),
        "currency": "PHP",
    }


def format_order(order_id: str, payload: dict) -> str:
    lines = [f"New order · {order_id}", f"Hotel / table: {payload['table']}", ""]
    lines.extend(f"{i['title']} ×{i['quantity']} = {i['subtotal']} PHP" for i in payload["items"])
    lines.extend(["", f"Total: {payload['total']} PHP", f"Customer: {payload['name']}", f"Contact: {payload['phone']}"])
    if payload.get("telegram_id"):
        lines.append(f"Telegram ID: {payload['telegram_id']}")
    return "\n".join(lines)


class OrderService:
    def __init__(self, menu, repository, notifier):
        self.menu, self.repository, self.notifier = menu, repository, notifier

    async def place(self, request: OrderRequest, telegram_user: dict | None = None):
        payload = price_order(request, self.menu.public_items(), telegram_user)
        order = await self.repository.create(payload)  # Commit BEFORE any external effects.
        try:
            delivered = await self.notifier.notify(order.id, payload)
            delivery = "sent" if delivered else "pending"
        except Exception:
            logger.exception("Order notification failed for %s; order remains stored", order.id)
            delivery = "pending"
        try:
            await self.repository.mark_notification(order.id, delivery)
        except Exception:
            logger.exception("Could not record notification result for %s", order.id)
        return {
            "status": "ok",
            "order_id": order.id,
            "notification_status": delivery,
            "total": payload["total"],
            "currency": "PHP",
        }
