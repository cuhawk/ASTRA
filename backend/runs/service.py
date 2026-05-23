from __future__ import annotations

import secrets
import time
from typing import Literal

import aiosqlite
from pydantic import BaseModel

Status = Literal["pending", "acquiring", "analyzing", "done", "failed"]


class RunRecord(BaseModel):
    id: str
    user_id: int
    url: str | None
    status: Status
    error: str | None = None
    created_at: int
    started_at: int | None = None
    finished_at: int | None = None
    files: int = 0
    functions: int = 0
    edges: int = 0


def new_run_id() -> str:
    return secrets.token_hex(6)


async def create_run(
    db: aiosqlite.Connection, *, user_id: int, url: str | None
) -> RunRecord:
    rid = new_run_id()
    now = int(time.time())
    await db.execute(
        "INSERT INTO runs (id, user_id, url, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
        (rid, user_id, url, now),
    )
    await db.commit()
    return RunRecord(id=rid, user_id=user_id, url=url, status="pending", created_at=now)


async def get_run(
    db: aiosqlite.Connection, run_id: str, *, user_id: int | None = None
) -> RunRecord | None:
    sql = "SELECT * FROM runs WHERE id = ?"
    params: tuple = (run_id,)
    if user_id is not None:
        sql += " AND user_id = ?"
        params = (run_id, user_id)
    cur = await db.execute(sql, params)
    row = await cur.fetchone()
    await cur.close()
    if row is None:
        return None
    return RunRecord(**dict(row))


async def list_runs(
    db: aiosqlite.Connection, user_id: int, limit: int = 50
) -> list[RunRecord]:
    cur = await db.execute(
        "SELECT * FROM runs WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    )
    rows = await cur.fetchall()
    await cur.close()
    return [RunRecord(**dict(r)) for r in rows]


async def set_status(
    db: aiosqlite.Connection,
    run_id: str,
    status: Status,
    *,
    error: str | None = None,
) -> None:
    now = int(time.time())
    fields = ["status = ?"]
    params: list = [status]
    if status == "acquiring":
        fields.append("started_at = ?")
        params.append(now)
    if status in ("done", "failed"):
        fields.append("finished_at = ?")
        params.append(now)
    if error is not None:
        fields.append("error = ?")
        params.append(error)
    params.append(run_id)
    await db.execute(
        f"UPDATE runs SET {', '.join(fields)} WHERE id = ?", params
    )
    await db.commit()


async def delete_run(
    db: aiosqlite.Connection, run_id: str, *, user_id: int
) -> bool:
    cur = await db.execute(
        "DELETE FROM runs WHERE id = ? AND user_id = ?", (run_id, user_id)
    )
    await db.commit()
    deleted = cur.rowcount > 0
    await cur.close()
    return deleted


async def write_metrics(
    db: aiosqlite.Connection,
    run_id: str,
    *,
    files: int,
    functions: int,
    edges: int,
) -> None:
    await db.execute(
        "UPDATE runs SET files = ?, functions = ?, edges = ? WHERE id = ?",
        (files, functions, edges, run_id),
    )
    await db.commit()
