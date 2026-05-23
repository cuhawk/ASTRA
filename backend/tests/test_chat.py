from __future__ import annotations

from unittest.mock import AsyncMock, patch

import aiosqlite
import httpx

from backend.auth.sessions import create_session, make_signer, sign_sid
from backend.chat.service import append_message, list_messages
from backend.config import Settings
from backend.llm.base import LLMError, LLMResponse, LLMUsage


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


async def _seed_run(db: aiosqlite.Connection, user_id: int, run_id: str = "abc123") -> str:
    await db.execute(
        "INSERT INTO runs (id, user_id, url, status, created_at, files, functions, edges) "
        "VALUES (?, ?, 'http://x/', 'done', strftime('%s','now'), 0, 0, 0)",
        (run_id, user_id),
    )
    await db.commit()
    return run_id


def _fake_response(text: str = "ok!") -> LLMResponse:
    return LLMResponse(
        provider="gemini",
        model="gemini-3.1-flash-lite",
        text=text,
        usage=LLMUsage(prompt_tokens=10, completion_tokens=4),
        cost_usd=0.0001,
        duration_ms=42,
    )


async def test_append_and_list(db: aiosqlite.Connection) -> None:
    uid = await _seed_user(db)
    rid = await _seed_run(db, uid)
    await append_message(db, run_id=rid, role="user", content="hi")
    await append_message(db, run_id=rid, role="assistant", content="hello")
    rows = await list_messages(db, rid)
    assert [r.role for r in rows] == ["user", "assistant"]
    assert [r.content for r in rows] == ["hi", "hello"]


async def test_get_chat_empty(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    uid = await _authed(app_client, db, settings)
    await _seed_run(db, uid, "r1")
    r = await app_client.get("/runs/r1/chat")
    assert r.status_code == 200
    assert r.json() == []


async def test_get_chat_unknown_run_404(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    await _authed(app_client, db, settings)
    r = await app_client.get("/runs/missing/chat")
    assert r.status_code == 404


async def test_post_chat_persists_turns(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    uid = await _authed(app_client, db, settings)
    rid = await _seed_run(db, uid, "r2")

    with patch(
        "backend.chat.service.GeminiClient.generate",
        new=AsyncMock(return_value=_fake_response("greetings, friend")),
    ):
        r = await app_client.post(
            f"/runs/{rid}/chat", json={"message": "summarize this run"}
        )
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "assistant"
    assert r.json()["content"] == "greetings, friend"

    history = await app_client.get(f"/runs/{rid}/chat")
    rows = history.json()
    assert [m["role"] for m in rows] == ["user", "assistant"]
    assert [m["content"] for m in rows] == ["summarize this run", "greetings, friend"]
    assert rows[1]["llm_call_id"] is not None


async def test_post_chat_audit_transcript_captured(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    uid = await _authed(app_client, db, settings)
    rid = await _seed_run(db, uid, "r3")

    with patch(
        "backend.chat.service.GeminiClient.generate",
        new=AsyncMock(return_value=_fake_response("audit-me")),
    ):
        await app_client.post(f"/runs/{rid}/chat", json={"message": "hello"})

    cur = await db.execute(
        "SELECT reason, prompt_text, response_text, provider FROM audit_llm_calls"
    )
    rows = await cur.fetchall()
    await cur.close()
    assert len(rows) == 1
    assert rows[0]["reason"] == "chat"
    assert rows[0]["provider"] == "gemini"
    assert "hello" in (rows[0]["prompt_text"] or "")
    assert rows[0]["response_text"] == "audit-me"


async def test_post_chat_unknown_run_404(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    await _authed(app_client, db, settings)
    r = await app_client.post("/runs/missing/chat", json={"message": "hi"})
    assert r.status_code == 404


async def test_post_chat_validation(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    uid = await _authed(app_client, db, settings)
    await _seed_run(db, uid, "r4")
    r = await app_client.post("/runs/r4/chat", json={"message": ""})
    assert r.status_code == 422


async def test_post_chat_llm_error_502(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    uid = await _authed(app_client, db, settings)
    rid = await _seed_run(db, uid, "r5")
    with patch(
        "backend.chat.service.GeminiClient.generate",
        new=AsyncMock(side_effect=LLMError("upstream down", provider="gemini")),
    ):
        r = await app_client.post(f"/runs/{rid}/chat", json={"message": "hi"})
    assert r.status_code == 502


async def test_post_chat_other_user_404(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    uid_other = await _seed_user(db, login="other")
    rid = await _seed_run(db, uid_other, "r6")
    await _authed(app_client, db, settings)
    r = await app_client.post(f"/runs/{rid}/chat", json={"message": "hi"})
    assert r.status_code == 404


async def test_post_chat_unauthed_401(app_client: httpx.AsyncClient) -> None:
    r = await app_client.post("/runs/any/chat", json={"message": "hi"})
    assert r.status_code == 401


async def test_chat_sends_multi_turn_contents_with_stable_prefix(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    uid = await _authed(app_client, db, settings)
    rid = await _seed_run(db, uid, "r_prefix")
    captured: list[list[dict]] = []

    async def fake_generate(self, contents, *, system, max_tokens=1024, temperature=0.2):
        captured.append(contents)
        return _fake_response(f"reply {len(captured)}")

    with patch(
        "backend.chat.service.GeminiClient.generate", new=fake_generate
    ):
        await app_client.post(f"/runs/{rid}/chat", json={"message": "first"})
        await app_client.post(f"/runs/{rid}/chat", json={"message": "second"})

    assert len(captured) == 2
    first, second = captured
    # First two turns are the stable prefix: run-context primer + model ack.
    assert first[0]["role"] == "user"
    assert "ASTRA RUN CONTEXT" in first[0]["parts"][0]["text"]
    assert first[1]["role"] == "model"
    # That prefix must be byte-identical between calls (cache key).
    assert first[0] == second[0]
    assert first[1] == second[1]
    # And the prior assistant turn must also be re-sent verbatim so the
    # cached prefix can grow as the conversation extends.
    assert second[2]["role"] == "user" and second[2]["parts"][0]["text"] == "first"
    assert second[3]["role"] == "model" and second[3]["parts"][0]["text"] == "reply 1"
    assert second[-1]["role"] == "user" and second[-1]["parts"][0]["text"] == "second"


async def test_chat_audit_persists_cached_token_count(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    uid = await _authed(app_client, db, settings)
    rid = await _seed_run(db, uid, "r_cached")
    cached_resp = LLMResponse(
        provider="gemini",
        model="gemini-3.1-flash-lite",
        text="hit",
        usage=LLMUsage(
            prompt_tokens=1200, completion_tokens=15, cached_prompt_tokens=900
        ),
        cost_usd=0.0,  # recomputed inside cost_for; doesn't matter here
        duration_ms=42,
    )
    with patch(
        "backend.chat.service.GeminiClient.generate",
        new=AsyncMock(return_value=cached_resp),
    ):
        await app_client.post(f"/runs/{rid}/chat", json={"message": "hi"})

    cur = await db.execute(
        "SELECT prompt_tokens, cached_prompt_tokens FROM audit_llm_calls"
    )
    rows = await cur.fetchall()
    await cur.close()
    assert len(rows) == 1
    assert rows[0]["prompt_tokens"] == 1200
    assert rows[0]["cached_prompt_tokens"] == 900
