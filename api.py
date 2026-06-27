from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Header, HTTPException, Request, Depends
import json
import os
import re
import time
import base64
import asyncio
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text, select
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import AsyncSession

from bot import dp, bot, engine, async_session_maker
from middleware import DbSessionMiddleware
import logging
from pydantic import BaseModel, Field
from typing import List, Optional
# Импортируем модель User (убедись, что она импортирована корректно)
from models import User  # Если модель в другом файле, поправь путь
from handlers import *

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)


# --- Настройки и логгер остаются без изменений ---

# 1. Функция получения сессии БД (Dependency Injection)
async def get_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session


class OrderItem(BaseModel):
    id: str
    quantity: int = Field(..., gt=0, le=20)
    price: float
    title: str


class OrderRequest(BaseModel):
    user_id: Optional[int] = None
    name: Optional[str] = Field(None)
    phone: Optional[str] = Field(None)
    table: str = Field(...)
    items: List[OrderItem] = Field(..., min_items=1, max_items=50)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        try:
            await conn.execute(text("ALTER TABLE users ENABLE ROW LEVEL SECURITY;"))
        except Exception as e:
            print(f"⚠️ RLS Policy skip: {e}")

    dp.update.middleware(DbSessionMiddleware(session_pool=async_session_maker))
    print("🤖 Запуск polling бота...")
    polling_task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))
    yield
    polling_task.cancel()


app = FastAPI(lifespan=lifespan)

@app.post("/api/create_order")
@limiter.limit("10/minute")
async def create_order(
        request: Request,
        order: OrderRequest,
        session: AsyncSession = Depends(get_session),  # 👈 Внедряем сессию
        x_secret_token: str = Header(None)
):
    #if x_secret_token != "notakes":
        #  raise HTTPException(status_code=403, detail="Access denied")

    try:
        items = order.items
        text_lines = ""
        total = sum(p.price * p.quantity for p in items)

        for item in items:
            text_lines += f"{item.title} x{item.quantity} = {item.price * item.quantity} PHP\n"

        order_details = f"\n💰 *Total: {total} PHP*"

        # --- ЛОГИКА ОПРЕДЕЛЕНИЯ ЮЗЕРА ---
        user_display = "Unknown"

        if order.user_id:
            # Ищем юзера в базе по tg_id
            statement = select(User).where(User.tg_id == str(order.user_id))
            result = await session.execute(statement)
            db_user = result.scalar_one_or_none()

            # Если нашли и есть name — формируем name, иначе имя
            if db_user and db_user.name:
                user_display = f"{db_user.name}"
            else:
                user_display = order.name or f"ID: {order.user_id}"
            try:
                msg = f"🧾 *Your order to table №{order.table}📍:*\n\n" + text_lines + order_details
                await bot.send_message(int(order.user_id), text=msg, parse_mode="Markdown")
            except Exception as e:
                print(f"Клиент не получил сообщение: {e}")

        elif order.phone and order.name:
            user_display = f"{order.name} (Phone: {order.phone})"
        admin_id = [6178875035, 1189846903, 5621436121, 1644073645]
        for id in admin_id:
            admin_text = f"🧾 *New order:*\n\nto table №{order.table}📍\n{text_lines}{order_details}\n\n👤 *Customer:* {user_display}"
            await bot.send_message(id, text=admin_text, parse_mode="Markdown")

        return {"status": "ok", "message": "Заказ принят"}

    except Exception as e:
        logging.error(f"Ошибка при создании заказа: {e}")
        return {"status": "error", "detail": str(e)}


@app.get("/api")
@limiter.limit("10/minute")
async def api_read_menu(request: Request, x_secret_token: str = Header(None)):
    try:
        with open('/app/instruction.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        menu = data.copy()
        for item in data:
            metadata = item.get("metadata", {})
            categories = metadata.get("categories", [])

            if categories[0] == "info":
                menu.remove(item)
        return menu

    except Exception as e:
        print(f"ERROR: {str(e)}")
        return {"error": str(e)}

# ==========================================================================
# 🔐 ADMIN PANEL — управление меню (блюда, цены, картинки и т.д.)
# ==========================================================================

INSTRUCTION_PATH = "/app/instruction.json"
IMAGES_DIR = "/app/static/images"
# Токен админки. Задаётся через переменную окружения admin_token (.env).
ADMIN_TOKEN = os.getenv("admin_token", "notakes")


def _check_admin(token: Optional[str]):
    if not token or token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token")


@app.get("/api/admin/menu")
async def admin_get_menu(x_admin_token: str = Header(None)):
    """Возвращает полный instruction.json (включая info-блоки) для редактирования."""
    _check_admin(x_admin_token)
    with open(INSTRUCTION_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/admin/menu")
async def admin_save_menu(request: Request, x_admin_token: str = Header(None)):
    """Полностью перезаписывает instruction.json переданным массивом."""
    _check_admin(x_admin_token)
    data = await request.json()
    if not isinstance(data, list):
        raise HTTPException(status_code=400, detail="Expected a JSON array")

    # Лёгкая валидация структуры
    for item in data:
        if not isinstance(item, dict) or "metadata" not in item:
            raise HTTPException(status_code=400, detail="Each item needs a 'metadata' object")

    # instruction.json is bind-mounted as a single file, so os.replace() over it
    # fails with EBUSY ("Device or resource busy"). Build the full payload first
    # (so a serialization error can't leave a half-written file), then write the
    # mounted file in place.
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    with open(INSTRUCTION_PATH, "w", encoding="utf-8") as f:
        f.write(payload)
    return {"status": "ok", "count": len(data)}


@app.post("/api/admin/upload")
async def admin_upload(request: Request, x_admin_token: str = Header(None)):
    """Принимает картинку как base64 (или data-URL) и сохраняет её в /static/images."""
    _check_admin(x_admin_token)
    body = await request.json()
    raw = body.get("data")
    if not raw:
        raise HTTPException(status_code=400, detail="Missing 'data'")

    ext = "jpg"
    if isinstance(raw, str) and raw.startswith("data:"):
        header, raw = raw.split(",", 1)
        m = re.search(r"image/(\w+)", header)
        if m:
            ext = m.group(1).lower().replace("jpeg", "jpg")

    try:
        binary = base64.b64decode(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 data")

    if len(binary) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 8MB)")
    if ext not in ("jpg", "png", "webp", "gif"):
        ext = "jpg"

    os.makedirs(IMAGES_DIR, exist_ok=True)
    filename = f"dish_upload_{int(time.time() * 1000)}.{ext}"
    with open(os.path.join(IMAGES_DIR, filename), "wb") as f:
        f.write(binary)

    return {"url": f"/static/images/{filename}"}


app.mount("/static", StaticFiles(directory="/app/static"), name="static_assets")

app.mount("/", StaticFiles(directory="/app/static", html=True), name="static")
