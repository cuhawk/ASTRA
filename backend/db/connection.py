from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import aiosqlite

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


async def init_db(db_path: str) -> None:
    schema = _SCHEMA_PATH.read_text()
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(schema)
        await conn.commit()


async def connect(db_path: str) -> aiosqlite.Connection:
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON")
    return conn


async def get_db_dep(db_path: str) -> AsyncIterator[aiosqlite.Connection]:
    conn = await connect(db_path)
    try:
        yield conn
    finally:
        await conn.close()
