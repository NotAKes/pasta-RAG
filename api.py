from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
import json
import asyncio
from main import main as start_logic_bot
import logging
from pydantic import BaseModel
from typing import List, Optional
from bot import bot

origins = [
    "http://localhost",
    "http://127.0.0.1:8080",
    "http://localhost:8080",
    "https://resplendently-connectional-maryanna.ngrok-free.dev",
]

logging.basicConfig(
    filename='logs.log',
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)



# 1. Модель данных (то, что присылает React)
class OrderItem(BaseModel):
    id: str
    quantity: int
    price: float
    title: str

class OrderRequest(BaseModel):
    user_id: Optional[int] = None  # Теперь необязательно!
    name: Optional[str] = None     # Для сайта
    phone: Optional[str] = None    # Для сайта
    table: str
    items: List[OrderItem]


@asynccontextmanager
async def lifespan(app: FastAPI):
    bot_task = asyncio.create_task(start_logic_bot())
    yield
    bot_task.cancel()

app = FastAPI(lifespan=lifespan)



app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.post("/api/create_order")
async def create_order(order:OrderRequest):
    try:
        items = order.items


        text = ""
        total = sum(p.price * p.quantity for p in items)
        for item in items:
            name = item.title
            price = item.price
            qty = item.quantity
            row_sum = price * qty
            text += f"{name} x{qty} = {row_sum} PHP\n"

        text += f"\n💰 *Итого: {total} PHP*"
        try:
            await bot.send_message(int(order.user_id), text=f"🧾 *Ваш заказ к столу №{order.table}📍:*\n\n" + text, parse_mode="Markdown")
        #TODO
        except Exception as e:
                print(f"Не удалось отправить подтверждение клиенту: {e}")


        await bot.send_message(1423155014, text=f"🧾 *Новый заказ:*\n\n к столу №{order.table}📍\n" + text,
                               parse_mode="Markdown")
        return {"status": "ok", "message": "Заказ принят"}
    except Exception as e:
        print(f"Ошибка при создании заказа: {e}")
        return {"status": "error", "detail": str(e)}


@app.get("/api")
async def api_read_menu():
    try:
        with open('/app/instruction.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        menu = data.copy()
        for item in data:
            metadata = item.get("metadata", {})
            categories = metadata.get("categories", [])

            if categories[0] == "info":
                menu.remove(item)
        return  menu

    except Exception as e:
        print(f"ERROR: {str(e)}")
        return {"error": str(e)}