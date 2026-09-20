"""App factory, lifespan, health, static mounts, router stubs, and the three sockets.

Step 0 owns this file. Lanes replace the socket bodies in app/ingest and fill their own routers.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request, WebSocket
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import (
    assets,
    close,
    corrections,
    events,
    journal,
    metrics,
    review,
    rules,
    settings,
    setup,
    sim,
)
from app.config import APP_VERSION, REPO_DIR, Settings, get_settings
from app.db import dispose_db, init_db, session_scope, table_names
from app.ingest import bin_socket, phone_socket, ui_socket
from app.ingest.state import build_state
from app.models import ALL_TABLES
from app.pipeline import build_default_pipeline
from app.schemas import BrandInfo, HealthResponse

log = logging.getLogger(__name__)

PHONE_DIR = REPO_DIR / "phone"
BRAND_FILE = REPO_DIR / "brand.json"

# Every way of naming this laptop or something on its hotspot, and nothing else. `localhost`
# and `127.0.0.1` are the same machine by two names, and `[::1]` is the same machine again:
# which one a browser picks is the browser's business, so all three are here.
CORS_ORIGIN_PATTERN = r"https?://(localhost|127\.0\.0\.1|\[::1\]|[0-9.]+)(:\d+)?"


def setup_logging() -> None:
    """Give the structured lines somewhere to go.

    Every stage of the pipeline logs one line at INFO, and nothing in the stack configures
    the root logger, so without this the only lines anyone ever sees are warnings. It runs
    once and never takes a handler off something that already set one up.
    """
    if logging.getLogger().handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s %(message)s",
    )


def seed_when_empty(active: Settings) -> None:
    """Load the seed files on a first start, so a fresh database is never a blank demo.

    The seed script lives beside the backend rather than inside it, so the repo root goes
    on the path first. A seed that cannot run is logged and the app still starts: an empty
    catalog is a visible problem on the setup page, not a reason to refuse to boot.
    """
    if not active.seed_on_start:
        return
    if str(REPO_DIR) not in sys.path:
        sys.path.insert(0, str(REPO_DIR))
    try:
        from scripts.seed_db import is_empty, seed_all
    except ImportError:
        log.warning("the seed script is not importable, the database was left as it is")
        return
    try:
        with session_scope() as session:
            if not is_empty(session):
                return
            summary = seed_all(session)
        log.info(
            "seeded a fresh database: %d rows in, %d waiting on a person",
            summary.inserted,
            summary.skipped,
        )
        for row in summary.skipped_rows:
            log.warning("seed row skipped: %s", row)
    except Exception:
        log.exception("the seed files could not be loaded")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    active: Settings = app.state.settings
    setup_logging()
    active.media_dir.mkdir(parents=True, exist_ok=True)
    init_db(active)
    log.info("database ready with %d tables", len(table_names()))
    seed_when_empty(active)
    app.state.ingest = build_state(active)
    # The one place every lane meets. It owns both seams: ingest to identification, and
    # identification to the engine, the ledger and the three surfaces.
    app.state.pipeline = build_default_pipeline(active)
    app.state.pipeline.attach(app.state.ingest)
    try:
        yield
    finally:
        app.state.ingest.close()
        app.state.ingest = None
        app.state.pipeline = None
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


# The two addresses a person can be at. The backend itself is neither of them.
PHONE_PATH = "/phone/"
LAPTOP_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "[::1]"})


def _is_laptop(request: Request) -> bool:
    """Is this the machine running the demo, or something on the hotspot?

    Anything that is not the loopback name reached the backend over the network, which on
    this build means a phone, because the phone is the only thing on the hotspot.
    """
    host = (request.headers.get("host") or "").rsplit(":", 1)[0].strip().lower()
    return host in LAPTOP_HOSTS


def _front_door(app: FastAPI, active: Settings) -> None:
    """The backend's own address is not a page. Send whoever asked to the one they wanted."""

    @app.get("/", include_in_schema=False)
    def root(request: Request) -> RedirectResponse:
        target = active.dashboard_url if _is_laptop(request) else PHONE_PATH
        return RedirectResponse(url=target, status_code=307)

    @app.exception_handler(StarletteHTTPException)
    def http_error(request: Request, error: Exception) -> JSONResponse:
        """Say where the two pages are rather than the framework's bare "Not Found".

        Only for an address that matched no route. A route that answers 404 has already
        said something better than this, such as which event does not exist, and replacing
        that with a signpost would lose it.
        """
        assert isinstance(error, StarletteHTTPException)
        detail = error.detail
        code = "error"
        if error.status_code == 404 and request.scope.get("route") is None:
            detail = (
                "Nothing lives at this address. The dashboard is at "
                f"{active.dashboard_url} and the phone page is at /phone."
            )
            code = "not_found"
        return JSONResponse(
            status_code=error.status_code,
            content={"detail": detail, "code": code},
            headers=getattr(error, "headers", None),
        )


def _sockets(app: FastAPI) -> None:
    """The three sockets. Every body is one call into app.ingest, which owns the rest."""

    @app.websocket("/ws/bin")
    async def ws_bin(websocket: WebSocket) -> None:
        await bin_socket.serve(websocket)

    @app.websocket("/ws/phone")
    async def ws_phone(websocket: WebSocket) -> None:
        await phone_socket.serve(websocket)

    @app.websocket("/ws/ui")
    async def ws_ui(websocket: WebSocket) -> None:
        await ui_socket.serve(websocket)


# What a refused request says back. DESIGN.md section 8: say what happened and what to do.
# The default body repeats every rejected field verbatim, which hands a hostile string
# straight back to whatever renders the error, and says nothing a person can act on.
REFUSED_DETAIL = "That is not something this field accepts. Check the value and try again."


def _refuse_quietly(request: Request, error: RequestValidationError) -> JSONResponse:
    """Refuse a bad request without echoing what was sent.

    The full reason goes to the log, where an engineer can read it. What goes back on the
    wire is one sentence, because the request body may hold anything at all and the
    dashboard and the phone both draw whatever comes back.
    """
    log.warning("refused %s %s: %s", request.method, request.url.path, error.errors())
    return JSONResponse(status_code=422, content={"detail": REFUSED_DETAIL})


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
    app.add_exception_handler(RequestValidationError, _refuse_quietly)  # type: ignore[arg-type]

    # The dashboard runs on its own port in development and on the same origin in the demo.
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=CORS_ORIGIN_PATTERN,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(_health_router(conf))
    app.include_router(events.router)
    app.include_router(corrections.router)
    app.include_router(assets.router)
    app.include_router(journal.router)
    app.include_router(rules.router)
    app.include_router(metrics.router)
    app.include_router(close.router)
    app.include_router(review.router)
    app.include_router(settings.router)
    app.include_router(setup.router)
    if conf.dev_tools:
        app.include_router(sim.router)

    _brand_route(app, conf)
    _front_door(app, conf)
    _sockets(app)

    conf.media_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=conf.media_dir), name="media")
    if PHONE_DIR.is_dir():
        app.mount("/phone", StaticFiles(directory=PHONE_DIR, html=True), name="phone")

    return app


app = create_app()
