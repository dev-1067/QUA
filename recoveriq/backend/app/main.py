from __future__ import annotations

import asyncio
import logging
import time
import uuid

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import clock
from .config import STATIC_DIR, settings
from .db import SessionLocal, engine, init_db, write_session
from .domain import rules as rulebook
from .models import User
from .realtime import hub
from .security import decode_token

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("recoveriq")


class _DropClientResets(logging.Filter):
    """Windows' proactor loop logs a traceback whenever a browser drops a keep-alive socket.
    It is harmless noise, so hide just that case."""
    def filter(self, record: logging.LogRecord) -> bool:
        exc = record.exc_info[1] if record.exc_info else None
        return not isinstance(exc, (ConnectionResetError, ConnectionAbortedError))


logging.getLogger("asyncio").addFilter(_DropClientResets())

app = FastAPI(title="RecoverIQ API", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json",
              description="AI-powered debt collections platform: QUASAR 5.0 PS-01 prototype")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def request_id(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    request.state.request_id = rid
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["x-request-id"] = rid
    response.headers["x-response-time-ms"] = f"{(time.perf_counter() - start) * 1000:.1f}"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


def _err(request: Request, status: int, code: str, message):
    rid = getattr(request.state, "request_id", None)
    msg = message if isinstance(message, str) else "Validation failed"
    return JSONResponse({"error": {"code": code, "message": msg, "request_id": rid}, "detail": message},
                        status_code=status)


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    return _err(request, exc.status_code, f"http_{exc.status_code}", exc.detail)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    loc = ".".join(str(p) for p in first.get("loc", [])[1:])
    return _err(request, 422, "validation_error", f"{loc}: {first.get('msg', 'invalid')}" if loc else first.get("msg", "invalid"))


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error on %s", request.url.path)
    return _err(request, 500, "internal_error", "Something went wrong on the server. It has been logged.")


from .api import admin, agent, allocation, auth, cases, dashboards, intake, payments  # noqa: E402

for r in (auth.router, cases.router, agent.router, intake.router, allocation.router, payments.router,
          dashboards.router, admin.router):
    app.include_router(r, prefix="/api/v1")


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}


@app.get("/api/v1/ready")
def ready():
    with engine.connect() as c:
        c.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.websocket("/api/v1/ws")
async def ws(websocket: WebSocket, token: str):
    try:
        data = decode_token(token)
    except Exception:
        await websocket.close(code=4401)
        return
    db = SessionLocal()
    try:
        user = db.get(User, data["sub"])
        scope = {"user_id": user.id, "role": user.role, "branch_id": user.branch_id, "region_id": user.region_id}
    finally:
        db.close()
    await hub.connect(websocket, scope)
    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(websocket)


# ------------------------------------------------------------------ background jobs

async def scheduler():
    from .api.payments import reconcile
    from .services import break_due_promises
    tick = 0
    while True:
        await asyncio.sleep(60)
        tick += 1
        try:
            def ptp():
                with write_session() as db:
                    n = break_due_promises(db)
                    if n:
                        log.info("PTP scheduler: %d promises broken", n)
            await asyncio.to_thread(ptp)
            if tick % 10 == 0:  # every 10 minutes catch webhooks the gateway never delivered
                def rec():
                    with write_session() as db:
                        r = reconcile(db)
                        if r["posted"]:
                            log.info("Reconciliation posted %d payments", r["posted"])
                await asyncio.to_thread(rec)
        except Exception:
            log.exception("Scheduler tick failed")


@app.on_event("startup")
async def startup():
    hub.loop = asyncio.get_running_loop()
    init_db()
    from .seed import ensure_seeded
    await asyncio.to_thread(ensure_seeded)
    db = SessionLocal()
    try:
        clock.set_offset(float(rulebook.get_setting(db, "clock_offset", 0.0) or 0.0))
    finally:
        db.close()
    asyncio.create_task(scheduler())
    log.info("RecoverIQ ready · gateway=%s · demo clock offset=%ss", settings.gateway, clock.get_offset())


# ------------------------------------------------------------------ web app (built SPA)

if (STATIC_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
async def spa(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    candidate = STATIC_DIR / full_path
    if full_path and candidate.is_file() and STATIC_DIR in candidate.resolve().parents:
        return FileResponse(candidate)
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
    return JSONResponse({"detail": "Web app not built yet. Run: npm run build (in /web)"}, status_code=503)
