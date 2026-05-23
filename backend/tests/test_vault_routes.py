from __future__ import annotations

import aiosqlite
import httpx

from backend.auth.sessions import create_session, make_signer, sign_sid
from backend.config import Settings


async def _authed(
    client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> int:
    await db.execute(
        "INSERT INTO users (github_id, github_login, email, created_at, last_login_at) "
        "VALUES (1, 'alice', NULL, strftime('%s','now'), strftime('%s','now'))"
    )
    await db.commit()
    cur = await db.execute("SELECT id FROM users WHERE github_id = 1")
    uid = int((await cur.fetchone())["id"])
    await cur.close()
    sess = await create_session(db, uid, settings.session_max_age_s)
    await db.commit()
    signer = make_signer(settings.session_secret)
    client.cookies.set(settings.session_cookie_name, sign_sid(signer, sess.id))
    return uid


VALID_KEY = "sk-ant-" + "a" * 64


async def test_get_status_empty(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    await _authed(app_client, db, settings)
    r = await app_client.get("/vault/keys/anthropic")
    assert r.status_code == 200
    body = r.json()
    assert body == {"provider": "anthropic", "present": False, "updated_at": None}


async def test_put_then_get(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    await _authed(app_client, db, settings)
    r = await app_client.put("/vault/keys/anthropic", json={"key": VALID_KEY})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["present"] is True
    assert isinstance(body["updated_at"], int)

    g = await app_client.get("/vault/keys/anthropic")
    assert g.status_code == 200
    assert g.json()["present"] is True


async def test_put_rejects_bad_prefix(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    await _authed(app_client, db, settings)
    r = await app_client.put(
        "/vault/keys/anthropic", json={"key": "openai-xxxxxxxxxxxxxxxxxxxx"}
    )
    assert r.status_code == 422
    assert "sk-ant-" in r.json()["detail"]


async def test_put_rejects_short_key(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    await _authed(app_client, db, settings)
    r = await app_client.put("/vault/keys/anthropic", json={"key": "sk-ant-"})
    assert r.status_code == 422


async def test_unknown_provider_404(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    await _authed(app_client, db, settings)
    r = await app_client.get("/vault/keys/openai")
    assert r.status_code == 404


async def test_delete_clears_key(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    await _authed(app_client, db, settings)
    await app_client.put("/vault/keys/anthropic", json={"key": VALID_KEY})
    d = await app_client.delete("/vault/keys/anthropic")
    assert d.status_code == 204
    g = await app_client.get("/vault/keys/anthropic")
    assert g.json()["present"] is False


async def test_delete_missing_404(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    await _authed(app_client, db, settings)
    d = await app_client.delete("/vault/keys/anthropic")
    assert d.status_code == 404


async def test_put_replaces_existing(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    await _authed(app_client, db, settings)
    await app_client.put("/vault/keys/anthropic", json={"key": VALID_KEY})
    other = "sk-ant-" + "b" * 64
    r = await app_client.put("/vault/keys/anthropic", json={"key": other})
    assert r.status_code == 200
    # And the stored key really is the second one — round-trip via KeyVault.
    from backend.vault.envelope import KeyVault

    cur = await db.execute("SELECT id FROM users LIMIT 1")
    uid = int((await cur.fetchone())["id"])
    await cur.close()
    vault = KeyVault(settings.vault_kek_hex)
    pt = await vault.get(db, uid, "anthropic")
    assert pt == other


async def test_unauthed_401(app_client: httpx.AsyncClient) -> None:
    r = await app_client.get("/vault/keys/anthropic")
    assert r.status_code == 401
    r2 = await app_client.put("/vault/keys/anthropic", json={"key": VALID_KEY})
    assert r2.status_code == 401
    r3 = await app_client.delete("/vault/keys/anthropic")
    assert r3.status_code == 401


async def test_put_emits_activity_event(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    await _authed(app_client, db, settings)
    await app_client.put("/vault/keys/anthropic", json={"key": VALID_KEY})
    activity = await app_client.get("/activity")
    actions = [e["action"] for e in activity.json()]
    assert "vault.key_saved" in actions


async def test_delete_emits_activity_event(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    await _authed(app_client, db, settings)
    await app_client.put("/vault/keys/anthropic", json={"key": VALID_KEY})
    await app_client.delete("/vault/keys/anthropic")
    activity = await app_client.get("/activity")
    actions = [e["action"] for e in activity.json()]
    assert "vault.key_removed" in actions
