from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
import json
import asyncio
from main import main as start_logic_bot
import logging
origins = [
    "http://localhost",
    "http://127.0.0.1:8080",
    "http://localhost:8080",
    "https://myfrontendapp.com",
]

logging.basicConfig(
    filename='logs.log',
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    bot_task = asyncio.create_task(start_logic_bot())
    yield
    bot_task.cancel()

app = FastAPI(lifespan=lifespan)



app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Allows specific origins
    allow_credentials=True,  # Allows cookies, authorization headers, etc.
    allow_methods=["*"],  # Allows all methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allows all headers
)
@app.get("/api/menu")
def api_read_menu():
    try:
        with open('/pastabarai/instruction.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data
    except Exception as e:
        print(f"ERROR: {str(e)}")  # Это точно появится в логах Docker
        return {"error": str(e)}