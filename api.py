from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Header, HTTPException, Request
import json
import asyncio
from fastapi.staticfiles import StaticFiles
from main import main as start_logic_bot
import logging
from pydantic import BaseModel, Field, constr
from typing import List, Optional
from bot import bot


from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

origins = [
    "http://localhost",
    "http://127.0.0.1:8080",
    "http://localhost:8080",
    "https://resplendently-connectional-maryanna.ngrok-free.dev",
]

logging.basicConfig(
    filename='logs/logs.log',
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)



# 1. Модель данных (то, что присылает React)
class OrderItem(BaseModel):
    id: str
    quantity: int = Field(..., gt=0, le=20)
    price: float
    title: str

class OrderRequest(BaseModel):
    user_id: Optional[int] = None  # Теперь необязательно!
    name: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)
    table: str = Field(..., max_length=10)

    items: List[OrderItem] = Field(..., min_items=1, max_items=50)


@asynccontextmanager
async def lifespan(app: FastAPI):
    bot_task = asyncio.create_task(start_logic_bot())
    yield
    bot_task.cancel()

app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.mount("/", StaticFiles(directory="/app/static", html=True), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/create_order")
@limiter.limit("10/minute")
async def create_order(request: Request, order:OrderRequest, x_secret_token: str = Header(None)):
    if x_secret_token != "1yQ!={shr[RX3tj12w34554w2Ejyj6wef1WZ)<XtV>":
        raise HTTPException(status_code=403, detail="Access denied")
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
        return  menu

    except Exception as e:
        print(f"ERROR: {str(e)}")
        return {"error": str(e)}