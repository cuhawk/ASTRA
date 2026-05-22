"""End-to-end Session 4: login via GitHub → /auth/me → /probe/quota → vault put/get → logout."""
from __future__ import annotations

import aiosqlite
import httpx
import pytest

from backend.config import Settings
from backend.db.connection import connect
from backend.vault.envelope import KeyVault


async def _walk_login(
    app_client: httpx.AsyncClient, httpx_mock, settings: Settings, github_id: int = 4242
) -> dict:
    login = await app_client.get("/auth/github/login", follow_redirects=False)
    assert login.status_code == 302
    state = login.cookies["astra_oauth_state"]

    httpx_mock.add_response(
        url="https://github.com/login/oauth/access_token",
        method="POST",
        json={"access_token": "gho_test", "token_type": "bearer"},
    )
    httpx_mock.add_response(
        url="https://api.github.com/user",
        method="GET",
        json={"id": github_id, "login": "alice", "email": "alice@example.com"},
    )

    cb = await app_client.get(
        f"/auth/github/callback?code=abc&state={state}", follow_redirects=False
    )
    assert cb.status_code == 302
    me = await app_client.get("/auth/me")
    assert me.status_code == 200
    return me.json()


@pytest.mark.asyncio
async def test_full_session_lifecycle(app_client, httpx_mock, settings: Settings) -> None:
    user = await _walk_login(app_client, httpx_mock, settings)
    assert user["github_login"] == "alice"
    assert user["github_id"] == 4242

    probe1 = await app_client.get("/probe/quota")
    assert probe1.status_code == 200
    assert probe1.json() == {"used": 1, "remaining": 99, "limit": 100}

    probe2 = await app_client.get("/probe/quota")
    assert probe2.json() == {"used": 2, "remaining": 98, "limit": 100}

    vault = KeyVault(settings.vault_kek_hex)
    db: aiosqlite.Connection = await connect(settings.db_path)
    try:
        await vault.put(db, user["id"], "anthropic", "sk-ant-secret-marker-xyz")
        roundtrip = await vault.get(db, user["id"], "anthropic")
        assert roundtrip == "sk-ant-secret-marker-xyz"

        cur = await db.execute(
            "SELECT key_ciphertext FROM api_keys_encrypted WHERE user_id = ?",
            (user["id"],),
        )
        row = await cur.fetchone()
        assert b"sk-ant-secret-marker-xyz" not in bytes(row["key_ciphertext"])
    finally:
        await db.close()

    logout = await app_client.post("/auth/logout")
    assert logout.status_code == 204

    me_after = await app_client.get("/auth/me")
    assert me_after.status_code == 401


@pytest.mark.asyncio
async def test_quota_exhaustion_returns_429(app_client, httpx_mock, settings: Settings) -> None:
    app_client._transport.app.state.settings.free_tier_daily_limit = 2  # type: ignore[attr-defined]
    await _walk_login(app_client, httpx_mock, settings)

    assert (await app_client.get("/probe/quota")).status_code == 200
    assert (await app_client.get("/probe/quota")).status_code == 200
    blocked = await app_client.get("/probe/quota")
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "quota exceeded"
