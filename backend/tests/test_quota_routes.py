from __future__ import annotations

import aiosqlite
import httpx

from backend.auth.sessions import create_session, make_signer, sign_sid
from backend.config import Settings


async def _make_authed_client(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> int:
    await db.execute(
        "INSERT INTO users (github_id, github_login, email, created_at, last_login_at) "
        "VALUES (?, ?, ?, strftime('%s', 'now'), strftime('%s', 'now'))",
        (123, "alice", "a@example.com"),
    )
    await db.commit()
    cur = await db.execute("SELECT id FROM users WHERE github_id = 123")
    row = await cur.fetchone()
    await cur.close()
    user_id = int(row["id"])
    sess = await create_session(db, user_id, settings.session_max_age_s)
    signer = make_signer(settings.session_secret)
    app_client.cookies.set(settings.session_cookie_name, sign_sid(signer, sess.id))
    return user_id


async def test_probe_quota_unauthed_401(app_client: httpx.AsyncClient) -> None:
    resp = await app_client.get("/probe/quota")
    assert resp.status_code == 401


async def test_probe_quota_authed_increments(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    await _make_authed_client(app_client, db, settings)
    resp = await app_client.get("/probe/quota")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"used": 1, "remaining": 99, "limit": 100}
    resp = await app_client.get("/probe/quota")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"used": 2, "remaining": 98, "limit": 100}


async def test_probe_quota_hits_limit(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    await _make_authed_client(app_client, db, settings)
    # Shrink the live app's limit so we can hit it in two calls.
    app_client._transport.app.state.settings.free_tier_daily_limit = 2  # type: ignore[attr-defined]
    r1 = await app_client.get("/probe/quota")
    assert r1.status_code == 200
    r2 = await app_client.get("/probe/quota")
    assert r2.status_code == 200
    r3 = await app_client.get("/probe/quota")
    assert r3.status_code == 429


async def test_audit_log_written(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    user_id = await _make_authed_client(app_client, db, settings)
    resp = await app_client.get("/probe/quota")
    assert resp.status_code == 200
    cur = await db.execute(
        "SELECT user_id, delta, reason FROM audit_quota WHERE user_id = ?",
        (user_id,),
    )
    rows = await cur.fetchall()
    await cur.close()
    assert len(rows) == 1
    assert rows[0]["delta"] == 1
    assert rows[0]["reason"] == "probe"
