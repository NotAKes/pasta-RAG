"""Durable order snapshots; schema creation is suitable for a single-instance MVP."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, DateTime, String, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    notification_status: Mapped[str] = mapped_column(String(30), default="pending")
    accepted_by: Mapped[str | None] = mapped_column(String(30), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON)


class OrderRepository:
    def __init__(self, url: str):
        self.engine = create_async_engine(url)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def start(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def create(self, payload: dict) -> Order:
        async with self.sessions() as session:
            order = Order(payload=payload)
            session.add(order)
            await session.commit()
            return order

    async def mark_notification(self, order_id: str, status: str) -> None:
        async with self.sessions() as session:
            await session.execute(update(Order).where(Order.id == order_id).values(notification_status=status))
            await session.commit()

    async def accept(self, order_id: str, admin_id: int) -> bool:
        async with self.sessions() as session:
            result = await session.execute(
                update(Order)
                .where(Order.id == order_id, Order.status == "pending")
                .values(status="accepted", accepted_by=str(admin_id))
            )
            await session.commit()
            return result.rowcount == 1

    async def get(self, order_id: str) -> Order | None:
        async with self.sessions() as session:
            return await session.get(Order, order_id)

    async def list_recent(self, limit: int = 50) -> list[dict]:
        async with self.sessions() as session:
            result = await session.scalars(select(Order).order_by(Order.created_at.desc()).limit(limit))
            return [
                {
                    "id": order.id,
                    "created_at": order.created_at.isoformat(),
                    "status": order.status,
                    "notification_status": order.notification_status,
                    "accepted_by": order.accepted_by,
                    "payload": order.payload,
                }
                for order in result
            ]

    async def close(self) -> None:
        await self.engine.dispose()
