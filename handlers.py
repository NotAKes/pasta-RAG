from aiogram import types, F
from aiogram.filters.command import Command
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
import os
from sqlmodel import select
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from bot import dp, bot, ADMIN_IDS
from get_context import search
from urllib.parse import quote
from redis.asyncio import Redis
import json
from models import User
from load_env import deepseek_key

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")

redis_client = Redis(host=REDIS_HOST, port=6379, decode_responses=True)
client = AsyncOpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com")

async def push_redis(user_id, content, role):
    msg_to_save = json.dumps({"role": role, "content": content}, ensure_ascii=False)
    await redis_client.rpush(f"chat_history:{user_id}", msg_to_save)
    await redis_client.ltrim(f"chat_history:{user_id}", -20, -1)

async def get_redis(user_id):
    messages_json = await redis_client.lrange(f"chat_history:{user_id}", 0, -1)
    hh = []
    for msg in messages_json:
        try:
            hh.append(json.loads(msg))
        except json.JSONDecodeError:
            continue
    return hh
'''
# раскоммент для тестов доступности аиограма
@dp.message()
async def echo_handler(message: types.Message):
    print(f"DEBUG: Пришло сообщение {message.text}")
    await message.answer("Я тебя слышу!")'''


@dp.message(Command("start"))
async def cmd_start(message: types.Message, session: AsyncSession):
    user_id_str = str(message.from_user.id)
    statement = select(User).where(User.tg_id == user_id_str)
    result = await session.execute(statement)
    user = result.scalar_one_or_none()
    if user is None:
        # print(f"Creating new user: {message.from_user.full_name}")
        user = User(
            name=message.from_user.full_name,
            tg_id=user_id_str,
            # username=message.from_user.username,
            platform="telegram",
            languages='ru'
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="See menu and order📱",
            web_app=WebAppInfo(url="https://pastamoalboal.shop/")
        )]
    ])
    await message.answer(
        f"Привет, {user.name}!👋 Можете писать ваши вопросы в этот чат!\n"
        f"Ваш ID в системе: {user.tg_id}\n"
        f"Hello, {user.name}!👋 You can write your questions in this chat\n"
        f"Your ID is: {user.tg_id}", reply_markup=kb
    )


@dp.message(F.web_app_data)
async def handle_web_app_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)

        table = data.get('table', 'Не указан')
        items = data.get('items', [])


        text = ""
        total = 0
        for item in items:
            name = item.get('title', 'Товар')
            price = item.get('price', 0)
            qty = item.get('quantity', 1)
            row_sum = price * qty
            total += row_sum
            text += f"{name} x{qty} = {row_sum} PHP\n"

        text += f"\n💰 *Итого: {total} PHP*"

        await message.answer(f"🧾 *Ваш заказ к столу №{table}📍:*\n\n" + text, parse_mode="Markdown")
        #TODO
        await message.bot.send_message(1423155014, f"🧾 *Новый заказ:*\n\n к столу №{table}📍" + text, parse_mode="Markdown")

    except Exception as e:
        await message.answer(f"Ошибка чтения данных: {e}")

system_prompt = f"""Ты — опытный администратор ресторана "Pastabar" в Моалбоале. 
                Твоя цель: давать безупречно точные ответы гостям и красиво оформить этот ответ для гостя.
                Если гость выбрал блюдо, то предложи ему забронировать столик в заведении и написать менеджеру(@Philsbrands). Обязательно предложи забронировать стол, если выбранное блюдо доступно не только по предзаказу

                ### ТВОИ ЗНАНИЯ:
                Помни, что 'Crepes' в нашем меню — это блины
                Если пользователь спрашивает общую категорию (например, 'какие есть блины?' или 'что у вас на завтрак?'), найди в предоставленном КОНТЕКСТЕ все подходящие позиции и составь из них нумерованный список. Для каждой позиции укажи название и кратко суть. Не пиши огромные абзацы для каждого вида — будь лаконичен.
                ПРАВИЛА ОФОРМЛЕНИЯ:

                Эмодзи: Используй тематические иконки (🍝, 🥞, 🍹, 💰).

                Структура: Названия блюд выделяй жирным, цену пиши на новой строке.

                Тон: "Не используй жирный шрифт для каждого второго слова. Избегай шаблонных фраз вроде 'Тропический восторг' или 'Ваш идеальный выбор', если их нет в описании. Будь лаконичен, как живой человек.
                ### ТВОИ ПРАВИЛА (НЕУКОСНИТЕЛЬНО):
                1. ПРИНЦИП "НЕТ В МЕНЮ — НЕТ В ОТВЕТЕ":
                   - Если гость просит что-то (например, вегетарианскую еду), а в предоставленном [MENU] только блюда с мясом/рыбой — ты ОБЯЗАН ответить: "К сожалению, в нашем текущем меню нет блюд, соответствующих вашему запросу". 
                   - НИКОГДА не предлагай мясные блюда как "похожие" на вегетарианские.

                2. ЯЗЫКОВОЙ БАРЬЕР:
               - В КОНТЕКСТЕ информация дублируется на английском и русском. 
               - ALWAYS respond in the same language as the user's last message. If the user asks in English, answer in English. 
                 Если пользователь спрашивает на русском, отвечай на русском.
               - Если спросили на русском — бери факты (цены, состав) из контекста, но формулируй ответ чисто по-русски.

                3. КРОСС-ЯЗЫКОВОЙ ПОИСК:
               - Если в контексте найдено "Pasta Mushrooms / Паста с грибами", считай это ОДНИМ блюдом.

                4. ПРОВЕРКА НАЛИЧИЯ:
               - Если пользователь пишет на русском "Есть что-то веганское?", а в контексте нет слова "vegetarian" или "постное/вегетарианское" — отвечай, что таких позиций нет.


                5. ПРИНЦИП ТОЧНОСТИ АДРЕСА:
                   - Если в контексте есть [INFO] с адресом, при вопросе "где вы?" выдавай его максимально подробно.

                6. ПРИНЦИП ЧЕСТНОСТИ:
                   - Если переменная КОНТЕКСТ пуста или содержит "NO_CONTEXT", ответь: "Извините, у меня нет информации по этому вопросу. Пожалуйста, напишите нашему менеджеру @Anonymous8769".

                7. СТИЛЬ:
                   - Форматирование: форматируй текст так, чтобы он корректно отображался в чате telegram и приложении facebook(без выделения с ** и ##). 
                   - Тон: дружелюбный, но профессиональный. 
                   - Язык: отвечай на том же языке, на котором обратился гость.
                   - Цены: только в PHP, как указано в меню.

                ### ПОРЯДОК ДЕЙСТВИЙ:
                Шаг 1: Проверь, есть ли в контексте ПРЯМОЙ ответ на вопрос.
                Шаг 2: Если есть противоречие (запрос на овощи, а в контексте лосось) — откажи в услуге.
                Шаг 3: Сформулируй краткий и вежливый ответ.
                """



def _is_admin_accept(message: types.Message) -> bool:
    return (
        message.from_user is not None
        and message.from_user.id in ADMIN_IDS
        and bool(message.text)
        and message.text.strip().lower() == "принял"
    )


@dp.message(_is_admin_accept)
async def admin_order_accepted(message: types.Message):
    """Когда любой админ пишет «принял» — уведомляем всех админов, что заказ принят."""
    accepted_by = message.from_user.full_name or str(message.from_user.id)
    notice = f"✅ Заказ принят администратором {accepted_by}."
    for admin in ADMIN_IDS:
        try:
            await bot.send_message(admin, notice)
        except Exception as e:
            print(f"Не удалось уведомить админа {admin}: {e}")


@dp.message(F.text)
async def answer(message: types.Message, session: AsyncSession):
    # TODO

    context = search(message.text)
    # kb = [
    #     [KeyboardButton(
    #         text="",
    #         web_app=WebAppInfo(url="")
    #     )]
    # ]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="See menu and order📱",
            web_app=WebAppInfo(url="https://pastamoalboal.shop/")
        )]
    ])
    await push_redis(message.from_user.id, message.text, "user")

    memory_msg = await get_redis(message.from_user.id)

    response = await client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            *memory_msg[:-1],
            {"role": "user", "content": f"Context from menu: {context}\n\nQuestion: {message.text}"}
        ],
        temperature=0.3
    )

    bot_answer = response.choices[0].message.content.replace("*", "").replace("#", "")
    await push_redis(message.from_user.id, bot_answer, "assistant")
    await message.answer(bot_answer, reply_markup=kb)
