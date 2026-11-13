"""Public menu and order endpoints."""

from fastapi import APIRouter, Header, HTTPException, Request

from ..schemas import OrderRequest
from ..security import verify_telegram_init_data

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    runtime = request.app.state.runtime
    return {
        "status": "ok",
        "retrieval": runtime.retrieval.status,
        "telegram": "enabled" if runtime.transport else "disabled",
    }


@router.get("/api")
async def menu(request: Request):
    return request.app.state.runtime.menu.public_items()


@router.get("/api/banner")
async def banner(request: Request):
    return {"video_url": request.app.state.runtime.media.banner()}


@router.post("/api/create_order", status_code=201)
async def create_order(request: Request, order: OrderRequest, x_telegram_init_data: str | None = Header(default=None)):
    runtime = request.app.state.runtime
    user = None
    if x_telegram_init_data:
        try:
            user = verify_telegram_init_data(x_telegram_init_data, runtime.settings.bot_token)
        except ValueError as error:
            raise HTTPException(status_code=401, detail=str(error)) from error
    # Browser guests are allowed; an unsigned user_id is intentionally ignored.
    try:
        return await runtime.orders.place(order, user)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
