"""User-visible activity log.

Writes to `audit_events`. Cleanup is lazy: each `emit` deletes rows older than
`RETENTION_S` for the same user. This keeps the table bounded without a
background worker. Returns the inserted row id (mainly for tests).

Schema (see backend/db/schema.sql):
    id, user_id, action, entity, entity_id, payload, at
"""
from __future__ import annotations

import json
import time
from typing import Any

import aiosqlite
from pydantic import BaseModel

RETENTION_S = 7 * 24 * 60 * 60


class ActivityEvent(BaseModel):
    id: int
    user_id: int
    action: str
    entity: str
    entity_id: str | None
    payload: dict[str, Any] | None
    at: int


async def emit(
    db: aiosqlite.Connection,
    *,
    user_id: int,
    action: str,
    entity: str,
    entity_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> int:
    now = int(time.time())
    cur = await db.execute(
        "INSERT INTO audit_events (user_id, action, entity, entity_id, payload, at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            user_id,
            action,
            entity,
            entity_id,
            json.dumps(payload) if payload is not None else None,
            now,
        ),
    )
    rowid = cur.lastrowid
    await cur.close()
    cutoff = now - RETENTION_S
    await db.execute(
        "DELETE FROM audit_events WHERE user_id = ? AND at < ?", (user_id, cutoff)
    )
    await db.commit()
    return int(rowid or 0)


async def list_for_user(
    db: aiosqlite.Connection, user_id: int, *, limit: int = 50
) -> list[ActivityEvent]:
    cur = await db.execute(
        "SELECT id, user_id, action, entity, entity_id, payload, at "
        "FROM audit_events WHERE user_id = ? ORDER BY at DESC, id DESC LIMIT ?",
        (user_id, limit),
    )
    rows = await cur.fetchall()
    await cur.close()
    out: list[ActivityEvent] = []
    for r in rows:
        d = dict(r)
        if d.get("payload"):
            try:
                d["payload"] = json.loads(d["payload"])
            except json.JSONDecodeError:
                d["payload"] = None
        else:
            d["payload"] = None
        out.append(ActivityEvent(**d))
    return out
