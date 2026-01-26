import asyncio
import os

from bot import dp, bot
from aiogram import types
from aiogram.filters.command import Command
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from bot import engine, async_session_maker
# from handlers import cmd_start
from middleware import DbSessionMiddleware

load_dotenv()
Base = declarative_base()
USER = os.getenv("user")
PASSWORD = os.getenv("password")
HOST = os.getenv("host")
PORT = os.getenv("port")
DBNAME = os.getenv("dbname")
DATABASE_URL = f"postgresql+asyncpg://{USER}:{PASSWORD}@{HOST}:{PORT}/{DBNAME}"

load_dotenv()


# engine = None
# async_session_maker= None

# engine = create_async_engine(DATABASE_URL, echo=True, future=True)
# async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

import handlers
# async def init_db():


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    dp.update.middleware(DbSessionMiddleware(session_pool=async_session_maker))
    await dp.start_polling(bot)



# router = Router()
# Команда /start



if __name__ == "__main__":
    asyncio.run(main())
