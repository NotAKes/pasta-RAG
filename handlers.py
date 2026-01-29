import asyncio

from torch.cuda import memory_summary

from main import user_histories
from get_context import search
from aiogram import types, F
from aiogram.filters.command import Command
# from ai_service import system_prompt
from sqlmodel import select
from models import User
from bot import dp, bot
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key="sk-c46004461d7548fd9ce679b9007fd5df", base_url="https://api.deepseek.com")

# context = ''
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
        f"Hello, {user.name}!👋\n"
        f"Your ID is: {user.tg_id}"
    )

system_prompt = f"""Ты — опытный администратор ресторана "Pastabar" в Моалбоале. 
                Твоя цель: давать безупречно точные ответы гостям и красиво оформить этот ответ для гостя.

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
    def get_limited_history(user_id, limit=6):
        if user_id not in user_histories:
            user_histories[user_id] = []
        return user_histories[user_id][-limit:]

    def add_to_history(user_id, role, content):
        if user_id not in user_histories:
            user_histories[user_id] = []
        user_histories[user_id].append({"role": role, "content": content})
        if len(user_histories[user_id]) > 20:
            user_histories[user_id].pop(0)

    context = search(message.text)
    add_to_history(message.from_user.id, "user", message.text)

    memory_msg = get_limited_history(message.from_user.id)

    response = await client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            *memory_msg[:-1],
            {"role": "user", "content": f"Context from menu: {context}\n\nQuestion: {message.text}"}
        ],
        temperature=0.3
    )

    bot_answer = response.choices[0].message.content
    add_to_history(message.from_user.id, "assistant", bot_answer.replace("**", "").replace("##", ""))
    await message.answer(bot_answer)
