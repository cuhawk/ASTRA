from __future__ import annotations

import time

import aiosqlite
import httpx

from backend.audit.events import RETENTION_S, emit, list_for_user
from backend.auth.sessions import create_session, make_signer, sign_sid
from backend.config import Settings


async def _seed_user(db: aiosqlite.Connection, login: str = "alice") -> int:
    await db.execute(
        "INSERT INTO users (github_id, github_login, email, created_at, last_login_at) "
        "VALUES (?, ?, NULL, strftime('%s','now'), strftime('%s','now'))",
        (hash(login) % 10_000_000, login),
    )
    await db.commit()
    cur = await db.execute(
        "SELECT id FROM users WHERE github_login = ?", (login,)
    )
    row = await cur.fetchone()
    await cur.close()
    return int(row["id"])


async def _authed(
    client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> int:
    uid = await _seed_user(db)
    sess = await create_session(db, uid, settings.session_max_age_s)
    await db.commit()
    signer = make_signer(settings.session_secret)
    client.cookies.set(settings.session_cookie_name, sign_sid(signer, sess.id))
    return uid


async def test_emit_roundtrip(db: aiosqlite.Connection) -> None:
    uid = await _seed_user(db)
    await emit(
        db,
        user_id=uid,
        action="run.created",
        entity="run",
        entity_id="abc123",
        payload={"url": "http://x/"},
    )
    events = await list_for_user(db, uid)
    assert len(events) == 1
    e = events[0]
    assert e.action == "run.created"
    assert e.entity == "run"
    assert e.entity_id == "abc123"
    assert e.payload == {"url": "http://x/"}


async def test_emit_payload_optional(db: aiosqlite.Connection) -> None:
    uid = await _seed_user(db)
    await emit(db, user_id=uid, action="auth.login", entity="session")
    events = await list_for_user(db, uid)
    assert events[0].payload is None
    assert events[0].entity_id is None


async def test_list_orders_newest_first(db: aiosqlite.Connection) -> None:
    uid = await _seed_user(db)
    for i in range(5):
        await emit(db, user_id=uid, action=f"e{i}", entity="run")
    events = await list_for_user(db, uid)
    assert [e.action for e in events] == ["e4", "e3", "e2", "e1", "e0"]


async def test_list_isolates_user(db: aiosqlite.Connection) -> None:
    u1 = await _seed_user(db, "a")
    u2 = await _seed_user(db, "b")
    await emit(db, user_id=u1, action="run.created", entity="run")
    await emit(db, user_id=u2, action="run.created", entity="run")
    e1 = await list_for_user(db, u1)
    e2 = await list_for_user(db, u2)
    assert len(e1) == 1 and len(e2) == 1
    assert e1[0].user_id == u1
    assert e2[0].user_id == u2


async def test_retention_sweeps_old_rows(db: aiosqlite.Connection) -> None:
    uid = await _seed_user(db)
    old = int(time.time()) - RETENTION_S - 60
    await db.execute(
        "INSERT INTO audit_events (user_id, action, entity, entity_id, payload, at) "
        "VALUES (?, 'stale', 'run', NULL, NULL, ?)",
        (uid, old),
    )
    await db.commit()
    # Next emit triggers the lazy cleanup.
    await emit(db, user_id=uid, action="fresh", entity="run")
    events = await list_for_user(db, uid)
    assert [e.action for e in events] == ["fresh"]


async def test_activity_endpoint_returns_list(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    uid = await _authed(app_client, db, settings)
    await emit(db, user_id=uid, action="run.created", entity="run", entity_id="r1")
    r = await app_client.get("/activity")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["action"] == "run.created"


async def test_activity_endpoint_unauthed_401(
    app_client: httpx.AsyncClient,
) -> None:
    r = await app_client.get("/activity")
    assert r.status_code == 401


async def test_activity_respects_limit(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    uid = await _authed(app_client, db, settings)
    for i in range(10):
        await emit(db, user_id=uid, action=f"e{i}", entity="run")
    r = await app_client.get("/activity?limit=3")
    assert r.status_code == 200
    assert len(r.json()) == 3


async def test_run_create_emits_event(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    uid = await _authed(app_client, db, settings)
    r = await app_client.post("/runs", json={"url": "http://example.invalid/"})
    assert r.status_code == 202
    events = await list_for_user(db, uid)
    actions = {e.action for e in events}
    assert "run.created" in actions


async def test_run_delete_emits_event(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    uid = await _authed(app_client, db, settings)
    r = await app_client.post("/runs", json={"url": "http://example.invalid/"})
    rid = r.json()["id"]
    d = await app_client.delete(f"/runs/{rid}")
    assert d.status_code == 204
    events = await list_for_user(db, uid)
    actions = [e.action for e in events]
    assert actions[0] == "run.deleted"
