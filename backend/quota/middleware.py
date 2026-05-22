from __future__ import annotations

import aiosqlite
from fastapi import HTTPException, Request, status

from backend.config import Settings
from backend.quota.counter import QuotaCounter, QuotaExceeded, write_audit


def get_quota_counter(request: Request) -> QuotaCounter:
    settings: Settings = request.app.state.settings
    return QuotaCounter(request.app.state.redis, settings.free_tier_daily_limit)


async def _open_request_db(request: Request) -> aiosqlite.Connection:
    settings: Settings = request.app.state.settings
    conn = await aiosqlite.connect(settings.db_path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON")
    return conn


async def enforce_quota(
    *, user_id: int, reason: str, units: int, request: Request
) -> int:
    counter = get_quota_counter(request)
    try:
        new_used = await counter.deduct(user_id, units, reason)
    except QuotaExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="quota exceeded"
        ) from exc
    db = await _open_request_db(request)
    try:
        await write_audit(db, user_id, units, reason)
        await db.commit()
    finally:
        await db.close()
    return new_used
