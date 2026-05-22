from __future__ import annotations

import secrets
from collections.abc import AsyncIterator
from pathlib import Path

import aiosqlite
import fakeredis.aioredis as fakeredis
import httpx
import pytest

from backend.config import Settings
from backend.db.connection import init_db
from backend.main import create_app


@pytest.fixture
def vault_kek_hex() -> str:
    return secrets.token_hex(32)


@pytest.fixture
def settings(tmp_path: Path, vault_kek_hex: str) -> Settings:
    return Settings(
        db_path=str(tmp_path / "astra.db"),
        redis_url="redis://test/0",
        session_secret=secrets.token_hex(32),
        github_client_id="test-client-id",
        github_client_secret="test-client-secret",
        github_redirect_uri="http://127.0.0.1:8000/auth/github/callback",
        vault_kek_hex=vault_kek_hex,
        base_url="http://127.0.0.1:8000",
        session_cookie_secure=False,
    )


@pytest.fixture
async def db(settings: Settings) -> AsyncIterator[aiosqlite.Connection]:
    await init_db(settings.db_path)
    conn = await aiosqlite.connect(settings.db_path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        await conn.close()


@pytest.fixture
async def fake_redis() -> AsyncIterator[fakeredis.FakeRedis]:
    client = fakeredis.FakeRedis(decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
async def app_client(
    settings: Settings, fake_redis: fakeredis.FakeRedis
) -> AsyncIterator[httpx.AsyncClient]:
    await init_db(settings.db_path)
    app = create_app(settings=settings)
    app.state.redis = fake_redis
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        yield client
