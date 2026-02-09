import asyncio
import os

from sqlalchemy import text
from sqlmodel import SQLModel

from bot import dp, bot
from bot import engine, async_session_maker
from middleware import DbSessionMiddleware

#
import logging
from handlers import *
import redis
logging.basicConfig(
    filename='logs/logs.log',
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)

# DATABASE_URL = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{dbname}"




async def main():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        default_policy = text(
            """
        ALTER TABLE users ENABLE ROW LEVEL SECURITY;
        """
        )
        await conn.execute(default_policy)

    dp.update.middleware(DbSessionMiddleware(session_pool=async_session_maker))
    print("Бот запускает polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
