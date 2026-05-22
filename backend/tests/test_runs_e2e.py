"""Session 6 e2e: POST /runs against the react-min fixture, await execution, assert Kuzu populated."""
from __future__ import annotations

import asyncio
import socket
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import aiosqlite
import httpx
import pytest

from backend.auth.sessions import create_session, make_signer, sign_sid
from backend.config import Settings
from backend.pillars.memory.graph import GraphStore
from backend.pillars.memory.runs import RunLayout
from backend.runs.worker import make_executor

_FIXTURE_DIST = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "react-min" / "dist"
)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *_args: object) -> None:
        return


def _serve(directory: Path, port: int) -> ThreadingHTTPServer:
    handler = type(
        "Bound",
        (_Quiet,),
        {"__init__": lambda self, *a, **kw: SimpleHTTPRequestHandler.__init__(
            self, *a, directory=str(directory), **kw
        )},
    )
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


async def _seed_user(db: aiosqlite.Connection, github_id: int = 9999) -> int:
    await db.execute(
        "INSERT INTO users (github_id, github_login, email, created_at, last_login_at) "
        "VALUES (?, 'alice', NULL, strftime('%s','now'), strftime('%s','now'))",
        (github_id,),
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


@pytest.mark.asyncio
async def test_full_run_lifecycle_against_react_min(
    app_client: httpx.AsyncClient, db: aiosqlite.Connection, settings: Settings, tmp_path: Path
) -> None:
    assert _FIXTURE_DIST.is_dir()
    s = settings.model_copy(update={"runs_root": str(tmp_path / "runs")})
    app_client._transport.app.state.settings = s  # type: ignore[attr-defined]
    app_client._transport.app.state.run_executor = make_executor(s)  # type: ignore[attr-defined]
    user_id = await _authed(app_client, db, s)

    port = _free_port()
    server = _serve(_FIXTURE_DIST, port)
    try:
        post = await app_client.post(
            "/runs", json={"url": f"http://127.0.0.1:{port}/"}
        )
        assert post.status_code == 202, post.text
        run_id = post.json()["id"]

        for _ in range(60):
            await asyncio.sleep(0.5)
            r = await app_client.get(f"/runs/{run_id}")
            assert r.status_code == 200
            status = r.json()["status"]
            if status in ("done", "failed"):
                break
        assert r.json()["status"] == "done", r.json()
        assert r.json()["files"] >= 1
        assert r.json()["functions"] >= 1
    finally:
        server.shutdown()

    layout = RunLayout(
        root=Path(s.runs_root).resolve(), user_id=f"u{user_id}", run_id=run_id
    )
    with GraphStore(layout.graph_path) as g:
        rows = g.query("MATCH (f:Function) RETURN f.name AS name LIMIT 5")
    names = [row["name"] for row in rows]
    assert len(names) >= 1, rows
