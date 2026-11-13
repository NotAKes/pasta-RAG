import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from load_env import user, password, host, port, dbname

DATABASE_URL = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{dbname}"

engine = create_async_engine(DATABASE_URL, echo=True, future=True)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

bot = Bot(token=os.getenv("tg_key"))
dp = Dispatcher()

# Telegram-ID администраторов, получающих заказы и подтверждения.
ADMIN_IDS = [6178875035, 1189846903, 5621436121, 1644073645, 1423155014, 8367484968]
