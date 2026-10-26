"""App entry point: `uvicorn steep.main:app`."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, api, db, fetcher, scheduler
from .config import get_settings
from .events import broadcaster

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("steep")

CSP = (
    "default-src 'self'; "
    "img-src * data: blob:; media-src *; "
    "style-src 'self' 'unsafe-inline'; font-src 'self'; script-src 'self'; "
    "connect-src 'self'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'self'"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    db.migrate()
    broadcaster.bind(asyncio.get_running_loop())
    if not __import__("os").environ.get("STEEP_PASSWORD"):
        log.warning("STEEP_PASSWORD is not set. A generated password is in %s", s.data_dir / "initial_password.txt")
    if not __import__("os").environ.get("STEEP_DISABLE_SCHEDULER"):
        scheduler.start()
    log.info("Steep %s ready; data in %s", __version__, s.data_dir)
    try:
        yield
    finally:
        scheduler.stop()
        await fetcher.close_client()


def create_app() -> FastAPI:
    app = FastAPI(title="Steep", version=__version__, lifespan=lifespan, docs_url=None, redoc_url=None)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", CSP)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        with db.connect() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"ok": True, "version": __version__}

    app.include_router(api.public)
    app.include_router(api.router)

    @app.exception_handler(404)
    async def not_found(request: Request, exc):
        if request.url.path.startswith("/api/"):
            detail = getattr(exc, "detail", "Not found")
            return JSONResponse({"detail": detail}, status_code=404)
        return _spa_index() or JSONResponse({"detail": "Not found"}, status_code=404)

    static = get_settings().static_dir
    if static and static.exists():
        assets = static / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            candidate = (static / path).resolve()
            if path and candidate.is_file() and static.resolve() in candidate.parents:
                return FileResponse(candidate)
            return _spa_index()

    return app


def _spa_index():
    static = get_settings().static_dir
    if static and (static / "index.html").exists():
        return FileResponse(static / "index.html", headers={"Cache-Control": "no-cache"})
    return None


app = create_app()
