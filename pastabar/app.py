"""FastAPI application factory; no connections or model loading at import time."""

import logging
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from time import monotonic

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import Settings
from .routes import admin, public
from .runtime import Runtime

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        settings.validate()
        runtime = Runtime(settings)
        app.state.runtime = runtime
        try:
            await runtime.start()
            yield
        finally:
            await runtime.close()

    app = FastAPI(title="Pastabar API", version="2.0.0", lifespan=lifespan)
    attempts = defaultdict(deque)

    @app.middleware("http")
    async def safety_headers(request: Request, call_next):
        # Single-process limiter. Multi-worker deployments should enforce this at
        # the edge or use shared Redis state; forwarded headers are NOT trusted here.
        if request.method == "POST" and request.url.path.startswith("/api"):
            now = monotonic()
            key = (request.client.host if request.client else "unknown", request.url.path)
            if len(attempts) > 10000:
                for old_key in list(attempts):
                    if not attempts[old_key] or attempts[old_key][-1] < now - 60:
                        del attempts[old_key]
            queue = attempts[key]
            while queue and queue[0] <= now - 60:
                queue.popleft()
            if len(queue) >= 10:
                return JSONResponse(
                    {"detail": "Too many requests; try again in one minute"},
                    status_code=429,
                    headers={"Retry-After": "60"},
                )
            queue.append(now)
            if request.url.path != "/api/admin/banner":
                try:
                    if int(request.headers.get("content-length", "0")) > 12 * 1024 * 1024:
                        return JSONResponse({"detail": "Request body too large"}, status_code=413)
                except ValueError:
                    return JSONResponse({"detail": "Invalid content length"}, status_code=400)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception):
        logger.error("Unhandled request error at %s", request.url.path, exc_info=error)
        return JSONResponse({"detail": "An internal error occurred; please try again"}, status_code=500)

    app.include_router(public.router)
    app.include_router(admin.router)
    uploads = settings.data_dir / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=uploads), name="uploads")
    # Existing menu image URLs remain valid after migrating images to DATA_DIR/uploads.
    app.mount("/static/images", StaticFiles(directory=uploads), name="legacy_images")
    if settings.static_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="frontend")
    return app
