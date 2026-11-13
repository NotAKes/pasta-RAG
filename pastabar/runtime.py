"""Composition root: explicitly own startup/shutdown and optional integrations."""

import shutil

from .assistant import AssistantService
from .database import OrderRepository
from .history import MemoryHistory, RedisHistory
from .media import MediaRepository
from .menu import MenuRepository
from .orders import OrderService
from .retrieval import RetrievalService


class Runtime:
    def __init__(self, settings):
        self.settings = settings
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        # Never migrate or rewrite the source menu on disk. Copy the seed once;
        # production may explicitly point MENU_PATH at the live menu in DATA_DIR.
        live_menu = settings.data_dir / "menu.json"
        if not live_menu.exists():
            shutil.copyfile(settings.menu_path, live_menu)
        self.menu = MenuRepository(live_menu)
        self.media = MediaRepository(settings.data_dir / "uploads")
        self.repository = OrderRepository(settings.resolved_database_url)
        self.history = RedisHistory(settings.redis_url) if settings.telegram_enabled else MemoryHistory()
        self.retrieval = RetrievalService(self.menu, settings)
        self.assistant = AssistantService(settings, self.retrieval, self.history)
        from .telegram import DemoNotifier, TelegramTransport

        self.transport = (
            TelegramTransport(settings, self.assistant, self.repository) if settings.telegram_enabled else None
        )
        self.orders = OrderService(self.menu, self.repository, self.transport or DemoNotifier())

    async def start(self):
        self.menu.migrate_ids()
        await self.repository.start()
        if self.settings.rag_enabled:
            await self.retrieval.start()
        if self.transport:
            await self.transport.start()

    async def close(self):
        if self.transport:
            await self.transport.close()
        await self.assistant.close()
        await self.retrieval.close()
        await self.history.close()
        await self.repository.close()
