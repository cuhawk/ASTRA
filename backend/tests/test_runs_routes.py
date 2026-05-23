from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import aiosqlite
import httpx

from backend.auth.sessions import create_session, make_signer, sign_sid
from backend.config import Settings
from backend.runs.service import RunRecord


async def _authed(
    client: httpx.AsyncClient,
    db: aiosqlite.Connection,
    settings: Settings,
    github_id: int = 4242,
    login: str = "alice",
) -> int:
    await db.execute(
        "INSERT INTO users (github_id, github_login, email, created_at, last_login_at) "
        "VALUES (?, ?, NULL, strftime('%s','now'), strftime('%s','now'))",
        (github_id, login),
    )
    await db.commit()
    cur = await db.execute("SELECT id FROM users WHERE github_id = ?", (github_id,))
    row = await cur.fetchone()
    await cur.close()
    user_id = int(row["id"])
    sess = await create_session(db, user_id, settings.session_max_age_s)
    await db.commit()
    signer = make_signer(settings.session_secret)
    client.cookies.set(settings.session_cookie_name, sign_sid(signer, sess.id))
    return user_id


async def test_post_runs_unauthed_401(app_client: httpx.AsyncClient) -> None:
    r = await app_client.post("/runs", json={"url": "http://example.invalid/"})
    assert r.status_code == 401


async def test_post_runs_creates_pending(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    await _authed(app_client, db, settings)
    r = await app_client.post("/runs", json={"url": "http://example.invalid/"})
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert body["url"].startswith("http://example.invalid")
    assert body["files"] == 0
    assert body["functions"] == 0
    assert body["edges"] == 0


async def test_post_runs_invalid_url_422(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    await _authed(app_client, db, settings)
    r = await app_client.post("/runs", json={"url": "not a url"})
    assert r.status_code == 422


async def test_post_runs_dispatches_executor(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    await _authed(app_client, db, settings)

    done = asyncio.Event()
    captured: dict = {}

    async def fake_executor(rec: RunRecord) -> None:
        captured["rec"] = rec
        done.set()

    app_client._transport.app.state.run_executor = fake_executor  # type: ignore[attr-defined]

    r = await app_client.post("/runs", json={"url": "http://example.invalid/"})
    assert r.status_code == 202, r.text

    await asyncio.wait_for(done.wait(), timeout=2.0)
    assert isinstance(captured["rec"], RunRecord)
    assert captured["rec"].id == r.json()["id"]
    assert captured["rec"].status == "pending"


async def test_get_runs_lists_only_caller(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    u1 = await _authed(app_client, db, settings, github_id=1, login="a")
    # Seed a second user + two runs directly via SQL.
    await db.execute(
        "INSERT INTO users (github_id, github_login, email, created_at, last_login_at) "
        "VALUES (2, 'b', NULL, strftime('%s','now'), strftime('%s','now'))"
    )
    await db.commit()
    cur = await db.execute("SELECT id FROM users WHERE github_id = 2")
    u2 = int((await cur.fetchone())["id"])
    await cur.close()

    from backend.runs.service import create_run as _create

    await _create(db, user_id=u1, url="http://a1/")
    await _create(db, user_id=u1, url="http://a2/")
    await _create(db, user_id=u2, url="http://b1/")
    await _create(db, user_id=u2, url="http://b2/")

    r = await app_client.get("/runs")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2
    assert all(it["user_id"] == u1 for it in items)


async def test_delete_run_removes_row_and_returns_204(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    await _authed(app_client, db, settings)
    r = await app_client.post("/runs", json={"url": "http://example.invalid/"})
    assert r.status_code == 202, r.text
    rid = r.json()["id"]

    d = await app_client.delete(f"/runs/{rid}")
    assert d.status_code == 204, d.text

    cur = await db.execute("SELECT id FROM runs WHERE id = ?", (rid,))
    row = await cur.fetchone()
    await cur.close()
    assert row is None

    g = await app_client.get(f"/runs/{rid}")
    assert g.status_code == 404


async def test_delete_run_missing_returns_404(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    await _authed(app_client, db, settings)
    d = await app_client.delete("/runs/deadbeef0000")
    assert d.status_code == 404


async def test_delete_run_other_user_404(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    await db.execute(
        "INSERT INTO users (github_id, github_login, email, created_at, last_login_at) "
        "VALUES (1, 'a', NULL, strftime('%s','now'), strftime('%s','now'))"
    )
    await db.commit()
    cur = await db.execute("SELECT id FROM users WHERE github_id = 1")
    u1 = int((await cur.fetchone())["id"])
    await cur.close()

    from backend.runs.service import create_run as _create

    victim = await _create(db, user_id=u1, url="http://victim/")

    await _authed(app_client, db, settings, github_id=2, login="b")
    d = await app_client.delete(f"/runs/{victim.id}")
    assert d.status_code == 404

    cur = await db.execute("SELECT id FROM runs WHERE id = ?", (victim.id,))
    row = await cur.fetchone()
    await cur.close()
    assert row is not None


async def test_delete_run_unauthed_401(app_client: httpx.AsyncClient) -> None:
    d = await app_client.delete("/runs/anything")
    assert d.status_code == 401


async def test_get_run_other_user_404(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    # u1 owns a run; authed client is u2.
    await db.execute(
        "INSERT INTO users (github_id, github_login, email, created_at, last_login_at) "
        "VALUES (1, 'a', NULL, strftime('%s','now'), strftime('%s','now'))"
    )
    await db.commit()
    cur = await db.execute("SELECT id FROM users WHERE github_id = 1")
    u1 = int((await cur.fetchone())["id"])
    await cur.close()

    from backend.runs.service import create_run as _create

    other_run = await _create(db, user_id=u1, url="http://victim/")

    await _authed(app_client, db, settings, github_id=2, login="b")
    r = await app_client.get(f"/runs/{other_run.id}")
    assert r.status_code == 404


async def test_list_run_files_and_content(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings
) -> None:
    from pathlib import Path
    user_id = await _authed(app_client, db, settings)
    
    from backend.runs.service import create_run as _create
    run = await _create(db, user_id=user_id, url="http://example.invalid/")
    
    from backend.pillars.memory.runs import RunLayout
    layout = RunLayout(
        root=Path(settings.runs_root).resolve(),
        user_id=f"u{user_id}",
        run_id=run.id,
    )
    layout.create()
    
    src_file = layout.sourcemap_dir / "src" / "App.tsx"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("console.log('hello world');", encoding="utf-8")
    
    r = await app_client.get(f"/runs/{run.id}/files")
    assert r.status_code == 200, r.text
    files = r.json()
    assert "src/App.tsx" in files
    
    r = await app_client.get(f"/runs/{run.id}/files/content", params={"path": "src/App.tsx"})
    assert r.status_code == 200, r.text
    assert r.json()["content"] == "console.log('hello world');"
    
    r = await app_client.get(f"/runs/{run.id}/files/content", params={"path": "../../../etc/passwd"})
    assert r.status_code == 400

