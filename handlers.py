import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram import types
from aiogram.filters.command import Command
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from middleware import DbSessionMiddleware
from bot import dp, bot, async_session_maker

@dp.message(Command("start"))
async def cmd_start(message: types.Message, session: async_session_maker):
    # statement = select(User).where(User.name == "Spider-Boy")
    # result = await session.execute(statement)
    # print(result.scalars().one()) цуа

    await message.answer("Привет!👋 Я бот, определяющий погоду:")
    # await menu(message)


# async def menu(message: types.Message):
#     inp = [
#         [
#             types.KeyboardButton(text="О боте"),
#             types.KeyboardButton(text="Прогноз погоды")
#         ],
#     ]
#     keyboard = types.ReplyKeyboardMarkup(
#         keyboard=inp,
#         resize_keyboard=True,
#         input_field_placeholder="Выберите функцию"
#     )
#     await message.answer("Выберите функцию⚙️", reply_markup=keyboard)