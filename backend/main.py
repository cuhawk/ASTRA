from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI

from backend.config import Settings, get_settings
from backend.db.connection import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    await init_db(settings.db_path)
    app.state.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield
    finally:
        await app.state.redis.aclose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="ASTRA", lifespan=lifespan)
    app.state.settings = settings

    from backend.auth.routes import router as auth_router
    from backend.coverage.routes import router as coverage_router
    from backend.llm.routes import router as llm_router
    from backend.quota.routes import router as quota_router
    from backend.runs.routes import router as runs_router
    from backend.runs.worker import make_executor

    app.include_router(auth_router)
    app.include_router(quota_router)
    app.include_router(llm_router)
    app.include_router(runs_router)
    app.include_router(coverage_router)

    app.state.run_executor = make_executor(settings)

    @app.get("/healthz")
    async def healthz() -> dict[str, bool]:
        return {"ok": True}

    return app
