import asyncio
import os
from ai_service import get_ai_answer
from get_context import search
from aiogram import types, F
from aiogram.filters.command import Command
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlmodel import select
from sqlalchemy.orm import declarative_base
from middleware import DbSessionMiddleware
from models import User
from bot import dp, bot
from sqlalchemy.ext.asyncio import AsyncSession


@dp.message(Command("start"))
async def cmd_start(message: types.Message, session: AsyncSession):
    user_id_str = str(message.from_user.id)
    statement = select(User).where(User.tg_id == user_id_str)
    result = await session.execute(statement)
    user = result.scalar_one_or_none()
    if user is None:
        print(f"Creating new user: {message.from_user.full_name}")
        user = User(
            name=message.from_user.full_name,
            tg_id=user_id_str,
            username=message.from_user.username,
            platform="telegram",
            languages='ru'
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    else:
        print(f"User found: {user.name}")

    await message.answer(
        f"Привет, {user.name}!👋\n"
        f"Ваш ID в системе: {user.tg_id}"
    )
@dp.message(F.text)
async def answer(message: types.Message, session: AsyncSession):
    context = search(message.text)
    answer = await get_ai_answer(message.text, context)
    await message.answer(answer)
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
