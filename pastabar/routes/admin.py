"""Authenticated menu/media management, without business logic in route handlers."""

import asyncio
import base64
import binascii
import hmac
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request

router = APIRouter(prefix="/api/admin", dependencies=[])
MAX_VIDEO_BYTES = 100 * 1024 * 1024
VIDEO_TYPES = {"video/mp4": "mp4", "video/webm": "webm", "video/quicktime": "mov"}


def require_admin(request: Request, x_admin_token: str | None = Header(default=None)):
    expected = request.app.state.runtime.settings.admin_token
    if not expected:
        raise HTTPException(status_code=503, detail="Admin access is not configured")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=403, detail="Invalid admin token")


router.dependencies.append(Depends(require_admin))


@router.get("/menu")
async def get_menu(request: Request):
    return request.app.state.runtime.menu.all_items()


@router.post("/menu")
async def save_menu(request: Request):
    try:
        data = await request.json()
        count = await asyncio.to_thread(request.app.state.runtime.menu.save, data)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    # Retrieval compares content fingerprints before semantic searches.
    return {"status": "ok", "count": count}


@router.post("/upload")
async def upload_image(request: Request):
    try:
        raw = (await request.json()).get("data", "")
        if not isinstance(raw, str) or len(raw) > 12 * 1024 * 1024:
            raise ValueError("Image too large or invalid")
        encoded = raw.split(",", 1)[1] if raw.startswith("data:") else raw
        binary = base64.b64decode(encoded, validate=True)
        url = await asyncio.to_thread(request.app.state.runtime.media.save_image, binary)
    except (ValueError, binascii.Error, IndexError, AttributeError) as error:
        raise HTTPException(status_code=422, detail="Invalid image data") from error
    return {"url": url}


@router.post("/banner")
async def upload_banner(request: Request):
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type not in VIDEO_TYPES:
        raise HTTPException(status_code=415, detail="Only MP4, WebM or MOV video is allowed")
    media = request.app.state.runtime.media
    filename = f"banner_{uuid4().hex}.{VIDEO_TYPES[content_type]}"
    path = media.directory / filename
    size = 0
    try:
        with path.open("wb") as stream:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_VIDEO_BYTES:
                    raise HTTPException(status_code=413, detail="Video too large (max 100 MB)")
                await asyncio.to_thread(stream.write, chunk)
        if not size:
            raise HTTPException(status_code=422, detail="Empty video")
        url = f"/uploads/{filename}"
        media.set_banner(url)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return {"video_url": url}


@router.delete("/banner")
async def delete_banner(request: Request):
    request.app.state.runtime.media.set_banner(None)
    return {"video_url": None}


@router.get("/orders")
async def list_orders(request: Request, limit: int = 50):
    """Review saved orders, including those without delivered Telegram notifications."""
    return await request.app.state.runtime.repository.list_recent(max(1, min(limit, 100)))
