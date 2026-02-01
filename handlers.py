from aiogram import types, F
from aiogram.filters.command import Command
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
# from ai_service import system_prompt
from sqlmodel import select

from bot import dp
from get_context import search

from redis.asyncio import Redis
import json
from models import User
from load_env import deepseek_key


redis_client = Redis(host='localhost', port=6379, decode_responses=True)
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
        f"Привет, {user.name}!👋 Можете писать ваши вопросы в этот чат!\n"
        f"Ваш ID в системе: {user.tg_id}\n"
        f"Hello, {user.name}!👋 You can write your questions in this chat\n"
        f"Your ID is: {user.tg_id}"
    )

system_prompt = f"""Ты — опытный администратор ресторана "Pastabar" в Моалбоале. 
                Твоя цель: давать безупречно точные ответы гостям и красиво оформить этот ответ для гостя.
                Если гость выбрал блюдо, то предложи ему придти в заведение или написать менеджеру(@Roza120503). Обязательно предложи придти в заведение, если выбранное блюдо доступно не только по предзаказу

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



@dp.message(F.text)
async def answer(message: types.Message, session: AsyncSession):
    # def get_limited_history(user_id, limit=6):
    #     if user_id not in redis_client:
    #         redis_client.set(user_id, [])
    #     return redis_client.get(user_id)[-limit:]
    #
    # def add_to_history(user_id, role, content):
    #     if user_id not in redis_client:
    #         redis_client.lpush(user_id,  *[])
    #     redis_client.lrange(user_id, 0 , -1).append({"role": role, "content": content})
    #     if len(redis_client.get(user_id)) > 20:
    #         redis_client.lrange(user_id, 0 , -1).pop(0)

    context = search(message.text)
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

    bot_answer = response.choices[0].message.content.replace("**", "").replace("##", "")
    await push_redis(message.from_user.id, bot_answer, "assistant")
    await message.answer(bot_answer)
