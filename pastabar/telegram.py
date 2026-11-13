"""Telegram transport: consultation, order delivery and explicit acceptance by ID."""

import asyncio
import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from .orders import format_order

logger = logging.getLogger(__name__)


class DemoNotifier:
    async def notify(self, order_id, payload):
        logger.info("Demo order %s stored; Telegram delivery is disabled", order_id)
        return False


class TelegramTransport:
    def __init__(self, settings, assistant, repository):
        self.settings, self.assistant, self.repository = settings, assistant, repository
        self.bot = Bot(settings.bot_token)
        self.dispatcher = Dispatcher()
        self.task = None
        self._register_handlers()

    def menu_keyboard(self):
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="See menu and order 📱", web_app=WebAppInfo(url=self.settings.webapp_url))]
            ]
        )

    def _register_handlers(self):
        router = Router()

        @router.message(Command("start"))
        async def welcome(message):
            await message.answer(
                "Welcome to Pastabar! Ask about our menu, or open it below to order.\n"
                "Добро пожаловать! Задайте вопрос о меню или откройте его кнопкой ниже.",
                reply_markup=self.menu_keyboard(),
            )

        @router.callback_query(F.data.startswith("accept:"))
        async def accept_order(callback):
            if callback.from_user.id not in self.settings.admin_ids:
                await callback.answer("Access denied", show_alert=True)
                return
            order_id = callback.data.removeprefix("accept:")
            accepted = await self.repository.accept(order_id, callback.from_user.id)
            await callback.answer("Order accepted" if accepted else "Already accepted or not found")
            if accepted:
                await self._broadcast(f"Order {order_id} accepted by {callback.from_user.full_name}.")
                with suppress(Exception):
                    await callback.message.edit_reply_markup(reply_markup=None)

        @router.message(F.text)
        async def answer(message):
            if not message.from_user:
                return
            reply = await self.assistant.answer(message.from_user.id, message.text[:4000])
            for start in range(0, len(reply), 4000):
                await message.answer(reply[start : start + 4000], reply_markup=self.menu_keyboard())

        self.dispatcher.include_router(router)

    async def _broadcast(self, text, keyboard=None):
        delivered = 0
        for admin_id in self.settings.admin_ids:
            try:
                await self.bot.send_message(admin_id, text, reply_markup=keyboard)
                delivered += 1
            except Exception:
                logger.warning("Could not notify administrator %s", admin_id, exc_info=True)
        return delivered > 0

    async def notify(self, order_id, payload):
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Accept order", callback_data=f"accept:{order_id}")]]
        )
        delivered = await self._broadcast(format_order(order_id, payload), keyboard)
        if payload.get("telegram_id"):
            try:
                await self.bot.send_message(
                    payload["telegram_id"], format_order(order_id, payload).replace("New order", "Your order", 1)
                )
            except Exception:
                logger.info("Customer order receipt was not delivered", exc_info=True)
        return delivered

    async def start(self):
        self.task = asyncio.create_task(self.dispatcher.start_polling(self.bot, handle_signals=False))
        self.task.add_done_callback(self._polling_done)

    @staticmethod
    def _polling_done(task):
        if not task.cancelled() and task.exception():
            logger.error("Telegram polling stopped", exc_info=task.exception())

    async def close(self):
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
        await self.bot.session.close()
