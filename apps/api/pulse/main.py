"""FastAPI entry point: `uvicorn pulse.main:app`."""

import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request, Response

from pulse import __version__, bot, seed, sync
from pulse.api import router
from pulse.core import db, visitor
from pulse.core.config import get_settings
from pulse.modules import knowledge

KINDS = (
    "user",
    "company",
    "deal",
    "lead",
    "call",
    "task",
    "stage_change",
    "erp_sale",
    "erp_payment",
    "erp_stock",
    "erp_order",
)


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await sync.ensure_ready()
    knowledge.ensure_index()
    worker = asyncio.create_task(sync.loop())
    hook = asyncio.create_task(bot.setup_webhook())
    try:
        yield
    finally:
        worker.cancel()
        hook.cancel()


app = FastAPI(
    title="Pulse", version=__version__, docs_url="/api/swagger", openapi_url="/api/openapi.json", lifespan=lifespan
)
app.include_router(router)


@app.middleware("http")
async def session_cookie(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """A first-time visitor gets a session id; the same request already uses it (see `core.visitor`)."""
    visitor.assign(request)
    response = await call_next(request)
    visitor.ensure_cookie(request, response)
    return response


@app.get("/api/health")
def health() -> dict[str, Any]:
    settings = get_settings()
    return {"status": "ok", "version": __version__, "crm": settings.crm_mode, "erp": settings.erp_mode}


@app.get("/api/data/summary")
def summary() -> dict[str, Any]:
    """What is in the local store and when it was synced — the integrations screen reads this."""
    return {
        "counts": {k: db.count(k) for k in KINDS},
        "last_sync": db.get_setting("last_sync"),
        "seed_fresh": seed.is_fresh(),
        "log": db.recent_log(10),
    }


@app.post("/api/admin/reset")
async def admin_reset(x_admin_key: str = Header(default="")) -> dict[str, Any]:
    key = get_settings().admin_key
    if not key or x_admin_key != key:
        raise HTTPException(status_code=403, detail="Нужен X-Admin-Key")
    result = await sync.reset()
    return {"counts": result["counts"]}
