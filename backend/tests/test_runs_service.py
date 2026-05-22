from __future__ import annotations

import asyncio

import aiosqlite

from backend.runs.service import (
    create_run,
    get_run,
    list_runs,
    set_status,
    write_metrics,
)


async def _seed_user(db: aiosqlite.Connection, github_id: int = 100, login: str = "u") -> int:
    await db.execute(
        "INSERT INTO users (github_id, github_login, email, created_at, last_login_at) "
        "VALUES (?, ?, NULL, strftime('%s','now'), strftime('%s','now'))",
        (github_id, login),
    )
    await db.commit()
    cur = await db.execute("SELECT id FROM users WHERE github_id = ?", (github_id,))
    row = await cur.fetchone()
    await cur.close()
    return int(row["id"])


async def test_create_get(db: aiosqlite.Connection) -> None:
    uid = await _seed_user(db)
    rec = await create_run(db, user_id=uid, url="http://x/")
    got = await get_run(db, rec.id)
    assert got is not None
    assert got.id == rec.id
    assert got.user_id == uid
    assert got.url == "http://x/"
    assert got.status == "pending"
    assert got.files == 0
    assert got.functions == 0
    assert got.edges == 0


async def test_get_other_user_returns_none(db: aiosqlite.Connection) -> None:
    u1 = await _seed_user(db, github_id=1, login="a")
    u2 = await _seed_user(db, github_id=2, login="b")
    rec = await create_run(db, user_id=u1, url=None)
    assert await get_run(db, rec.id, user_id=u2) is None
    assert (await get_run(db, rec.id, user_id=u1)) is not None


async def test_set_status_transitions(db: aiosqlite.Connection) -> None:
    uid = await _seed_user(db)
    rec = await create_run(db, user_id=uid, url="http://x/")

    await set_status(db, rec.id, "acquiring")
    after_acq = await get_run(db, rec.id)
    assert after_acq is not None
    assert after_acq.status == "acquiring"
    assert after_acq.started_at is not None
    assert after_acq.finished_at is None

    await set_status(db, rec.id, "done")
    after_done = await get_run(db, rec.id)
    assert after_done is not None
    assert after_done.status == "done"
    assert after_done.started_at == after_acq.started_at
    assert after_done.finished_at is not None


async def test_set_status_failed_records_error(db: aiosqlite.Connection) -> None:
    uid = await _seed_user(db)
    rec = await create_run(db, user_id=uid, url=None)
    await set_status(db, rec.id, "failed", error="boom")
    got = await get_run(db, rec.id)
    assert got is not None
    assert got.status == "failed"
    assert got.error == "boom"
    assert got.finished_at is not None


async def test_write_metrics(db: aiosqlite.Connection) -> None:
    uid = await _seed_user(db)
    rec = await create_run(db, user_id=uid, url=None)
    await write_metrics(db, rec.id, files=4, functions=17, edges=23)
    got = await get_run(db, rec.id)
    assert got is not None
    assert got.files == 4
    assert got.functions == 17
    assert got.edges == 23


async def test_list_runs_ordered_by_created_at_desc(db: aiosqlite.Connection) -> None:
    uid = await _seed_user(db)
    r1 = await create_run(db, user_id=uid, url="http://1/")
    r2 = await create_run(db, user_id=uid, url="http://2/")
    r3 = await create_run(db, user_id=uid, url="http://3/")
    # Force ordering via direct created_at update; second-granularity is too coarse.
    await db.execute("UPDATE runs SET created_at = ? WHERE id = ?", (100, r1.id))
    await db.execute("UPDATE runs SET created_at = ? WHERE id = ?", (200, r2.id))
    await db.execute("UPDATE runs SET created_at = ? WHERE id = ?", (300, r3.id))
    await db.commit()

    items = await list_runs(db, uid)
    assert [r.id for r in items] == [r3.id, r2.id, r1.id]


async def test_list_runs_scopes_to_user(db: aiosqlite.Connection) -> None:
    u1 = await _seed_user(db, github_id=1, login="a")
    u2 = await _seed_user(db, github_id=2, login="b")
    await create_run(db, user_id=u1, url=None)
    await create_run(db, user_id=u2, url=None)
    rows_u1 = await list_runs(db, u1)
    assert len(rows_u1) == 1
    assert rows_u1[0].user_id == u1
