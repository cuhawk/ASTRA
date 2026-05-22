"""Session 5 e2e: authed user → /llm/nl_to_cypher (free + pro) → /llm/advise → audit log + killswitch."""
from __future__ import annotations

import re

import aiosqlite
import httpx
import pytest

from backend.auth.sessions import create_session, make_signer, sign_sid
from backend.config import Settings
from backend.db.connection import connect
from backend.vault.envelope import KeyVault

GEMINI_URL_RE = re.compile(r"https://generativelanguage\.googleapis\.com/.+generateContent.*")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def _gemini_ok(text: str = "hello", in_tok: int = 10, out_tok: int = 5) -> dict:
    return {
        "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}],
        "usageMetadata": {"promptTokenCount": in_tok, "candidatesTokenCount": out_tok},
    }


def _anthropic_ok(text: str = "hi", model: str = "claude-sonnet-4-5-20250929") -> dict:
    return {
        "content": [{"type": "text", "text": text}],
        "usage": {"input_tokens": 7, "output_tokens": 3},
        "model": model,
    }


async def _seed_user(db: aiosqlite.Connection, github_id: int = 7777) -> int:
    await db.execute(
        "INSERT INTO users (github_id, github_login, email, created_at, last_login_at) "
        "VALUES (?, ?, ?, strftime('%s', 'now'), strftime('%s', 'now'))",
        (github_id, "alice", "alice@example.com"),
    )
    await db.commit()
    cur = await db.execute("SELECT id FROM users WHERE github_id = ?", (github_id,))
    return (await cur.fetchone())["id"]


async def _authed(
    client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> int:
    user_id = await _seed_user(db)
    sess = await create_session(db, user_id, settings.session_max_age_s)
    await db.commit()
    signer = make_signer(settings.session_secret)
    client.cookies.set(settings.session_cookie_name, sign_sid(signer, sess.id))
    return user_id


@pytest.fixture
def settings_with_gemini(settings: Settings) -> Settings:
    return settings.model_copy(update={"gemini_api_key": "test-gemini-key"})


@pytest.mark.asyncio
async def test_free_tier_routes_to_gemini(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings_with_gemini: Settings, httpx_mock
):
    app_client._transport.app.state.settings = settings_with_gemini  # type: ignore[attr-defined]
    user_id = await _authed(app_client, db, settings_with_gemini)

    httpx_mock.add_response(method="POST", url=GEMINI_URL_RE, json=_gemini_ok())

    r = await app_client.post("/llm/nl_to_cypher", json={"prompt": "match all"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["provider"] == "gemini"
    assert body["text"] == "hello"
    assert body["cost_usd"] > 0

    cur = await db.execute(
        "SELECT provider, model, reason, prompt_tokens, completion_tokens, outcome "
        "FROM audit_llm_calls WHERE user_id = ?",
        (user_id,),
    )
    rows = await cur.fetchall()
    assert len(rows) == 1
    assert rows[0]["provider"] == "gemini"
    assert rows[0]["reason"] == "nl_to_cypher"
    assert rows[0]["outcome"] == "ok"


@pytest.mark.asyncio
async def test_pro_tier_routes_to_anthropic_when_vault_has_key(
    app_client: httpx.AsyncClient,
    db: aiosqlite.Connection,
    settings_with_gemini: Settings,
    httpx_mock,
):
    app_client._transport.app.state.settings = settings_with_gemini  # type: ignore[attr-defined]
    user_id = await _authed(app_client, db, settings_with_gemini)

    vault = KeyVault(settings_with_gemini.vault_kek_hex)
    vault_db = await connect(settings_with_gemini.db_path)
    try:
        await vault.put(vault_db, user_id, "anthropic", "sk-ant-test-key")
    finally:
        await vault_db.close()

    httpx_mock.add_response(method="POST", url=ANTHROPIC_URL, json=_anthropic_ok())

    r = await app_client.post("/llm/nl_to_cypher", json={"prompt": "match all"})
    assert r.status_code == 200, r.text
    assert r.json()["provider"] == "anthropic"

    cur = await db.execute("SELECT provider FROM audit_llm_calls WHERE user_id = ?", (user_id,))
    assert (await cur.fetchone())["provider"] == "anthropic"


@pytest.mark.asyncio
async def test_advise_requires_vault_key(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings_with_gemini: Settings
):
    app_client._transport.app.state.settings = settings_with_gemini  # type: ignore[attr-defined]
    await _authed(app_client, db, settings_with_gemini)

    r = await app_client.post("/llm/advise", json={"prompt": "is this xss?"})
    assert r.status_code == 502
    assert "no anthropic key" in r.json()["detail"]


@pytest.mark.asyncio
async def test_advise_uses_sonnet_then_opus_on_uncertain(
    app_client: httpx.AsyncClient,
    db: aiosqlite.Connection,
    settings_with_gemini: Settings,
    httpx_mock,
):
    app_client._transport.app.state.settings = settings_with_gemini  # type: ignore[attr-defined]
    user_id = await _authed(app_client, db, settings_with_gemini)

    vault = KeyVault(settings_with_gemini.vault_kek_hex)
    vault_db = await connect(settings_with_gemini.db_path)
    try:
        await vault.put(vault_db, user_id, "anthropic", "sk-ant-test-key")
    finally:
        await vault_db.close()

    httpx_mock.add_response(
        method="POST",
        url=ANTHROPIC_URL,
        json=_anthropic_ok(text='{"verdict":"uncertain"}', model=settings_with_gemini.anthropic_default_model),
    )
    httpx_mock.add_response(
        method="POST",
        url=ANTHROPIC_URL,
        json=_anthropic_ok(text='{"verdict":"vulnerable"}', model=settings_with_gemini.anthropic_opus_model),
    )

    r = await app_client.post("/llm/advise", json={"prompt": "look at this chain"})
    assert r.status_code == 200, r.text
    assert r.json()["model"] == settings_with_gemini.anthropic_opus_model


@pytest.mark.asyncio
async def test_killswitch_blocks_free_tier_after_cap(
    app_client: httpx.AsyncClient,
    db: aiosqlite.Connection,
    settings_with_gemini: Settings,
    httpx_mock,
):
    s = settings_with_gemini.model_copy(update={"daily_spend_cap_usd": 0.0000001})
    app_client._transport.app.state.settings = s  # type: ignore[attr-defined]
    await _authed(app_client, db, s)

    httpx_mock.add_response(method="POST", url=GEMINI_URL_RE, json=_gemini_ok())

    r1 = await app_client.post("/llm/nl_to_cypher", json={"prompt": "x"})
    assert r1.status_code == 200

    r2 = await app_client.post("/llm/nl_to_cypher", json={"prompt": "x"})
    assert r2.status_code == 503
    assert "killswitch" in r2.json()["detail"]


@pytest.mark.asyncio
async def test_spend_endpoint_returns_totals(
    app_client: httpx.AsyncClient,
    db: aiosqlite.Connection,
    settings_with_gemini: Settings,
    httpx_mock,
):
    app_client._transport.app.state.settings = settings_with_gemini  # type: ignore[attr-defined]
    await _authed(app_client, db, settings_with_gemini)

    httpx_mock.add_response(method="POST", url=GEMINI_URL_RE, json=_gemini_ok())
    await app_client.post("/llm/nl_to_cypher", json={"prompt": "x"})

    r = await app_client.get("/llm/spend")
    assert r.status_code == 200
    body = r.json()
    assert body["gemini"] > 0
    assert body["anthropic"] == 0
    assert body["cap_usd"] == settings_with_gemini.daily_spend_cap_usd
