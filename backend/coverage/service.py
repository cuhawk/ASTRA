from __future__ import annotations

import secrets
import time
from typing import Literal

import aiosqlite
from pydantic import BaseModel

Status = Literal["pending", "recording", "done", "failed"]


class FeatureRecord(BaseModel):
    id: str
    run_id: str
    name: str
    created_at: int
    last_run_at: int | None = None
    last_status: Status | None = None
    error: str | None = None
    matched_functions: int = 0


def new_feature_id() -> str:
    return secrets.token_hex(6)


async def create_feature(
    db: aiosqlite.Connection, *, run_id: str, name: str
) -> FeatureRecord:
    fid = new_feature_id()
    now = int(time.time())
    await db.execute(
        "INSERT INTO features (id, run_id, name, created_at) VALUES (?, ?, ?, ?)",
        (fid, run_id, name, now),
    )
    await db.commit()
    return FeatureRecord(id=fid, run_id=run_id, name=name, created_at=now)


async def get_feature(
    db: aiosqlite.Connection, feature_id: str
) -> FeatureRecord | None:
    cur = await db.execute("SELECT * FROM features WHERE id = ?", (feature_id,))
    row = await cur.fetchone()
    return FeatureRecord(**dict(row)) if row else None


async def list_features(db: aiosqlite.Connection, run_id: str) -> list[FeatureRecord]:
    cur = await db.execute(
        "SELECT * FROM features WHERE run_id = ? ORDER BY created_at DESC", (run_id,)
    )
    rows = await cur.fetchall()
    return [FeatureRecord(**dict(r)) for r in rows]


async def set_status(
    db: aiosqlite.Connection,
    feature_id: str,
    status: Status,
    *,
    error: str | None = None,
) -> None:
    now = int(time.time())
    await db.execute(
        "UPDATE features SET last_status = ?, last_run_at = ?, error = ? WHERE id = ?",
        (status, now, error, feature_id),
    )
    await db.commit()


async def write_matched(
    db: aiosqlite.Connection, feature_id: str, matched: int
) -> None:
    await db.execute(
        "UPDATE features SET matched_functions = ? WHERE id = ?",
        (matched, feature_id),
    )
    await db.commit()
