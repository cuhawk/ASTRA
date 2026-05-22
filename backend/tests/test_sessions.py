from __future__ import annotations

import aiosqlite

from backend.auth.oauth import GitHubUser
from backend.auth.sessions import (
    _now,
    create_session,
    delete_session,
    get_session,
    make_signer,
    new_sid,
    sign_sid,
    upsert_github_user,
    verify_signed,
)
from backend.config import Settings


def test_signer_roundtrip(settings: Settings) -> None:
    signer = make_signer(settings.session_secret)
    sid = new_sid()
    signed = sign_sid(signer, sid)
    assert verify_signed(signer, signed) == sid
    assert verify_signed(signer, signed + "x") is None
    assert verify_signed(signer, "garbage") is None


def test_new_sid_is_random_and_urlsafe() -> None:
    a, b = new_sid(), new_sid()
    assert a != b
    assert "=" not in a
    assert "/" not in a
    assert "+" not in a


async def _make_user(db: aiosqlite.Connection, github_id: int = 1) -> int:
    return await upsert_github_user(
        db, GitHubUser(id=github_id, login="octo", email="o@example.com")
    )


async def test_create_get_delete_session(
    db: aiosqlite.Connection, settings: Settings
) -> None:
    user_id = await _make_user(db)
    session = await create_session(db, user_id, settings.session_max_age_s)
    fetched = await get_session(db, session.id)
    assert fetched is not None
    assert fetched.user_id == user_id
    await delete_session(db, session.id)
    assert await get_session(db, session.id) is None


async def test_get_session_expired_returns_none(db: aiosqlite.Connection) -> None:
    user_id = await _make_user(db)
    now = _now()
    sid = new_sid()
    await db.execute(
        "INSERT INTO sessions (id, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (sid, user_id, now - 7200, now - 3600),
    )
    await db.commit()
    assert await get_session(db, sid) is None


async def test_upsert_github_user_inserts_then_updates(db: aiosqlite.Connection) -> None:
    uid1 = await upsert_github_user(
        db, GitHubUser(id=123, login="octo", email="o@example.com")
    )
    uid2 = await upsert_github_user(
        db, GitHubUser(id=123, login="octo2", email="o2@example.com")
    )
    assert uid1 == uid2
    cur = await db.execute(
        "SELECT github_login, email FROM users WHERE id = ?", (uid1,)
    )
    row = await cur.fetchone()
    await cur.close()
    assert row["github_login"] == "octo2"
    assert row["email"] == "o2@example.com"

    cur = await db.execute("SELECT COUNT(*) AS c FROM users")
    row = await cur.fetchone()
    await cur.close()
    assert row["c"] == 1
