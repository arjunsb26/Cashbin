"""App factory, lifespan, health, static mounts, router stubs, and the three sockets.

Step 0 owns this file. Lanes replace the socket bodies in app/ingest and fill their own routers.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from app.api import assets, close, corrections, events, journal, metrics, settings, sim
from app.config import APP_VERSION, REPO_DIR, Settings, get_settings
from app.db import dispose_db, init_db, table_names
from app.models import ALL_TABLES
from app.notify.bus import CHANNEL_PHONE, CHANNEL_UI, get_bus
from app.schemas import (
    BinHello,
    BrandInfo,
    HealthResponse,
    PhoneHello,
)

log = logging.getLogger(__name__)

PHONE_DIR = REPO_DIR / "phone"
BRAND_FILE = REPO_DIR / "brand.json"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    active: Settings = app.state.settings
    active.media_dir.mkdir(parents=True, exist_ok=True)
    init_db(active)
    log.info("database ready with %d tables", len(table_names()))
    try:
        yield
    finally:
        dispose_db()


def _health_router(active: Settings) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["health"])

    @router.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        present = set(table_names())
        db_ok = set(ALL_TABLES).issubset(present)
        return HealthResponse(
            status="ok" if db_ok else "degraded",
            version=APP_VERSION,
            db=db_ok,
            product_name=active.product_name,
        )

    return router


def _brand_route(app: FastAPI, active: Settings) -> None:
    @app.get("/brand.json", include_in_schema=False)
    def brand() -> JSONResponse:
        """The phone page and the dashboard both read the product name from here."""
        info = BrandInfo(
            name=active.product_name,
            short_name=active.product_short_name,
            tagline=active.product_tagline,
        )
        return JSONResponse(
            content=info.model_dump(),
            headers={"Cache-Control": "no-store"},
        )


def _sockets(app: FastAPI) -> None:
    """Accept, check the hello, answer ping and pong. Lanes A and E add the real handling."""
    bus = get_bus()

    @app.websocket("/ws/bin")
    async def ws_bin(websocket: WebSocket) -> None:
        await websocket.accept()
        greeted = False
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    await websocket.send_json({"type": "error", "detail": "not json"})
                    continue
                kind = message.get("type") if isinstance(message, dict) else None
                if kind == "hello":
                    try:
                        BinHello.model_validate(message)
                    except ValidationError:
                        await websocket.close(code=1008)
                        return
                    greeted = True
                    await websocket.send_json({"type": "ping"})
                elif not greeted:
                    await websocket.close(code=1008)
                    return
                elif kind in {"ping", "pong"}:
                    await websocket.send_json({"type": "pong" if kind == "ping" else "ping"})
        except WebSocketDisconnect:
            return

    @app.websocket("/ws/phone")
    async def ws_phone(websocket: WebSocket) -> None:
        await websocket.accept()
        greeted = False
        subscription = bus.subscribe(CHANNEL_PHONE)
        try:
            while True:
                packet = await websocket.receive()
                if packet.get("type") == "websocket.disconnect":
                    return
                raw = packet.get("text")
                if raw is None:
                    # Binary frames are JPEG bytes. Lane A gives them a ring buffer.
                    continue
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                kind = message.get("type") if isinstance(message, dict) else None
                if kind == "hello":
                    try:
                        PhoneHello.model_validate(message)
                    except ValidationError:
                        await websocket.close(code=1008)
                        return
                    greeted = True
                    await websocket.send_json({"type": "ping"})
                elif not greeted:
                    await websocket.close(code=1008)
                    return
                elif kind in {"ping", "pong"}:
                    await websocket.send_json({"type": "pong" if kind == "ping" else "ping"})
        except WebSocketDisconnect:
            return
        finally:
            subscription.close()

    @app.websocket("/ws/ui")
    async def ws_ui(websocket: WebSocket) -> None:
        await websocket.accept()
        subscription = bus.subscribe(CHANNEL_UI)
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                kind = message.get("type") if isinstance(message, dict) else None
                if kind in {"ping", "pong"}:
                    await websocket.send_json({"type": "pong" if kind == "ping" else "ping"})
        except WebSocketDisconnect:
            return
        finally:
            subscription.close()


def create_app(active: Settings | None = None) -> FastAPI:
    """Build the app. Pass settings in tests so each case gets its own database file."""
    conf = active or get_settings()
    app = FastAPI(
        title=conf.product_name,
        version=APP_VERSION,
        lifespan=lifespan,
        docs_url="/api/docs" if conf.dev_tools else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if conf.dev_tools else None,
    )
    app.state.settings = conf

    # The dashboard runs on its own port in development and on the same origin in the demo.
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|\[::1\]|[0-9.]+)(:\d+)?",
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(_health_router(conf))
    app.include_router(events.router)
    app.include_router(corrections.router)
    app.include_router(assets.router)
    app.include_router(journal.router)
    app.include_router(metrics.router)
    app.include_router(close.router)
    app.include_router(settings.router)
    if conf.dev_tools:
        app.include_router(sim.router)

    _brand_route(app, conf)
    _sockets(app)

    conf.media_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=conf.media_dir), name="media")
    if PHONE_DIR.is_dir():
        app.mount("/phone", StaticFiles(directory=PHONE_DIR, html=True), name="phone")

    return app


app = create_app()
