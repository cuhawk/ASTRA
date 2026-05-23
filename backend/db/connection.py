from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import aiosqlite

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


_LLM_TRANSCRIPT_COLS = ("prompt_text", "response_text")
_LLM_INT_COLS = ("cached_prompt_tokens",)


async def _ensure_llm_transcript_cols(conn: aiosqlite.Connection) -> None:
    cur = await conn.execute("PRAGMA table_info(audit_llm_calls)")
    rows = await cur.fetchall()
    await cur.close()
    existing = {r[1] for r in rows}
    for col in _LLM_TRANSCRIPT_COLS:
        if col not in existing:
            await conn.execute(
                f"ALTER TABLE audit_llm_calls ADD COLUMN {col} TEXT"
            )
    for col in _LLM_INT_COLS:
        if col not in existing:
            await conn.execute(
                f"ALTER TABLE audit_llm_calls ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0"
            )


async def init_db(db_path: str) -> None:
    schema = _SCHEMA_PATH.read_text()
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(schema)
        await _ensure_llm_transcript_cols(conn)
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
