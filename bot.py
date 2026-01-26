from aiogram import Bot, Dispatcher
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from dotenv import load_dotenv
load_dotenv()


USER = os.getenv("user")
PASSWORD = os.getenv("password")
HOST = os.getenv("host")
PORT = os.getenv("port")
DBNAME = os.getenv("dbname")
DATABASE_URL = f"postgresql+asyncpg://{USER}:{PASSWORD}@{HOST}:{PORT}/{DBNAME}"

engine = create_async_engine(DATABASE_URL, echo=True, future=True)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

bot = Bot(token=os.getenv("tg_key"))
dp = Dispatcher()